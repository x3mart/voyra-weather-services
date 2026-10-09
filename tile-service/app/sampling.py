"""Ресемплинг полей Grid в пиксели тайла с маскированной билинейной интерполяцией."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import map_coordinates #type: ignore

from app.geometry import TILE_SIZE_PX, grid_row_col, mercator_to_lonlat
from app.models import Grid


def sample_field(
    grid: Grid,
    field: np.ndarray,
    min_x: float, min_y: float, max_x: float, max_y: float,
    size: int = TILE_SIZE_PX,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Билинейно ресемплит поле сетки (регулярное по lon/lat) в пиксели тайла (Mercator).

    Использует МАСКИРОВАННУЮ интерполяцию: NaN-ячейки (суша) не "протравливают"
    соседние валидные ячейки через билинейное усреднение. Вместо этого возвращается
    отдельно (a) значение, посчитанное только по валидным соседям, и (b) доля валидных
    соседей в окне интерполяции этого пикселя (0..1) — её удобно использовать как
    мягкий альфа-канал у берега вместо жёсткого обреза.
    """
    xs = np.linspace(min_x, max_x, size, endpoint=False) + (max_x - min_x) / size / 2
    ys = np.linspace(max_y, min_y, size, endpoint=False) - (max_y - min_y) / size / 2
    xx, yy = np.meshgrid(xs, ys)

    lon, lat = mercator_to_lonlat(xx, yy)
    row, col = grid_row_col(grid, lon, lat)

    valid_mask = (~np.isnan(field)).astype(np.float32)
    field_filled = np.nan_to_num(field, nan=0.0).astype(np.float32)

    weighted_sum = map_coordinates(field_filled, [row, col], order=1, mode="constant", cval=0.0)
    coverage = map_coordinates(valid_mask, [row, col], order=1, mode="constant", cval=0.0)

    with np.errstate(invalid="ignore", divide="ignore"):
        values = weighted_sum / coverage
    values[coverage <= 1e-6] = np.nan  # совсем нет валидных данных рядом (суша/вне сетки)

    return values, coverage
