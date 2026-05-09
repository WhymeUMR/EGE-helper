"""Колбэки главного меню

menu:settings и menu:home ведут на настоящие экраны. Остальные menu:*
пока показывают тосты-заглушки — до момента, когда соответствующие
фичи будут готовы.

Внутри этого роутера порядок регистрации важен: точные хендлеры
(menu:settings, menu:home) должны быть выше catch-all'а menu:*,
иначе диспетчер заглотит их в заглушку первым делом.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.menu import main_menu_keyboard, settings_keyboard
from bot.services.users import get_or_create_user
from bot.texts import main_menu_text, settings_text
from bot.utils.names import display_name

router = Router()


_MENU_STUBS: dict[str, tuple[str, str]] = {
    "practice": (
        "🎯 Решать задачи",
        "Скоро здесь будут адаптивные задачи по SM-2.",
    ),
    "stats": (
        "📊 Статистика",
        "Скоро увидишь свой прогресс, стрики и сильные/слабые темы.",
    ),
    "materials": (
        "📚 Материалы",
        "Конспекты, формулы и шпаргалки — уже скоро.",
    ),
    "mock": (
        "📝 Пробный вариант",
        "Полноценный пробный вариант ЕГЭ с автопроверкой — уже скоро.",
    ),
}


@router.callback_query(F.data == "menu:settings")
async def menu_settings(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)

    await callback.message.edit_text(
        settings_text(user, name), reply_markup=settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:home")
async def menu_home(
    callback: CallbackQuery,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tg_user = callback.from_user
    name = display_name(tg_user)
    async with db_session_factory() as session:
        user = await get_or_create_user(session, tg_user)

    await callback.message.edit_text(
        main_menu_text(user, name), reply_markup=main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("menu:"))
async def main_menu_stub(callback: CallbackQuery) -> None:
    section = callback.data.split(":", 1)[1]
    stub = _MENU_STUBS.get(section)
    if stub is None:
        # menu:settings и menu:home обрабатываются выше, сюда не доходит
        await callback.answer("В разработке 🚧", show_alert=False)
        return
    title, hint = stub
    await callback.answer(
        f"{title}\n\n{hint}\n\n🚧 В разработке", show_alert=True
    )
