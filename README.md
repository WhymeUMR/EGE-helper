<div align="center">

<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/aiogram-3.27-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" />
<img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
<img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" />

# 🎯 EGE Helper

**Персональный Telegram-бот для подготовки к ЕГЭ на основе SM-2**

*Умное расписание · Автопроверка ответов · Аналитика прогресса · Open Source*

[Сообщить о баге](../../issues) · [Предложить фичу](../../issues)

</div>

---

> ⚠️ **Статус:** ранний этап разработки (`v0.2`). Работает онбординг, профиль с обратным отсчётом до ЕГЭ, главное меню как дашборд, настройки, сброс. Поднят отдельный parser-сервис: тянет каталог задач СдамГИА в Postgres, поддерживает seed-импорт из GitHub Releases. Алгоритм SM-2 и MiniApp — следующие на очереди.

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
git clone https://github.com/yourusername/EGE-helper.git
cd EGE-helper

# Создай .env по образцу ниже
cp .env.example .env
nano .env

# Запусти всё разом
docker compose up -d --build
```

После пересборки контейнера бот сам:
1. подключится к Postgres и применит `Base.metadata.create_all` (миграций пока нет);
2. проверит Redis;
3. начнёт `polling`.

Логи смотри командой:
```bash
docker compose logs -f bot
```

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

### v0.2 — Контент 🚧

- [x] Парсинг заданий через [`sdamgia-api`](https://github.com/anijackich/sdamgia-api) — отдельный async-сервис
- [x] Кэширование задач в собственной БД (схема + индексы, дедуп по `sdamgia_id`)
- [x] Seed-дампы на GitHub Releases с валидацией через CI
- [ ] Фильтрация по номеру и типу задания
- [ ] Расписание (часов в неделю → задач в день, ~17 мин на задачу)
- [ ] MiniApp для удобного решения задач прямо в Telegram
- [ ] Экран «📚 Материалы» — конспекты, формулы, шпаргалки
- [ ] Калибровка — опциональный пробный вариант на старте
- [ ] Полный пробный вариант ЕГЭ за раз (с общим таймером)

### v0.3 — SM-2 и аналитика

- [ ] Реализация алгоритма SM-2 (интервалы повторения по типам задач)
- [ ] Автопроверка ответов части 1
- [ ] Самооценка части 2 (с показом эталонного решения)
- [ ] Трекинг времени решения каждой задачи
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
