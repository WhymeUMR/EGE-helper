"""Собираем все feature-роутеры в один top-level router

main.py подключает только этот собранный router в диспетчер.

Порядок include важен только при пересечении фильтров внутри одного
роутера. Четыре фичи ниже владеют непересекающимися namespace'ами
колбэков (onb:* / onb:resume:* / onb:reset:* / menu:*), так что
порядок здесь чисто косметический.
"""

from aiogram import Router

from .menu import router as menu_router
from .onboarding import router as onboarding_router
from .reset import router as reset_router
from .resume import router as resume_router

router = Router()
router.include_router(onboarding_router)
router.include_router(resume_router)
router.include_router(reset_router)
router.include_router(menu_router)
