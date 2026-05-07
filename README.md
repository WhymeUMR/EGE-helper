# EGE Helper Bot

Telegram-бот помощник для подготовки к ЕГЭ на Python + aiogram.

## Что уже подключено
- `aiogram` (актуальная версия из PyPI при установке)
- `Redis` для быстрого состояния/счетчиков
- `PostgreSQL` для основной базы данных
- `SQLAlchemy` + `asyncpg`

## Быстрый старт

1. Скопируй пример переменных окружения:
```bash
cp .env.example .env
```

2. Запусти всё в Docker (бот + PostgreSQL + Redis):
```bash
docker compose up -d
```

3. Посмотри логи бота:
```bash
docker compose logs -f bot
```

## Локальный запуск бота (без Docker для Python)

Если хочешь запускать сам бот локально, а БД и Redis оставить в Docker:

1. Подними инфраструктуру:
```bash
docker compose up -d postgres redis
```

2. Создай виртуальное окружение и установи зависимости:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

3. Запусти бота:
```bash
python -m bot.main
```

## 📁 Структура проекта
```text
.
├── .dockerignore
├── .env.example
├── CONTRIBUTING.md
├── docker-compose.yml
├── Dockerfile
├── LICENSE
├── pyproject.toml
├── README.md
└── src/
    └── bot/
        ├── __init__.py
        ├── config.py
        ├── main.py
        ├── middlewares.py
        ├── db/
        │   ├── __init__.py
        │   ├── postgres.py
        │   └── redis_client.py
        ├── handlers/
        │   ├── __init__.py
        │   └── start.py
        ├── keyboards/
        │   └── __init__.py
        └── services/
            └── __init__.py
```
