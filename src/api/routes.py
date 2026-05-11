"""Legacy роутер: оставлен для обратной совместимости со старыми клиентами,
которые ждут /api/v1/topics. /subjects и /problems перенесены в
api/routers/{catalog,problems}.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api import repository as repo
from api.auth import require_token
from api.deps import get_session
from api.schemas import CategoryInfo, TopicInfo

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_token)])


@router.get("/topics", response_model=list[TopicInfo], tags=["meta"])
async def list_topics(
    subject: str = Query(..., description="ключ предмета: math, russian, ..."),
    session: AsyncSession = Depends(get_session),
) -> list[TopicInfo]:
    """Какие номера заданий есть в предмете и какие типы внутри каждого.

    Эквивалентно /api/v1/subjects/{subject}/topic-map. Оставлено для бота,
    который ходит сюда исторически.
    """
    topics = await repo.list_topics(session, subject)
    return [
        TopicInfo(
            topic_number=t["topic_number"],
            topic_name=t["topic_name"],
            problems_count=t["problems_count"],
            categories=[CategoryInfo(**c) for c in t["categories"]],
        )
        for t in topics
    ]
