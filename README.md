<div align="center">

<a href="https://github.com/WhymeUMR/EGE-helper/actions/workflows/tests.yml"><img src="https://github.com/WhymeUMR/EGE-helper/actions/workflows/tests.yml/badge.svg?branch=main" alt="tests" /></a>
<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/aiogram-3.27-2CA5E0?style=flat-square&logo=telegram&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white" />
<img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" />

# 🎯 EGE Helper

**Персональный Telegram-бот для подготовки к ЕГЭ на основе SM-2**

*Умное расписание · Автопроверка ответов · Аналитика прогресса · Open Source*

[Сообщить о баге](../../issues) · [Предложить фичу](../../issues)

</div>

---

> ⚠️ **Статус:** ранний этап разработки (`v0.2`). Работает онбординг, профиль с обратным отсчётом до ЕГЭ, главное меню как дашборд, настройки, сброс. Поднят отдельный parser-сервис: тянет каталог задач СдамГИА в Postgres, поддерживает seed-импорт из GitHub Releases. Поднят полноценный REST API платформы: auth/JWT, каталог, problems с проверкой ответов и закладками, attempts (полный цикл решения варианта с автоподсчётом баллов), Prometheus-метрики и Swagger на `/docs` — см. раздел [REST API](#rest-api). Алгоритм SM-2 и MiniApp — следующие на очереди.

---

## 🤔 Зачем это нужно?

Большинство инструментов для подготовки к ЕГЭ решают не ту проблему — они дают тебе задачи, но не говорят **когда** и **что** решать. В итоге ты либо ботаешь, что и так знаешь, либо избегаешь сложные темы.

EGE Helper будет работать иначе. Он использует алгоритм **SM-2** (тот же что в Anki) — отслеживает твои результаты по каждому типу заданий и сам решает что показать сегодня. Сложные темы появляются чаще, освоенные — реже. Никакого ручного планирования.

---

## ✨ Что уже работает

**Онбординг и профиль**
- 🚀 Полный поток: класс (10/11) → предметы (3–5) → темп (10–40 ч/нед) → опциональный пробник
- ⏱ Прогресс-бар шагов (`▰▰▱`) и явные «Шаг 1 из 3»
- ▶️ **Resume** — `/start` посреди онбординга вернёт на тот же шаг с опцией «Продолжить» / «Начать заново»
- 🔄 **Сброс** — `/reset` или Settings → «Пройти заново», с подтверждением
- 🔒 Кап на предметы (макс 5) с визуальным `🔒` и тостом-блокировкой

**Главное меню как дашборд**
- 👤 Профиль: класс, предметы (эмодзи + count), темп
- 📅 **Обратный отсчёт до ЕГЭ** — считаем от сегодня до ~23 мая для 11кл, +год для 10кл, с правильным склонением (1 день / 2 дня / 5 дней)
- 🔥 Серия и 🎯 Цель на сегодня — пока плейсхолдеры (заполнятся вместе с SM-2)
- 5 действий: Решать задачи / Статистика / Материалы / Настройки / Пробный вариант (Settings — рабочий экран, остальное пока тосты)

**Персонализация**
- 👋 Обращение по имени — берём из Telegram-апдейта, синкаем `first_name` / `username` в Postgres при `/start`
- 🌤 Time-aware greeting (Доброе утро / день / вечер / ночь) по МСК
- ✅ HTML-escape имени — никаких инъекций даже если в нике `<script>`

**Технологическое**
- 🎨 Цветные кнопки (Bot API 9.4): `primary` / `success` / `danger`
- 💬 HTML-разметка в сообщениях, аккуратные эмодзи и заголовки
- 📊 Счётчик `/start` в Redis с TTL 24 часа
- 🪵 Цветные логи через [`rich`](https://github.com/Textualize/rich) с трейсбэками
- 🐳 Docker Compose — бот + Postgres + Redis одной командой

---

## 📚 Поддерживаемые предметы

Профильная математика, русский язык, информатика, физика, химия, биология, история, обществознание, английский язык, литература, география.

---

## 🛠 Стек

| Слой | Технологии |
|---|---|
| Бот | `aiogram 3.27` (Bot API 9.4) |
| Парсер | `sdamgia-api` + `APScheduler` + `rich` (Live progress UI) |
| API | `FastAPI` + `uvicorn` (OpenAPI/Swagger из коробки) |
| TUI / DevOps | `Textual` — панель управления стеком в терминале (`make tui`) |
| База данных | `PostgreSQL 16` + `SQLAlchemy 2.x async` + `asyncpg` |
| Кэш / счётчики | `Redis 7` |
| Конфигурация | `pydantic-settings` |
| Логи | `rich` |
| Инфраструктура | `Docker` + `docker-compose` |
| CI/CD | GitHub Actions (валидация seed-дампов на каждом релизе) |

Ещё не подключено (в роадмапе): `Alembic`, `Pillow`.

---

## 🚀 Быстрый старт

### Требования
- Docker & docker-compose
- Telegram Bot Token ([получить у @BotFather](https://t.me/BotFather))

### Установка

```bash
git clone https://github.com/WhymeUMR/EGE-helper.git
cd EGE-helper
cp .env.example .env && nano .env   # вписать BOT_TOKEN

make up                              # docker compose up -d --build
make tui                             # TUI-панель управления
```

`make help` покажет все команды (`up`, `down`, `logs`, `test`, `dump`, `release`, …).

После пересборки контейнера бот сам подключается к Postgres, применяет `Base.metadata.create_all` (миграций пока нет), проверяет Redis и начинает `polling`. Парсер на пустой БД скачивает свежий seed-дамп с Releases (пара секунд) и переходит в инкрементный режим.

### TUI Control Center

```
make tui
```

`Textual`-панель с состоянием всех 5 сервисов, статистикой из БД и live-логами выбранного сервиса. Управление с клавиатуры:

| ключ | действие |
|---|---|
| ↑↓  | выбор сервиса |
| `s` | start (`docker compose up -d <svc>`) |
| `x` | stop |
| `r` | restart |
| `l` | переключить live-логи на выбранный сервис |
| `u` | поднять весь стек (`up -d --build`) |
| `d` | положить весь стек (`down`) |
| `R` | обновить статусы немедленно |
| `q` | выйти |

### Парсер задач

Каталог задач СдамГИА живёт в отдельном `parser`-сервисе. Он умеет две вещи:

1. **Импорт seed-дампа** — на пустой БД сам скачивает свежий дамп с GitHub Releases (~50–150 МБ) и разворачивает за пару минут. Так новые контрибьюторы не ждут часами полный парсинг.
2. **Инкрементный парсинг** — раз в сутки идёт на СдамГИА, проверяет что нового по сравнению с БД (дедуп по `(subject, sdamgia_id)` ДО запроса карточки), и доливает только свежее.

Прогресс рисуется красивым `rich`-баром прямо в логах:

```bash
docker compose logs -f parser
```

Если хочешь сделать дамп из своей БД и опубликовать его на Releases:

```bash
./scripts/dump-seed.sh                              # → dist/problems-YYYY-MM-DD.sql.gz
./scripts/release-seed.sh seed-$(date +%Y-%m-%d)    # → gh release create
```

Каждая публикация автоматически валидируется CI (`.github/workflows/validate-seed.yml`): свежий дамп заливается в чистую postgres и прогоняется sanity-проверка.

### REST API

Сервис `api` поднимает FastAPI на `:8000`. Интерактивный Swagger — на `/docs` (с кнопкой **Authorize** для JWT), ReDoc — на `/redoc`, чистый OpenAPI JSON — на `/openapi.json`.

Авторизация: bcrypt + JWT (access + rotating refresh). Получи пару токенов через `POST /api/v1/auth/register` или `/auth/login`, дальше шли `Authorization: Bearer <access_token>` (или жми «Authorize» в swagger).

#### Реализованные блоки (фаза 1)

Всё ниже — рабочее, покрыто 174 интеграционными тестами.

**🔐 Auth & Users** — `auth`, `me`

| | endpoint | требует JWT |
|---|---|---|
| ✅ | `POST   /api/v1/auth/register` | — |
| ✅ | `POST   /api/v1/auth/login` | — |
| ✅ | `POST   /api/v1/auth/refresh` | — |
| ✅ | `POST   /api/v1/auth/logout` | — |
| ✅ | `GET    /api/v1/me` | да |
| ✅ | `PATCH  /api/v1/me/profile` | да |
| ✅ | `PATCH  /api/v1/me/settings` | да |
| ✅ | `DELETE /api/v1/me` (soft-delete) | да |
| ✅ | `POST   /api/v1/me/telegram/link` | да |
| ✅ | `DELETE /api/v1/me/telegram/link` | да |

**📚 Catalog Meta** — `catalog`

| | endpoint |
|---|---|
| ✅ | `GET /api/v1/subjects` (все 11 предметов + статистика) |
| ✅ | `GET /api/v1/subjects/{subject}/meta` |
| ✅ | `GET /api/v1/subjects/{subject}/blueprints` (структура варианта ЕГЭ) |
| ✅ | `GET /api/v1/subjects/{subject}/topic-map` |
| ✅ | `GET /api/v1/subjects/{subject}/difficulty-scale` |
| ✅ | `GET /api/v1/subjects/{subject}/scoring-rules` |

> Шкалы перевода первичный→тестовый сейчас линейная аппроксимация (`version: "2025-linear-approx"`). Замена на официальные шкалы Рособрнадзора-2025 — в `src/api/seeds/scoring_rules.py`.

**📝 Problems** — `problems`

| | endpoint | требует JWT |
|---|---|---|
| ✅ | `GET    /api/v1/problems` | — |
| ✅ | `GET    /api/v1/problems/random` | — |
| ✅ | `GET    /api/v1/problems/{subject}/{sdamgia_id}` | — |
| ✅ | `POST   /api/v1/problems/search` (фильтры в body, ILIKE по тексту) | — |
| ✅ | `GET    /api/v1/problems/similar/{subject}/{sdamgia_id}` | — |
| ✅ | `POST   /api/v1/problems/{subject}/{sdamgia_id}/check` | — |
| ✅ | `POST   /api/v1/problems/{subject}/{sdamgia_id}/bookmark` | да |
| ✅ | `DELETE /api/v1/problems/{subject}/{sdamgia_id}/bookmark` | да |
| ✅ | `POST   /api/v1/problems/{subject}/{sdamgia_id}/report` | да |

**▶️ Attempts** — `attempts` (всё — JWT-only)

| | endpoint |
|---|---|
| ✅ | `POST  /api/v1/attempts/start` (по `variant_id` ИЛИ inline `problem_ids`/`sdamgia_ids`) |
| ✅ | `GET   /api/v1/attempts/{id}` |
| ✅ | `PATCH /api/v1/attempts/{id}` (тайминг) |
| ✅ | `POST  /api/v1/attempts/{id}/answer/{problem_id}` |
| ✅ | `POST  /api/v1/attempts/{id}/answers` (batch) |
| ✅ | `POST  /api/v1/attempts/{id}/submit` |
| ✅ | `POST  /api/v1/attempts/{id}/resume` |
| ✅ | `POST  /api/v1/attempts/{id}/abandon` |
| ✅ | `GET   /api/v1/attempts/{id}/review` |
| ✅ | `GET   /api/v1/attempts/{id}/mistakes` |

**✔️ Checking & Scoring** — `checking`

| | endpoint | требует JWT |
|---|---|---|
| ✅ | `POST /api/v1/checking/answers/validate` (нормализация) | — |
| ✅ | `POST /api/v1/checking/answers/check` | — |
| ✅ | `POST /api/v1/checking/attempts/{id}/recheck` | да |
| ✅ | `GET  /api/v1/checking/attempts/{id}/score` | да |
| ✅ | `GET  /api/v1/checking/attempts/{id}/criteria` | да |
| ✅ | `GET  /api/v1/checking/attempts/{id}/primary-points` | да |
| ✅ | `GET  /api/v1/checking/attempts/{id}/test-points` | да |

**🛠 Platform / Infra** — `meta`

| | endpoint |
|---|---|
| ✅ | `GET /health` |
| ✅ | `GET /live` |
| ✅ | `GET /ready` (пинг postgres) |
| ✅ | `GET /metrics` (Prometheus) |
| ✅ | `GET /api/v1/meta/version` |
| ✅ | `GET /api/v1/meta/features` |
| ✅ | `GET /api/v1/meta/limits` |

**Legacy** (для бота, поверх опционального `API_TOKEN` в `.env`):

| | endpoint |
|---|---|
| ✅ | `GET /api/v1/topics?subject=math` (эквивалент `/subjects/{subject}/topic-map`) |

#### Запланировано (фаза 2)

`variants` (CRUD/clone/publish/export PDF/DOCX), `analytics`, `homework/teacher/class`, `social/discussions/collections/feed`, `notifications/webhooks`, `admin/moderation`. Эндпоинты с этими тегами в `/api/v1/meta/features` помечены как `false`.

#### Пример: пройти вариант от старта до результата

```bash
# 1) регистрация
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"u@example.com","password":"pass1234"}' | jq -r .access_token)

# 2) старт attempt из 3 случайных задач по математике
ATTEMPT=$(curl -s -X POST localhost:8000/api/v1/attempts/start \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"subject":"math","sdamgia_ids":["12345","12346","12347"]}')
ID=$(echo "$ATTEMPT" | jq .id)

# 3) сохранить ответы пачкой
curl -s -X POST localhost:8000/api/v1/attempts/$ID/answers \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"answers":[{"problem_id":1,"answer":"42"},{"problem_id":2,"answer":"0,5"}]}'

# 4) submit + результат
curl -s -X POST localhost:8000/api/v1/attempts/$ID/submit \
  -H "Authorization: Bearer $TOKEN" | jq '{primary_score, test_score}'

# 5) разбор
curl -s localhost:8000/api/v1/attempts/$ID/review \
  -H "Authorization: Bearer $TOKEN" | jq '.items[] | {position, user_answer, correct_answer, is_correct}'
```

### Тесты

Юнит-тесты прогоняются без внешних зависимостей, integration-тесты используют postgres из `docker-compose`:

```bash
pip install -e ".[dev]"

# юнит — быстро, без БД
pytest tests/unit -v

# integration (нужна поднятая postgres из compose, БД ege_helper_test создастся сама)
docker compose up -d postgres
POSTGRES_TEST_HOST=localhost POSTGRES_TEST_PORT=5433 pytest tests/integration -v

# всё сразу
pytest -v
```

CI на каждый push/PR в `main` гоняет `pytest -v` с поднятой postgres-сервисом — статус виден на бейдже сверху.

### Переменные окружения

`.env` в корне проекта:

```env
BOT_TOKEN=123456:your_telegram_bot_token

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=ege_helper
POSTGRES_USER=ege_user
POSTGRES_PASSWORD=ege_password

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
```

> При запуске вне Docker замени `POSTGRES_HOST=localhost` и `POSTGRES_PORT=5433` (см. проброс портов в `docker-compose.yml`).

---

## 📁 Структура проекта

Послойная архитектура — однонаправленные зависимости, никаких циклов:

```
handlers → screens, services, texts, keyboards, utils, catalog
screens  → texts, keyboards, services
services → db, catalog
texts    → catalog, utils, db.models
keyboards → catalog
utils    → (ничего)
catalog  → (ничего)
```

```
.
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── scripts/
│   ├── dump-seed.sh         # pg_dump таблицы problems → dist/*.sql.gz
│   └── release-seed.sh      # gh release create со свежим дампом
├── .github/workflows/
│   └── validate-seed.yml    # CI: проверяем что дамп грузится в чистую PG
├── src/parser/              # отдельный async-сервис парсинга СдамГИА
│   ├── main.py              # entrypoint + APScheduler
│   ├── seed.py              # importer: качает seed.sql.gz при пустой БД
│   ├── client.py            # async-обёртка над sdamgia-api
│   ├── service.py           # каталог → категории → задачи → БД
│   ├── repository.py        # SELECT existing_ids + ON CONFLICT DO NOTHING
│   ├── progress.py          # rich Live-UI с прогресс-баром
│   ├── catalog.py           # маппинг bot.catalog → коды sdamgia
│   └── config.py            # ParserSettings: PARSER_* env-переменные
├── src/api/                 # FastAPI-сервис: фильтрация задач для бота/внешних
│   ├── main.py              # FastAPI app + uvicorn entry + индекс на старте
│   ├── routes.py            # 5 эндпоинтов /api/v1/*
│   ├── repository.py        # SQL-запросы: subjects/topics/problems/random
│   ├── schemas.py           # Pydantic response models
│   ├── auth.py              # опциональный Bearer-token через API_TOKEN
│   ├── deps.py              # async-сессия SQLAlchemy через Depends
│   └── config.py            # ApiSettings: API_HOST/API_PORT/API_TOKEN
├── src/devops/              # Textual TUI-панель управления стеком (make tui)
│   ├── app.py               # ControlCenter: services / stats / live-logs
│   ├── docker.py            # async-обёртка над `docker compose` (status/up/stop/logs)
│   └── stats.py             # запросы в БД для правой панели
├── Makefile                 # make tui / up / down / logs / test / dump / release
└── src/bot/
    ├── main.py                 # точка входа, startup/shutdown
    ├── config.py               # настройки через pydantic-settings
    ├── logging_config.py       # rich-логгер
    ├── middlewares.py          # прокидывает Redis и SessionFactory
    ├── catalog.py              # SUBJECTS, MIN/MAX_SUBJECTS, WEEKLY_HOURS, GRADE_LABELS
    ├── texts.py                # text builders (welcome/grade/subjects/hours/calibration/resume/settings/main_menu/reset_confirm/ABOUT)
    ├── screens.py              # step_screen / initial_state_screen — склейка text + keyboard по state
    ├── utils/
    │   ├── dates.py            # now_msk, greeting, days_to_ege, decline_days
    │   ├── names.py            # safe_name, display_name (HTML-escape)
    │   └── progress.py         # progress_bar (▰▰▱), step_header
    ├── services/
    │   └── users.py            # get_or_create_user, wipe_onboarding, onboarding_step_for
    ├── db/
    │   ├── models.py           # SQLAlchemy: User + Problem
    │   ├── postgres.py         # async engine + create_all
    │   └── redis_client.py
    ├── keyboards/
    │   ├── onboarding.py       # welcome/grade/subjects/hours/calibration/about_back/resume
    │   └── menu.py             # main_menu/settings/reset_confirm
    └── handlers/
        ├── __init__.py         # агрегирует 4 router'а
        ├── onboarding.py       # /start + onb:* (кроме reset/resume)
        ├── resume.py           # onb:resume:continue/restart
        ├── reset.py            # /reset + onb:reset:start/confirm/cancel
        └── menu.py             # menu:settings/home + catch-all stub
```

---

## 🗺 Роадмап

Логика версий: **контент → алгоритм → полировка → релиз**. Без контента SM-2 нечего адаптировать, без алгоритма нечего полировать, без полировки нет смысла релизить.

### v0.1 — Скелет ✅

- [x] Онбординг: класс → предметы (3–5) → темп
- [x] Resume + reset онбординга
- [x] Регистрация пользователей с синком имени из Telegram
- [x] Главное меню как дашборд + обратный отсчёт до ЕГЭ
- [x] Настройки с просмотром профиля и сбросом
- [x] Послойная архитектура (catalog / texts / screens / services / utils)

### v0.2 — Контент и платформенный API 🚧

- [x] Парсинг заданий через [`sdamgia-api`](https://github.com/anijackich/sdamgia-api) — отдельный async-сервис
- [x] Кэширование задач в собственной БД (схема + индексы, дедуп по `sdamgia_id`)
- [x] Seed-дампы на GitHub Releases с валидацией через CI
- [x] **Полноценный REST API платформы**: auth + me, catalog meta, problems (search/similar/check/bookmark/report), attempts (start/submit/review/mistakes), checking (validate/score/criteria/test-points), platform/infra
- [x] **Автопроверка ответов части 1** через `/api/v1/problems/{s}/{id}/check` и при `/attempts/{id}/submit`
- [x] **Трекинг времени решения** на уровне attempt и каждого ответа
- [ ] Расписание (часов в неделю → задач в день, ~17 мин на задачу)
- [ ] MiniApp для удобного решения задач прямо в Telegram
- [ ] Экран «📚 Материалы» — конспекты, формулы, шпаргалки
- [ ] Калибровка — опциональный пробный вариант на старте
- [ ] Замена линейной шкалы scoring на официальные таблицы Рособрнадзора-2025

### v0.3 — SM-2 и аналитика

- [ ] Реализация алгоритма SM-2 (интервалы повторения по типам задач)
- [ ] Самооценка части 2 (с показом эталонного решения) — фронт поверх `criteria_scores`
- [ ] Variants CRUD + генерация по blueprint (блок 4 API)
- [ ] Analytics endpoints: weak-topics / progress-curve / recommendations (блок 7)
- [ ] Заполнение «🔥 Серия» и «🎯 Цель на сегодня» в дашборде
- [ ] Экран «📊 Статистика» — топ слабых тем, тренд по неделям

### v0.4 — UX-полировка

- [ ] Личный кабинет с баннером (Pillow) — графика прогресса прямо в чате
- [ ] Напоминания через APScheduler — чтобы не забросить
- [ ] Разборы решений (пояснения к части 1, эталоны к части 2)
- [ ] i18n-каркас (на случай других языков / экзаменов)

### v0.5 — Релиз

- [ ] Alembic-миграции (заменить `Base.metadata.create_all`)
- [ ] Все темы ЕГЭ по основным предметам
- [ ] Тесты на хендлеры и сервисы
- [ ] Публичный деплой + мониторинг

---

## 🤝 Вклад в проект

Проект открыт для контрибьюторов. Если хочешь помочь:

1. Форкни репозиторий
2. Создай ветку для своей фичи (`git checkout -b feature/amazing-feature`)
3. Закоммить изменения (`git commit -m 'Add amazing feature'`)
4. Запушь ветку (`git push origin feature/amazing-feature`)
5. Открой Pull Request

Перед этим прочитай [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 Лицензия

Распространяется под лицензией MIT. Подробности в файле [LICENSE](LICENSE).

---

## ⚠️ Дисклеймер

Задания парсятся с [СдамГИА](https://ege.sdamgia.ru/) через неофициальный API ([`sdamgia-api`](https://github.com/anijackich/sdamgia-api)). Проект не аффилирован с СдамГИА, Яндексом или ФИПИ. Используй ответственно.

---

<div align="center">

Сделано с ❤️ для тех кто хочет сдать ЕГЭ а не просто подготовиться к нему

⭐ Поставь звезду если проект полезен

</div>
