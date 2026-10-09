"""Общие утилиты для тайлов: заглушка для областей вне покрытия сетки."""

from __future__ import annotations

import io

from PIL import Image

from app.geometry import TILE_SIZE_PX


def _build_transparent_tile() -> bytes:
    img = Image.new("RGBA", (TILE_SIZE_PX, TILE_SIZE_PX), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


TRANSPARENT_TILE = _build_transparent_tile()
