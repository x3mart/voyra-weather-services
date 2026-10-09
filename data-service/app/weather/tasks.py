import asyncio
import logging
from datetime import date
import aiohttp

from app.downloader import download_grib
from app.weather.pressure.processor import process_pressure
from app.weather.temperature.processor import process_temperature
from app.weather.wind.processor import process_wind
from app.weather.utils import build_weather_url
from config import DATA_FOLDER, NPZ_TMP_FOLDER, WIND_NPZ_FILENAME

logger = logging.getLogger(__name__)


async def process_weather_task(
    session: aiohttp.ClientSession, forecast_date: date, cycle: str
) -> bool:
    url = build_weather_url(forecast_date, cycle)
    grib_path = await download_grib(session, url)
    if grib_path is None:
        return False

    try:
        forecast = forecast_date.strftime("%Y-%m-%d")

        results = await asyncio.gather(
            asyncio.to_thread(process_wind, grib_path, forecast, cycle),
            asyncio.to_thread(process_pressure, grib_path, forecast, cycle),
            asyncio.to_thread(process_temperature, grib_path, forecast, cycle),
            return_exceptions=True,
        )
        names = ("wind", "pressure", "temperature")
        for name, res in zip(names, results):
            if isinstance(res, BaseException):
                logger.error("Ошибка в %s", name, exc_info=res)
        return all(r is True for r in results)
    finally:
        grib_path.unlink(missing_ok=True)
