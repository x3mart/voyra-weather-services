"""Рендер тайла (диспетчер color/direction) + in-memory кэш готовых PNG."""

from __future__ import annotations

import io

from cachetools import LRUCache
from PIL import Image

from app.arrows import render_direction_tile
from app.colormap import apply_colormap
from config import LAYER_CONFIG, LUTS, TILE_CACHE_MAXSIZE
from app.geometry import bbox_overlaps, tile_bounds_mercator
from app.sampling import sample_field
from app.store import store
from app.tile_utils import TRANSPARENT_TILE

TILE_CACHE: LRUCache = LRUCache(maxsize=TILE_CACHE_MAXSIZE)


def render_tile(layer: str, z: int, x: int, y: int) -> bytes:
    cfg = LAYER_CONFIG[layer]
    # Entry берём один раз: сетка и производные поля гарантированно из одного цикла,
    # даже если во время рендера поллер подменит данные
    entry = store.entry(cfg["source"])
    grid = entry.grid

    if cfg["kind"] == "direction":
        return render_direction_tile(
            grid, entry.field(cfg["u"]), entry.field(cfg["v"]), z, x, y
        )

    min_x, min_y, max_x, max_y = tile_bounds_mercator(z, x, y)

    if not bbox_overlaps(grid, min_x, min_y, max_x, max_y):
        return TRANSPARENT_TILE

    values, coverage = sample_field(grid, entry.field(cfg["field"]), min_x, min_y, max_x, max_y)
    rgba = apply_colormap(values, coverage, cfg["vmin"], cfg["vmax"], LUTS[layer])

    img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
