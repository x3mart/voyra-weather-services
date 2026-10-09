from pydantic import BaseModel

from app.pressure.models.pressure_point_response import PressurePointResponse
from app.temperature.models.temperature_point_response import TemperaturePointResponse
from app.wave.models.wave_point_response import WavePointResponse
from app.wind.models.wind_point_response import WindPointResponse


class AllServicesPointResponse(BaseModel):
    wave: WavePointResponse | None
    wind: WindPointResponse | None
    pressure: PressurePointResponse | None
    temperature: TemperaturePointResponse | None