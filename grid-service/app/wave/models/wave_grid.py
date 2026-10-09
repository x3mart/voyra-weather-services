from typing import ClassVar
import numpy as np

from app.wave.models.wave_point_response import WavePointResponse
from app.models.grid_base_model import GridBaseModel

SWH_MAX = 30.0       # м, с запасом под экстремальные штормы
PERPW_MAX = 30.0     # с


class WaveGrid(GridBaseModel):
    _EXTRA_FORMAT: ClassVar[str] = "2f"   # swh_max, perpw_max

    swh: np.ndarray      # м
    perpw: np.ndarray    # с
    dir_u: np.ndarray    # sin(направление движения), безразмерное
    dir_v: np.ndarray    # cos(направление движения)

    def _header_extra(self) -> tuple:
        return (SWH_MAX, PERPW_MAX)

    def _encode_payload(self, fx, fy) -> bytes:
        swh = self.quantize_uint16(self._interpolate(self.swh, fx, fy), 0.0, SWH_MAX)
        per = self.quantize_uint16(self._interpolate(self.perpw, fx, fy), 0.0, PERPW_MAX)
        du = self.quantize_int16(self._interpolate(self.dir_u, fx, fy), 1.0)
        dv = self.quantize_int16(self._interpolate(self.dir_v, fx, fy), 1.0)
        return (
            swh.ravel().tobytes()
            + per.ravel().tobytes()
            + du.ravel().tobytes()
            + dv.ravel().tobytes()
        )

    def sample_point(self, lon: float, lat: float) -> WavePointResponse:
        h = self._sample_scalar(self.swh, lon, lat)
        p = self._sample_scalar(self.perpw, lon, lat)
        u = self._sample_scalar(self.dir_u, lon, lat)
        v = self._sample_scalar(self.dir_v, lon, lat)
        if None in (h, p, u, v):
            return WavePointResponse(swh=None, perpw=None, dir_deg=None)

        # (u, v) направлен туда, куда идут волны; 
        deg = float(np.degrees(np.arctan2(u, v)) % 360) #type: ignore
        return WavePointResponse(swh=h, perpw=p, dir_deg=deg)