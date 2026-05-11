"""Integration-тесты блока 1: auth + me + telegram link."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# ───────────────────── helpers ─────────────────────


async def _register(api_client, email="alice@example.com", password="pass1234", first_name="Alice"):
    return await api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "first_name": first_name},
    )


def _bearer(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


# ───────────────────── /auth ─────────────────────


@pytest.mark.asyncio
async def test_register_returns_token_pair_and_persists(session, api_client):
    response = await _register(api_client)
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body and body["access_token"]
    assert "refresh_token" in body and body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["access_token"] != body["refresh_token"]


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(session, api_client):
    assert (await _register(api_client)).status_code == 201
    second = await _register(api_client)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_register_password_too_short(session, api_client):
    response = await api_client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "short1"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_password_must_have_letter_and_digit(session, api_client):
    response = await api_client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "alphabetic"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email(session, api_client):
    response = await api_client.post(
        "/api/v1/auth/register",
        json={"email": "not-email", "password": "pass1234"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_with_correct_password_returns_tokens(session, api_client):
    await _register(api_client, email="bob@example.com", password="pass1234")
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "pass1234"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_401(session, api_client):
    await _register(api_client, email="bob@example.com", password="pass1234")
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrong-pw1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user_returns_401_not_404(session, api_client):
    # одно и то же сообщение чтобы не палить enumeration
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "pass1234"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_normalizes_email_case(session, api_client):
    await _register(api_client, email="case@example.com", password="pass1234")
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "CASE@example.com", "password": "pass1234"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_revokes_old(session, api_client):
    tokens = (await _register(api_client)).json()
    refreshed = await api_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # старый refresh уже не работает
    second_use = await api_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert second_use.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_garbage_401(session, api_client):
    response = await api_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "not.a.jwt"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(session, api_client):
    # access-токен в /refresh идти не должен
    tokens = (await _register(api_client)).json()
    response = await api_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(session, api_client):
    tokens = (await _register(api_client)).json()
    logout = await api_client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout.status_code == 204
    after = await api_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert after.status_code == 401


# ───────────────────── /me ─────────────────────


@pytest.mark.asyncio
async def test_me_requires_auth(session, api_client):
    response = await api_client.get("/api/v1/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_profile(session, api_client):
    tokens = (await _register(api_client)).json()
    response = await api_client.get("/api/v1/me", headers=_bearer(tokens["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["first_name"] == "Alice"
    assert body["role"] == "user"
    assert body["telegram_id"] is None
    assert body["subjects"] == []
    assert body["onboarding_completed"] is False


@pytest.mark.asyncio
async def test_me_with_garbage_token_401(session, api_client):
    response = await api_client.get("/api/v1/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_profile_updates_grade_subjects_hours(session, api_client):
    tokens = (await _register(api_client)).json()
    response = await api_client.patch(
        "/api/v1/me/profile",
        headers=_bearer(tokens["access_token"]),
        json={
            "grade": 11,
            "subjects": ["math", "russian", "informatics"],
            "weekly_hours": 20,
            "onboarding_completed": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["grade"] == 11
    assert sorted(body["subjects"]) == ["informatics", "math", "russian"]
    assert body["weekly_hours"] == 20
    assert body["onboarding_completed"] is True


@pytest.mark.asyncio
async def test_patch_profile_rejects_unknown_subject(session, api_client):
    tokens = (await _register(api_client)).json()
    response = await api_client.patch(
        "/api/v1/me/profile",
        headers=_bearer(tokens["access_token"]),
        json={"subjects": ["math", "russian", "fortune-telling"]},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_profile_rejects_too_few_subjects(session, api_client):
    tokens = (await _register(api_client)).json()
    response = await api_client.patch(
        "/api/v1/me/profile",
        headers=_bearer(tokens["access_token"]),
        json={"subjects": ["math"]},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_profile_rejects_invalid_grade(session, api_client):
    tokens = (await _register(api_client)).json()
    response = await api_client.patch(
        "/api/v1/me/profile",
        headers=_bearer(tokens["access_token"]),
        json={"grade": 9},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_profile_rejects_invalid_weekly_hours(session, api_client):
    tokens = (await _register(api_client)).json()
    response = await api_client.patch(
        "/api/v1/me/profile",
        headers=_bearer(tokens["access_token"]),
        json={"weekly_hours": 99},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_settings_merges_keys(session, api_client):
    tokens = (await _register(api_client)).json()
    headers = _bearer(tokens["access_token"])

    r1 = await api_client.patch(
        "/api/v1/me/settings",
        headers=headers,
        json={"settings": {"theme": "dark", "notifications": True}},
    )
    assert r1.status_code == 200
    assert r1.json()["settings"] == {"theme": "dark", "notifications": True}

    # частичное обновление: theme остаётся, notifications удаляется
    r2 = await api_client.patch(
        "/api/v1/me/settings",
        headers=headers,
        json={"settings": {"notifications": None, "lang": "ru"}},
    )
    assert r2.status_code == 200
    assert r2.json()["settings"] == {"theme": "dark", "lang": "ru"}


@pytest.mark.asyncio
async def test_delete_me_soft_deletes_and_revokes_tokens(session, api_client):
    tokens = (await _register(api_client)).json()
    headers = _bearer(tokens["access_token"])

    deleted = await api_client.delete("/api/v1/me", headers=headers)
    assert deleted.status_code == 204

    # access-токен ещё валиден по подписи, но в БД user.deleted_at != null → 401
    me = await api_client.get("/api/v1/me", headers=headers)
    assert me.status_code == 401

    # refresh ревокнулся
    r = await api_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert r.status_code == 401

    # email освободился — можно зарегаться заново
    again = await _register(api_client)
    assert again.status_code == 201


# ───────────────────── /me/telegram/link ─────────────────────


@pytest.mark.asyncio
async def test_telegram_link_generates_code(session, api_client):
    tokens = (await _register(api_client)).json()
    headers = _bearer(tokens["access_token"])
    response = await api_client.post("/api/v1/me/telegram/link", headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert len(body["code"]) >= 6
    assert "expires_at" in body


@pytest.mark.asyncio
async def test_telegram_link_409_when_already_linked(session, api_client):
    from bot.db.models import User as UserModel
    from sqlalchemy import select

    tokens = (await _register(api_client)).json()
    headers = _bearer(tokens["access_token"])
    # эмулируем что юзер уже привязан
    user = await session.scalar(select(UserModel).where(UserModel.email == "alice@example.com"))
    user.telegram_id = 999_888_777
    await session.commit()

    response = await api_client.post("/api/v1/me/telegram/link", headers=headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_telegram_unlink_clears_telegram_id(session, api_client):
    from bot.db.models import User as UserModel
    from sqlalchemy import select

    tokens = (await _register(api_client)).json()
    headers = _bearer(tokens["access_token"])
    user = await session.scalar(select(UserModel).where(UserModel.email == "alice@example.com"))
    user.telegram_id = 123
    user.username = "alice_tg"
    await session.commit()

    response = await api_client.delete("/api/v1/me/telegram/link", headers=headers)
    assert response.status_code == 204

    me = await api_client.get("/api/v1/me", headers=headers)
    assert me.json()["telegram_id"] is None
    assert me.json()["username"] is None


@pytest.mark.asyncio
async def test_telegram_unlink_404_when_not_linked(session, api_client):
    tokens = (await _register(api_client)).json()
    headers = _bearer(tokens["access_token"])
    response = await api_client.delete("/api/v1/me/telegram/link", headers=headers)
    assert response.status_code == 404
