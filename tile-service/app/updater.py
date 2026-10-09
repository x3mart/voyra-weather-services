"""Фоновая проверка новых данных прогноза и их подгрузка в GridStore."""

from __future__ import annotations

import asyncio
import json
import logging

from config import CURRENT_CYCLE_JSON_PATH, DATA_DIR, POLL_INTERVAL_SECONDS, SOURCES
from app.store import store

logger = logging.getLogger(__name__)


def _read_current_cycle() -> dict | None:
    if not CURRENT_CYCLE_JSON_PATH.exists():
        logger.info("Не найден JSON")
        return None
    with open(CURRENT_CYCLE_JSON_PATH, "rb") as f:
        return json.load(f)


def _is_update_needed(source: str, current: dict) -> bool:
    grid = store.get_optional(source)
    return (
        grid is None
        or current["cycle"] != grid.cycle
        or current["forecast"] != grid.cycle_date
    )


async def reload_source(source: str) -> None:
    path = DATA_DIR / SOURCES[source].filename
    if not path.exists():
        logger.warning("%s: файл %s не найден", source, path)
        return

    # np.load блокирующий — уводим в отдельный поток, чтобы не стопорить event loop
    await asyncio.to_thread(store.load, source, path)

    grid = store.get_optional(source)
    if grid is not None:
        logger.info("%s: сетка обновлена cycle=%s date=%s", source, grid.cycle, grid.cycle_date)


async def poll_for_updates() -> None:
    """
    Бесконечный цикл: раз в POLL_INTERVAL_SECONDS проверяет current_cycle.json
    и перегружает те источники, у которых сетка не соответствует текущему циклу.

    Каждый источник обновляется независимо: ошибка в одном (битый npz, нет файла)
    не мешает остальным и не убивает цикл опроса.
    """
    while True:
        try:
            current = _read_current_cycle()
        except Exception:
            logger.exception("Ошибка чтения current_cycle.json")
            current = None

        if current is not None:
            for source in SOURCES:
                try:
                    if _is_update_needed(source, current):
                        await reload_source(source)
                except Exception:
                    logger.exception("%s: ошибка обновления сетки", source)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
