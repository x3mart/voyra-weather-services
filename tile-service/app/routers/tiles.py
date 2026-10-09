"""HTTP-роуты: отдача тайлов."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fastapi.concurrency import run_in_threadpool

from config import HTTP_TILE_CACHE_MAX_AGE_SECONDS, LAYER_CONFIG
from app.rendering import TILE_CACHE, render_tile
from app.store import store


router = APIRouter()


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
async def get_tile(layer: str, z: int, x: int, y: int) -> Response:
    cfg = LAYER_CONFIG.get(layer)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Unknown layer '{layer}'")

    # версия берётся по ИСТОЧНИКУ слоя (а не по имени слоя): так инвалидируются
    # все слои источника сразу, включая стрелки wave_dir
    cache_key = (layer, store.version(cfg["source"]), z, x, y)
    png_bytes = TILE_CACHE.get(cache_key)
    if png_bytes is None:
        png_bytes = await run_in_threadpool(render_tile, layer, z, x, y)
        TILE_CACHE[cache_key] = png_bytes

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": f"public, max-age={HTTP_TILE_CACHE_MAX_AGE_SECONDS}"},
    )
