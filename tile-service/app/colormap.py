"""Построение цветовых LUT и раскраска значений с мягким альфа-каналом у берега."""

from __future__ import annotations

import numpy as np


def hex_to_rgb(hex_color: str) -> np.ndarray:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Некорректный hex-цвет: {hex_color!r}")
    return np.array([
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    ], dtype=np.float32)


def build_lut(
    stops: list | tuple | None = None,
    n: int = 256,
    vmin: float | None = None,
    vmax: float | None = None,
) -> np.ndarray:
    """Строит RGBA LUT.

    stops — один из двух форматов:
      * ["#hex", "#hex", ...]            — цвета равномерно по шкале vmin..vmax;
      * [(значение, "#hex"), ...]        — цвет привязан к конкретному значению
                                           (нужны vmin и vmax), напр. 0 °C или 1013 гПа.
    """
    if stops is None:
        stops = ["#2CC2F6", "#370045"]

    if isinstance(stops[0], str):
        colors = np.array([hex_to_rgb(c) for c in stops], dtype=np.float32)
        positions = np.linspace(0.0, 1.0, len(colors))
    else:
        if vmin is None or vmax is None:
            raise ValueError("Для стопов (значение, цвет) нужны vmin и vmax")
        pairs = sorted(stops, key=lambda p: p[0])
        colors = np.array([hex_to_rgb(c) for _, c in pairs], dtype=np.float32)
        values = np.array([v for v, _ in pairs], dtype=np.float32)
        positions = (values - vmin) / (vmax - vmin)

    ramp = np.linspace(0.0, 1.0, n)
    lut = np.zeros((n, 4), dtype=np.float32)

    for ch in range(3):
        lut[:, ch] = np.interp(ramp, positions, colors[:, ch])

    lut[:, 3] = 255.0
    return lut.astype(np.uint8)


def apply_colormap(
    values: np.ndarray,
    coverage: np.ndarray,
    vmin: float, vmax: float,
    lut: np.ndarray,
    min_coverage: float = 0.15,
) -> np.ndarray:
    """
    Раскрашивает значения по LUT; альфа-канал берётся из coverage (доля валидных
    соседей при ресемплинге), а не 0/255 — это даёт плавное затухание к берегу
    вместо жёсткой ступенчатой границы. min_coverage отсекает пиксели, где данных
    почти совсем нет (глубоко на суше), чтобы не было полупрозрачной "грязи"
    далеко от воды.
    """
    norm = np.clip((values - vmin) / (vmax - vmin), 0, 1)
    norm = np.nan_to_num(norm, nan=0.0)
    idx = (norm * (len(lut) - 1)).astype(np.uint8)
    rgba = lut[idx].astype(np.float32)

    alpha = np.clip(coverage, 0.0, 1.0) * 255.0
    alpha[coverage < min_coverage] = 0.0
    rgba[..., 3] = alpha
    rgba[np.isnan(values)] = [0, 0, 0, 0]

    return rgba.astype(np.uint8)
