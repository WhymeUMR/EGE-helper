from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from redis.asyncio import Redis

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, redis: Redis) -> None:
    user_id = message.from_user.id
    key = f"user:{user_id}:starts"

    starts_count = await redis.incr(key)
    if starts_count == 1:
        await redis.expire(key, 60 * 60 * 24)

    await message.answer(
        "Привет! Я твой помощник по ЕГЭ.\n"
        f"Ты запускал меня {starts_count} раз(а) за последние 24 часа.\n\n"
        "Что делаем дальше: математика, русский или другой предмет?"
    )


@router.message(F.text)
async def echo_text(message: Message) -> None:
    await message.answer(
        "Я пока в базовой версии. Напиши, с каким предметом ЕГЭ помочь, "
        "и я подскажу следующий шаг."
    )
