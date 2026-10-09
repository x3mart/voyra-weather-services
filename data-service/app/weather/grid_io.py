from dataclasses import dataclass
from pathlib import Path
import logging

import numpy as np
import xarray as xr

from app.models import GridGeometry

logger = logging.getLogger(__name__)


def read_fields(
    path: Path,
    filter_keys: dict,
    names: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]] | None:
    """Читает переменные одной группы GRIB. None, если чего-то нет или форма не 2D."""
    with xr.open_dataset(
        path,
        engine="cfgrib",
        backend_kwargs={"filter_by_keys": filter_keys, "indexpath": ""},
    ) as ds:
        logger.debug("%s", ds.data_vars)
        for name in names:
            if name not in ds:
                logger.warning("%s не найдено в файле %s", name, path)
                return None
        fields = [ds[n].values.astype(np.float32, copy=False) for n in names]
        lats = ds.latitude.values
        lons = ds.longitude.values

    shapes = {f.shape for f in fields}
    if len(shapes) != 1 or fields[0].ndim != 2:
        logger.warning("Некорректные размеры полей %s: %s", names, shapes)
        return None
    return lats, lons, fields


def normalize_grid(
    lats: np.ndarray, lons: np.ndarray, fields: list[np.ndarray]
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], GridGeometry]:
    """Долгота -180..180 по возрастанию, широта с севера на юг, C-contiguous float32."""
    lons = ((lons + 180) % 360) - 180
    order = np.argsort(lons)
    lons = lons[order]
    fields = [f[:, order] for f in fields]

    if lats[0] < lats[-1]:
        lats = lats[::-1]
        fields = [f[::-1, :] for f in fields]

    fields = [np.ascontiguousarray(f, dtype=np.float32) for f in fields]

    dx = float(abs(lons[1] - lons[0]))
    dy = float(abs(lats[1] - lats[0]))
    if not np.allclose(np.diff(lons), dx, rtol=1e-3, atol=1e-3):
        raise ValueError("нерегулярная сетка по долготе")

    ny, nx = fields[0].shape
    geom = GridGeometry(
        min_lon=float(lons.min()), max_lon=float(lons.max()),
        min_lat=float(lats.min()), max_lat=float(lats.max()),
        dx=dx, dy=dy, nx=nx, ny=ny,
    )
    return lats, lons, fields, geom


def load_grid(path: Path, filter_keys: dict, names: tuple[str, ...]):
    """read_fields + normalize_grid. Возвращает (fields, geom) или None."""
    raw = read_fields(path, filter_keys, names)
    if raw is None:
        return None
    lats, lons, fields = raw
    _, _, fields, geom = normalize_grid(lats, lons, fields)
    return fields, geom