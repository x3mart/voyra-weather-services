from typing import ClassVar
from charset_normalizer.api import logger
import numpy as np

from app.models.grid_base_model import GridBaseModel
from app.wind.models.wind_point_response import WindPointResponse


WIND_SPEED_SCALE_MAX = 100.0
COMPASS_16 = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


class WindGrid(GridBaseModel):
    _EXTRA_FORMAT: ClassVar[str] = "f"

    u: np.ndarray
    v: np.ndarray

    def _header_extra(self) -> tuple:
        return (WIND_SPEED_SCALE_MAX,)

    def _encode_payload(self, fx, fy) -> bytes:
        u = self.quantize_int16(self._interpolate(self.u, fx, fy), WIND_SPEED_SCALE_MAX)
        v = self.quantize_int16(self._interpolate(self.v, fx, fy), WIND_SPEED_SCALE_MAX)
        return u.ravel().tobytes() + v.ravel().tobytes()

    def sample_point(self, lon: float, lat: float) -> WindPointResponse:
        u = self._sample_scalar(self.u, lon, lat)
        v = self._sample_scalar(self.v, lon, lat)
        if u is None or v is None:
            return WindPointResponse(speed=None, direction=None)
        speed = float(np.hypot(u, v))
        deg = float(np.degrees(np.arctan2(-u, -v)) % 360)   # откуда дует
        return WindPointResponse(speed=speed, direction=COMPASS_16[int((deg + 11.25) // 22.5) % 16])
