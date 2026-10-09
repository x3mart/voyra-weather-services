from typing import ClassVar
import numpy as np

from app.models.grid_base_model import GridBaseModel
from app.temperature.models.temperature_point_response import TemperaturePointResponse


TEMP_SCALE_MAX = 100.0

class TemperatureGrid(GridBaseModel):
    _EXTRA_FORMAT: ClassVar[str] = "f"

    t2m: np.ndarray   # °C

    def _header_extra(self) -> tuple:
        return (TEMP_SCALE_MAX,)

    def _encode_payload(self, fx, fy) -> bytes:
        return self.quantize_int16(self._interpolate(self.t2m, fx, fy), TEMP_SCALE_MAX).ravel().tobytes()

    def sample_point(self, lon: float, lat: float) -> TemperaturePointResponse:
        return TemperaturePointResponse(t2m=self._sample_scalar(self.t2m, lon, lat))