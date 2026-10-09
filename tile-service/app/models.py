"""Модели сеток прогноза: общая основа Grid и по одному классу на источник данных."""

from __future__ import annotations

from pathlib import Path
from typing import Self

import numpy as np
from pydantic import BaseModel, ConfigDict


class Grid(BaseModel):
    """Регулярная lon/lat сетка + метаданные цикла прогноза.

    Строки массивов идут с севера на юг (field[0] соответствует max_lat),
    долгота возрастает от min_lon к max_lon.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float

    dx: float
    dy: float
    nx: int
    ny: int

    cycle: str
    cycle_date: str

    @classmethod
    def load_npz(cls, path: Path) -> Self:
        """Читает npz, созданный save_npz в data-service. Ключи = поля модели."""
        with np.load(path) as f:
            data = {
                name: (f[name].item() if f[name].ndim == 0 else f[name])
                for name in cls.model_fields
            }
        return cls(**_close_longitude_seam(data))

    def derived_fields(self) -> dict[str, np.ndarray]:
        """Производные поля; считаются один раз при загрузке сетки, а не на каждый тайл."""
        return {}


def _close_longitude_seam(data: dict) -> dict:
    """Для глобальной сетки добавляет замыкающий столбец (lon = min_lon + 360).

    Глобальная сетка 0.25° заканчивается на 179.75°, и без этого на высоких зумах
    между 179.75° и 180° интерполяция падает до нуля — получается прозрачная полоса
    на антимеридиане. Замыкающий столбец повторяет первый, шов закрывается для всех слоёв.
    """
    span = data["max_lon"] - data["min_lon"] + data["dx"]
    if abs(span - 360.0) > 1e-3:
        return data  # региональная сетка — ничего не делаем

    nx = data["nx"]
    out = dict(data)
    for name, value in data.items():
        if isinstance(value, np.ndarray) and value.ndim == 2 and value.shape[1] == nx:
            out[name] = np.concatenate([value, value[:, :1]], axis=1)
    out["max_lon"] = data["max_lon"] + data["dx"]
    out["nx"] = nx + 1
    return out




class WaveGrid(Grid):
    swh: np.ndarray       # значимая высота волны, м — для цвета
    dir_u: np.ndarray     # unit-вектор направления движения волн, x-компонента
    dir_v: np.ndarray     # unit-вектор направления движения волн, y-компонента
    perpw: np.ndarray     # период, с


class WindGrid(Grid):
    u: np.ndarray         # м/с, на восток
    v: np.ndarray         # м/с, на север

    def derived_fields(self) -> dict[str, np.ndarray]:
        return {"speed": np.hypot(self.u, self.v).astype(np.float32)}


class TemperatureGrid(Grid):
    t2m: np.ndarray       # температура на 2 м, °C


class PressureGrid(Grid):
    prmsl: np.ndarray     # давление на уровне моря, гПа
