import struct
from abc import abstractmethod
from pathlib import Path
from typing import ClassVar, Self

import numpy as np
from pydantic import BaseModel, ConfigDict

from app.models.service_grid_request import ServiceGridRequest
from app.models.service_point_response import ServicePointResponse


R = 6378137.0
_BASE_HEADER = "<4d2i"   # min_x, max_x, min_y, max_y, nx, ny

class GridBaseModel(BaseModel):
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

    # формат хвоста заголовка после общей части; задаёт слой
    _EXTRA_FORMAT: ClassVar[str]

    # --- загрузка ---

    @classmethod
    def load(cls, path: Path) -> Self:
        with np.load(path) as data:
            kwargs = {
                name: (data[name].item() if data[name].ndim == 0 else data[name])
                for name in cls.model_fields
            }
        return cls(**kwargs)

    # --- геометрия ---

    @staticmethod
    def _mercator_to_lon(x: np.ndarray) -> np.ndarray:
        return np.degrees(x / R)

    @staticmethod
    def _mercator_to_lat(y: np.ndarray) -> np.ndarray:
        return np.degrees(2.0 * np.arctan(np.exp(y / R)) - np.pi / 2.0)

    def _request_coords(self, request: "ServiceGridRequest") -> tuple[np.ndarray, np.ndarray]:
        """Координаты пикселей запроса -> дробные индексы в сетке (строка 0 = max_lat)."""
        x = np.linspace(request.min_x, request.max_x, request.nx, dtype=np.float32)
        y = np.linspace(request.min_y, request.max_y, request.ny, dtype=np.float32)
        mx, my = np.meshgrid(x, y)
        lon = self._mercator_to_lon(mx)
        lat = self._mercator_to_lat(my)
        return (lon - self.min_lon) / self.dx, (self.max_lat - lat) / self.dy

    def _interpolate(self, field: np.ndarray, fx: np.ndarray, fy: np.ndarray) -> np.ndarray:
        fx0, fy0 = np.floor(fx), np.floor(fy)
        tx, ty = fx - fx0, fy - fy0              # дробная часть до clip

        ix0 = np.clip(fx0.astype(np.int32), 0, self.nx - 1)
        iy0 = np.clip(fy0.astype(np.int32), 0, self.ny - 1)
        ix1 = np.clip(ix0 + 1, 0, self.nx - 1)
        iy1 = np.clip(iy0 + 1, 0, self.ny - 1)

        return (
            field[iy0, ix0] * (1.0 - tx) * (1.0 - ty)
            + field[iy0, ix1] * tx * (1.0 - ty)
            + field[iy1, ix0] * (1.0 - tx) * ty
            + field[iy1, ix1] * tx * ty
        ).astype(np.float32)

    def _sample_scalar(self, field: np.ndarray, lon: float, lat: float) -> float | None:
        """Значение поля в точке; None, если точка вне сетки или там NaN."""
        fx = np.asarray((lon - self.min_lon) / self.dx)
        fy = np.asarray((self.max_lat - lat) / self.dy)
        if not (0 <= fx <= self.nx - 1 and 0 <= fy <= self.ny - 1):
            return None
        value = float(self._interpolate(field, fx, fy))
        return None if np.isnan(value) else value

    # --- бинарный тайл ---

    def resample_binary(self, request: ServiceGridRequest) -> bytes:
        fx, fy = self._request_coords(request)
        header = struct.pack(
            _BASE_HEADER + self._EXTRA_FORMAT.lstrip("<"),
            float(request.min_x), float(request.max_x),
            float(request.min_y), float(request.max_y),
            int(request.nx), int(request.ny),
            *self._header_extra(),
        )
        return header + self._encode_payload(fx, fy)

    # --- квантование (общие функции) ---

    @staticmethod
    def quantize_int16(field: np.ndarray, scale_max: float, nodata: int = -32768) -> np.ndarray:
        """Симметричный диапазон ±scale_max -> int16; NaN -> nodata."""
        nan = np.isnan(field)
        q = np.clip(np.round(np.nan_to_num(field) * (32767 / scale_max)), -32767, 32767).astype("<i2")
        q[nan] = nodata
        return q

    @staticmethod
    def quantize_uint16(field: np.ndarray, vmin: float, vmax: float, nodata: int = 65535) -> np.ndarray:
        """Диапазон [vmin, vmax] -> uint16 0..65534; NaN -> nodata."""
        nan = np.isnan(field)
        scale = 65534 / (vmax - vmin)
        q = np.round((np.nan_to_num(field, nan=vmin) - vmin) * scale)
        q = np.clip(q, 0, 65534).astype("<u2")
        q[nan] = nodata
        return q

    @abstractmethod
    def _header_extra(self) -> tuple: ...

    @abstractmethod
    def _encode_payload(self, fx: np.ndarray, fy: np.ndarray) -> bytes: ...

    @abstractmethod
    def sample_point(self, lon: float, lat: float) -> ServicePointResponse: ...