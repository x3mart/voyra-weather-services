"""
FastAPI-сервис генерации XYZ-тайлов для цветовой визуализации погодных данных
(волны, ветер, температура, давление) поверх Web Mercator карты — для
растровых слоёв в flutter-mapbox.

Запуск:
    uvicorn main:app --host 0.0.0.0 --port 8000

Тайлы:
    GET /tiles/{layer}/{z}/{x}/{y}.png
    layer: swh, perpw, wave_dir, wind, temperature, pressure   (см. LAYER_CONFIG)

Данные подхватываются автоматически: фоновый поллер раз в POLL_INTERVAL_SECONDS
сверяет current_cycle.json с загруженными сетками и перечитывает npz при новом цикле.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from config import SOURCES
from app.routers.tiles import router as tiles_router
from app.updater import poll_for_updates, reload_source

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,  # без force=True вызов часто оказывается no-op под uvicorn,
                 # если к этому моменту у root-логгера уже есть хендлеры
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    # начальную загрузку делаем здесь (а не полагаемся на первую итерацию поллера),
    # чтобы сервер не начал принимать запросы раньше, чем данные готовы;
    # ошибка одного источника не должна мешать запуску остальных
    for source in SOURCES:
        try:
            await reload_source(source)
        except Exception:
            logger.exception("%s: не удалось загрузить при старте", source)

    poll_task = asyncio.create_task(poll_for_updates())

    yield

    # --- shutdown ---
    poll_task.cancel()
    with suppress(asyncio.CancelledError):
        await poll_task


app = FastAPI(title="Weather Tile Server", lifespan=lifespan)
app.include_router(tiles_router)
