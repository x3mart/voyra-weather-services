from typing import ClassVar
import numpy as np

from app.wave.models.wave_point_response import WavePointResponse
from app.models.grid_base_model import GridBaseModel

# Формат совпадает с тем, что разбирает WaveGridModel.fromBytes во Flutter:
# заголовок "<4d2i2f" (48 байт), затем три блока int16 строго в порядке angle, swh, perpw.
SWH_MAX = 20.0       # м, экстремальный шторм
PERPW_MAX = 30.0     # с

_TWO_PI = 2.0 * np.pi
_LAND = -32768       # маркер «нет данных» (суша) во всех трёх блоках


class WaveGrid(GridBaseModel):
    _EXTRA_FORMAT: ClassVar[str] = "2f"   # swh_max, perpw_max

    swh: np.ndarray      # м
    perpw: np.ndarray    # с
    dir_u: np.ndarray    # sin(направление движения), безразмерное
    dir_v: np.ndarray    # cos(направление движения)

    @staticmethod
    def _quantize_angle(dir_u: np.ndarray, dir_v: np.ndarray) -> np.ndarray:
        """unit-вектор (куда идут волны) -> угол 0..2π от севера по часовой -> int16 на полный круг."""
        angle = np.arctan2(dir_u, dir_v) % _TWO_PI
        q = np.round(angle / _TWO_PI * 65535.0 - 32768.0)
        q = np.clip(np.nan_to_num(q, nan=0.0), -32767, 32767).astype("<i2")
        q[np.isnan(dir_u) | np.isnan(dir_v)] = _LAND
        return q

    def _header_extra(self) -> tuple:
        return (SWH_MAX, PERPW_MAX)

    def _encode_payload(self, fx, fy) -> bytes:
        dir_u = self._interpolate(self.dir_u, fx, fy)
        dir_v = self._interpolate(self.dir_v, fx, fy)
        swh = self._interpolate(self.swh, fx, fy)
        per = self._interpolate(self.perpw, fx, fy)

        # порядок блоков важен: angle, swh, perpw
        return (
            self._quantize_angle(dir_u, dir_v).ravel().tobytes()
            + self.quantize_int16(swh, SWH_MAX).ravel().tobytes()
            + self.quantize_int16(per, PERPW_MAX).ravel().tobytes()
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