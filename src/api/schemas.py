"""Response-схемы. Внутренний автоинкрементный `id` наружу не отдаём —
снаружи задача адресуется парой (subject, sdamgia_id)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubjectInfo(BaseModel):
    key: str
    label: str
    problems_count: int
    topics_count: int


class CategoryInfo(BaseModel):
    category_id: str | None
    category_name: str | None
    problems_count: int


class TopicInfo(BaseModel):
    topic_number: str | None
    topic_name: str | None
    problems_count: int
    categories: list[CategoryInfo]


class ProblemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject: str
    sdamgia_id: str
    topic_number: str | None
    topic_name: str | None
    category_id: str | None
    category_name: str | None
    condition_text: str | None
    condition_images: list[str]
    solution_text: str | None
    solution_images: list[str]
    answer: str | None
    analogs: list[str]
    url: str | None
    created_at: datetime
    updated_at: datetime


class ProblemsPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ProblemOut]
