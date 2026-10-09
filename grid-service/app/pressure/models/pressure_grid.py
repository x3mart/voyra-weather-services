import struct
from pathlib import Path
from typing import ClassVar, Self
import numpy as np

from app.models.grid_base_model import GridBaseModel

from app.pressure.models.pressure_point_response import PressurePointResponse


PRESSURE_MIN, PRESSURE_MAX = 800.0, 1100.0

class PressureGrid(GridBaseModel):
    _EXTRA_FORMAT: ClassVar[str] = "2f"

    prmsl: np.ndarray   # гПа

    def _header_extra(self) -> tuple:
        return (PRESSURE_MIN, PRESSURE_MAX)

    def _encode_payload(self, fx, fy) -> bytes:
        return self.quantize_uint16(self._interpolate(self.prmsl, fx, fy), PRESSURE_MIN, PRESSURE_MAX).ravel().tobytes()

    def sample_point(self, lon: float, lat: float) -> PressurePointResponse:
        return PressurePointResponse(prmsl=self._sample_scalar(self.prmsl, lon, lat))