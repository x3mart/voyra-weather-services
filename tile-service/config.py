"""Конфигурация приложения: источники данных (npz) и описание тайловых слоёв.

Терминология:
  * источник (source) — один npz-файл со своей моделью сетки: wave, wind, temperature, pressure;
  * слой (layer)      — то, что запрашивается в URL: /tiles/{layer}/{z}/{x}/{y}.png.
                        Один источник может питать несколько слоёв (у волн: swh, perpw, wave_dir).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.colormap import build_lut
from app.models import Grid, PressureGrid, TemperatureGrid, WaveGrid, WindGrid

# app/config.py -> app/ -> tiles-service/   (PROJECT_ROOT — корень сервиса, где лежит main.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "npz"
CURRENT_CYCLE_JSON_PATH = DATA_DIR / "current_cycle.json"  # поправьте имя под то, что реально пишет data-service
POLL_INTERVAL_SECONDS = 20 * 60  # раз в ~20 минут — в пределах требуемых 15-30

# Настройки рендера и кэша
TILE_CACHE_MAXSIZE = 20_000
HTTP_TILE_CACHE_MAX_AGE_SECONDS = 60

ARROW_SUPERSAMPLE = 4          # рендерим крупнее и уменьшаем — иначе линии выглядят "лесенкой"
ARROW_SPACING_PX = 40          # шаг сетки стрелок в пикселях финального тайла (256x256)
ARROW_LENGTH_PX = 25           # длина стрелки хвост-кончик, в пикселях финального тайла
ARROW_COLOR = (255, 255, 255)  # RGB заливки; альфа берётся из маски ниже
ARROW_MAX_ALPHA = 180          # альфа у кончика (0..255); у хвоста альфа всегда 0
ARROW_STROKE_RATIO = 0.06      # толщина линии относительно длины (~3/37, как в исходном SVG)
ARROW_HEAD_DEPTH_RATIO = 0.16  # длина "шеврона" относительно длины стрелки
ARROW_HEAD_HALF_HEIGHT_RATIO = 0.15  # раскрытие шеврона по вертикали
ARROW_GRADIENT_START_RATIO = 0.3     # доля длины от хвоста, где начинается рост альфы (0.5 = с середины)
ARROW_MIN_COVERAGE = 0.6       # не рисовать стрелку, если рядом мало валидных (не-суша) данных


# ---------------------------------------------------------------------------
# Источники данных
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceSpec:
    grid_cls: type[Grid]
    filename: str  # имя npz в DATA_DIR; должно совпадать с тем, под чем пишет data-service


SOURCES: dict[str, SourceSpec] = {
    "wave":        SourceSpec(WaveGrid,        "wave_data.npz"),
    "wind":        SourceSpec(WindGrid,        "wind_data.npz"),
    "temperature": SourceSpec(TemperatureGrid, "temperature_data.npz"),
    "pressure":    SourceSpec(PressureGrid,    "pressure_data.npz"),
}


# ---------------------------------------------------------------------------
# Слои
# ---------------------------------------------------------------------------
# "color"     — цветовая заливка по скалярному полю (field) источника (source)
# "direction" — стрелки по dir_u/dir_v источника wave
#
# cmap — либо список hex-цветов (равномерно по vmin..vmax),
#        либо список (значение, hex), если цвет нужно привязать к конкретному значению.
LAYER_CONFIG: dict[str, dict] = {
    # --- волны ---
    "swh": {
        "kind": "color", "source": "wave", "field": "swh", "vmin": 0.0, "vmax": 8.0,
        "cmap": ["#2ABFE8", "#1440D2", "#450AAA", "#82039C", "#5E003C"],
    },
    "perpw": {
        "kind": "color", "source": "wave", "field": "perpw", "vmin": 2.0, "vmax": 20.0,
        "cmap": ["#2CC2F6", "#370045"],
    },
    "wave_dir": {"kind": "direction", "source": "wave", "u": "dir_u", "v": "dir_v"},

    # --- ветер: цвет по скорости, м/с (стрелки не рисуем) ---
    "wind": {
        "kind": "color", "source": "wind", "field": "speed", "vmin": 0.0, "vmax": 35.0,
        "cmap": [(0, "#2A6FB0"), (5, "#3EC1D3"), (10, "#7BD389"), (15, "#F4E04D"),
                 (20, "#F28C28"), (25, "#D6372B"), (35, "#7A1E5A")],
    },

    # --- температура 2 м, °C (палитра-заготовка, подберите по карте) ---
    "temperature": {
        "kind": "color", "source": "temperature", "field": "t2m", "vmin": -40.0, "vmax": 40.0,
        "cmap": [(-40, "#7B2D8E"), (-20, "#2F4ACF"), (-5, "#2FA6E8"), (0, "#9BE3E0"),
                 (10, "#8BD36B"), (20, "#F4E04D"), (30, "#F28C28"), (40, "#C62828")],
    },

    # --- давление на уровне моря, гПа (палитра-заготовка) ---
    "pressure": {
        "kind": "color", "source": "pressure", "field": "prmsl", "vmin": 960.0, "vmax": 1060.0,
        "cmap": [(960, "#4A1486"), (985, "#2F5BD3"), (1000, "#4FB3E8"), (1013, "#F0F0F0"),
                 (1025, "#F2C94C"), (1040, "#E8743B"), (1060, "#9E1B32")],
    },
}

LUTS = {
    name: build_lut(cfg["cmap"], vmin=cfg["vmin"], vmax=cfg["vmax"])
    for name, cfg in LAYER_CONFIG.items()
    if cfg["kind"] == "color"
}
