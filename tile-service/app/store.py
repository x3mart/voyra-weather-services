"""Хранилище загруженных сеток в памяти + версии для инвалидации кэша тайлов."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from fastapi import HTTPException

from config import SOURCES
from app.models import Grid


@dataclass(frozen=True)
class Entry:
    """Всё, что относится к одному источнику; подменяется целиком одним присваиванием."""

    grid: Grid
    derived: dict[str, np.ndarray]
    version: str

    def field(self, name: str) -> np.ndarray:
        if name in self.derived:
            return self.derived[name]
        return getattr(self.grid, name)


class GridStore:
    """Держит актуальные сетки по источникам (wave, wind, ...) + версии цикла."""

    def __init__(self) -> None:
        self._entries: dict[str, Entry] = {}

    def load(self, source: str, path: Path) -> None:
        grid = SOURCES[source].grid_cls.load_npz(path)
        derived = grid.derived_fields()
        # cycle_date — это дата, а циклов в сутки несколько, поэтому версия = дата + цикл
        version = f"{grid.cycle_date}-{grid.cycle}"
        # присваивание ключа словаря атомарно: запрос видит либо старый Entry целиком, либо новый
        self._entries[source] = Entry(grid, derived, version)

    def entry(self, source: str) -> Entry:
        try:
            return self._entries[source]
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Source '{source}' not loaded")

    def get_optional(self, source: str) -> Grid | None:
        """Как entry().grid, но без исключения — для фонового поллера."""
        entry = self._entries.get(source)
        return entry.grid if entry else None

    def version(self, source: str) -> str:
        entry = self._entries.get(source)
        return entry.version if entry else "unknown"


store = GridStore()
