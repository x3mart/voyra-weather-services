"""Рендер стрелок направления волны (dir_u/dir_v) отдельным прозрачным слоем."""

from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates #type: ignore

from config import (
    ARROW_COLOR,
    ARROW_GRADIENT_START_RATIO,
    ARROW_HEAD_DEPTH_RATIO,
    ARROW_HEAD_HALF_HEIGHT_RATIO,
    ARROW_LENGTH_PX,
    ARROW_MAX_ALPHA,
    ARROW_MIN_COVERAGE,
    ARROW_SPACING_PX,
    ARROW_STROKE_RATIO,
    ARROW_SUPERSAMPLE,
)
from app.geometry import TILE_SIZE_PX, bbox_overlaps, grid_row_col, mercator_to_lonlat, tile_bounds_mercator
from app.models import Grid, WaveGrid
from app.tile_utils import TRANSPARENT_TILE


def _build_arrow_alpha_mask(length_px: float) -> Image.Image:
    """
    Строит МАСКУ стрелки — одноканальное изображение "L", значения которого
    станут будущей альфой: линия-хвост + открытый шеврон ">" на конце,
    с градиентом от 0 (у середины, см. ARROW_GRADIENT_START_RATIO) до
    ARROW_MAX_ALPHA (у кончика). Стрелка направлена вдоль +x (вправо).

    Цвет здесь вообще не участвует — он константа (ARROW_COLOR) и приклеивается
    отдельно уже после всех поворотов/масштабирований. Поэтому интерполяции
    (BICUBIC/LANCZOS) неоткуда подмешать в цвет ничего постороннего — работать
    приходится только с одним каналом, а не с RGBA, где цвет и альфа мешаются.
    """
    stroke_w = max(2, round(length_px * ARROW_STROKE_RATIO))
    head_depth = round(length_px * ARROW_HEAD_DEPTH_RATIO)
    head_half_h = round(length_px * ARROW_HEAD_HALF_HEIGHT_RATIO)
    pad = stroke_w  # запас под круглые "колпачки" на концах линий

    length_i = round(length_px)
    w = length_i + 2 * pad
    h = 2 * head_half_h + 2 * pad
    cy = h // 2
    tail_x = pad
    tip_x = pad + length_i

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    def cap(cx: float, cy_: float) -> None:
        r = stroke_w / 2
        draw.ellipse([cx - r, cy_ - r, cx + r, cy_ + r], fill=255)

    draw.line([(tail_x, cy), (tip_x, cy)], fill=255, width=stroke_w)
    cap(tail_x, cy)
    cap(tip_x, cy)

    head_x = tip_x - head_depth
    draw.line([(head_x, cy - head_half_h), (tip_x, cy)], fill=255, width=stroke_w)
    draw.line([(head_x, cy + head_half_h), (tip_x, cy)], fill=255, width=stroke_w)
    cap(head_x, cy - head_half_h)
    cap(head_x, cy + head_half_h)

    arr = np.array(mask).astype(np.float32)
    xs = np.arange(w, dtype=np.float32)
    grad_start_x = tail_x + (tip_x - tail_x) * ARROW_GRADIENT_START_RATIO
    grad = np.clip((xs - grad_start_x) / max(1.0, tip_x - grad_start_x), 0.0, 1.0) * ARROW_MAX_ALPHA
    arr = arr * (grad[np.newaxis, :] / 255.0)

    return Image.fromarray(arr.astype(np.uint8), mode="L")


def render_direction_tile(
    grid: Grid, dir_u: np.ndarray, dir_v: np.ndarray, z: int, x: int, y: int
) -> bytes:
    min_x, min_y, max_x, max_y = tile_bounds_mercator(z, x, y)

    if not bbox_overlaps(grid, min_x, min_y, max_x, max_y):
        return TRANSPARENT_TILE

    scale = ARROW_SUPERSAMPLE
    canvas_size = TILE_SIZE_PX * scale
    canvas_alpha = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
    sprite_mask = _build_arrow_alpha_mask(ARROW_LENGTH_PX * scale)

    n = max(1, TILE_SIZE_PX // ARROW_SPACING_PX)
    offset = ARROW_SPACING_PX / 2
    px = np.array([offset + i * ARROW_SPACING_PX for i in range(n)])

    xs_m = min_x + (px / TILE_SIZE_PX) * (max_x - min_x)
    ys_m = max_y - (px / TILE_SIZE_PX) * (max_y - min_y)
    xx_m, yy_m = np.meshgrid(xs_m, ys_m)
    lon, lat = mercator_to_lonlat(xx_m, yy_m)
    row, col = grid_row_col(grid, lon, lat)

    u = map_coordinates(np.nan_to_num(dir_u), [row, col], order=1, mode="constant", cval=0.0)
    v = map_coordinates(np.nan_to_num(dir_v), [row, col], order=1, mode="constant", cval=0.0)
    valid = (~np.isnan(dir_u)).astype(np.float32)
    coverage = map_coordinates(valid, [row, col], order=1, mode="constant", cval=0.0)

    for iy in range(n):
        for ix in range(n):
            if coverage[iy, ix] < ARROW_MIN_COVERAGE:
                continue
            uu, vv = float(u[iy, ix]), float(v[iy, ix])
            if uu == 0.0 and vv == 0.0:
                continue
            # bearing (по часовой от севера); если стрелки окажутся развёрнуты на 180° —
            # у вашей модели конвенция "направление ОТКУДА", тогда добавьте + math.pi
            bearing = math.atan2(uu, vv)

            # маска "смотрит" вправо (восток, bearing=90°) в исходном виде —
            # вращаем до нужного bearing. Знак подобран и проверен визуально
            # на тесте с известным направлением (см. test_direction.py).
            rotated = sprite_mask.rotate(90 - math.degrees(bearing), resample=Image.BICUBIC, expand=True, fillcolor=0) #type: ignore
            rotated_arr = np.clip(np.array(rotated), 0, ARROW_MAX_ALPHA).astype(np.uint8)  # BICUBIC может дать "звон" за пределы ARROW_MAX_ALPHA

            cx, cy = px[ix] * scale, px[iy] * scale
            paste_x = int(round(cx - rotated.width / 2))
            paste_y = int(round(cy - rotated.height / 2))

            # ручное наложение с обрезкой по границам канвы (спрайт у края тайла
            # может частично выходить за пределы) и объединением через максимум —
            # на случай если соседние стрелки всё же слегка перекроются
            src_x0, src_y0 = max(0, -paste_x), max(0, -paste_y)
            dst_x0, dst_y0 = max(0, paste_x), max(0, paste_y)
            dst_x1 = min(canvas_size, paste_x + rotated.width)
            dst_y1 = min(canvas_size, paste_y + rotated.height)
            if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
                continue
            src_x1 = src_x0 + (dst_x1 - dst_x0)
            src_y1 = src_y0 + (dst_y1 - dst_y0)

            region = canvas_alpha[dst_y0:dst_y1, dst_x0:dst_x1]
            np.maximum(region, rotated_arr[src_y0:src_y1, src_x0:src_x1], out=region)

    # финальный downsample — интерполируем только альфу (один канал), поэтому
    # цвету здесь неоткуда "потускнеть" или посереть на полупрозрачных краях
    final_alpha_img = Image.fromarray(canvas_alpha, mode="L").resize(
        (TILE_SIZE_PX, TILE_SIZE_PX), Image.LANCZOS #type: ignore
    )
    final_alpha = np.clip(np.array(final_alpha_img), 0, ARROW_MAX_ALPHA).astype(np.uint8)

    rgba = np.empty((TILE_SIZE_PX, TILE_SIZE_PX, 4), dtype=np.uint8)
    rgba[..., :3] = ARROW_COLOR
    rgba[..., 3] = final_alpha

    img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
