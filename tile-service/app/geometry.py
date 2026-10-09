"""Геометрия: Web Mercator <-> lon/lat, границы XYZ-тайлов, перевод в индексы сетки."""

from __future__ import annotations

import numpy as np

from app.models import Grid

EARTH_RADIUS = 6378137.0            # сферическая аппроксимация WGS84 (как у Mapbox)
EARTH_HALF = 20037508.342789244     # половина периметра Web Mercator, м
WORLD_SIZE = 2 * EARTH_HALF
TILE_SIZE_PX = 256


def tile_bounds_mercator(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """Границы XYZ-тайла в метрах Web Mercator (EPSG:3857)."""
    n = 2 ** z
    size = WORLD_SIZE / n
    min_x = -EARTH_HALF + x * size
    max_x = min_x + size
    max_y = EARTH_HALF - y * size
    min_y = max_y - size
    return min_x, min_y, max_x, max_y


def mercator_to_lonlat(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lon = np.degrees(x / EARTH_RADIUS)
    lat = np.degrees(2 * np.arctan(np.exp(y / EARTH_RADIUS)) - np.pi / 2)
    return lon, lat


def bbox_overlaps(grid: Grid, min_x: float, min_y: float, max_x: float, max_y: float) -> bool:
    """Пересекается ли тайл (метры Mercator) с экстентом сетки (lon/lat)."""
    lon0, lat0 = mercator_to_lonlat(min_x, min_y)
    lon1, lat1 = mercator_to_lonlat(max_x, max_y)
    return not (
        lon1 < grid.min_lon or lon0 > grid.max_lon
        or lat1 < grid.min_lat or lat0 > grid.max_lat
    )


def grid_row_col(grid: Grid, lon: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Единая точка перевода lon/lat -> дробные индексы (row, col) сетки Grid.

    ВАЖНО: и цветовые тайлы (sample_field), и стрелки (render_direction_tile)
    обязаны использовать именно эту функцию, а не пересчитывать row/col каждый
    своей копией — иначе при рассинхронизации формул слои начинают "плыть"
    относительно друг друга.
    """
    col = (lon - grid.min_lon) / grid.dx
    row = (grid.max_lat - lat) / grid.dy  # field[0] соответствует max_lat (заполнение сверху вниз)
    return row, col
