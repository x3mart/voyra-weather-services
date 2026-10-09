import asyncio
import logging
from datetime import date
from pathlib import Path

import aiohttp

from app.downloader import download_grib
from app.wave.processor import process_wave_grid
from app.wave.utils import build_wave_url
from config import DATA_FOLDER, NPZ_TMP_FOLDER, WAVE_NPZ_FILENAME

logger = logging.getLogger(__name__)


def _process_wave(grib_path: Path, forecast: str, cycle: str) -> bool:
    wave_grid = process_wave_grid(grib_path, forecast, cycle)
    if wave_grid is None:
        logger.warning("Не удалось обработать WaveGrid")
        return False

    output_path = NPZ_TMP_FOLDER / WAVE_NPZ_FILENAME
    wave_grid.save_npz(output_path)
    output_path.replace(DATA_FOLDER / WAVE_NPZ_FILENAME)
    return True


async def process_wave_task(
    session: aiohttp.ClientSession, forecast_date: date, cycle: str
) -> bool:
    url = build_wave_url(forecast_date, cycle)
    grib_path = await download_grib(session, url)
    if grib_path is None:
        return False

    try:
        forecast = forecast_date.strftime("%Y-%m-%d")
        return await asyncio.to_thread(_process_wave, grib_path, forecast, cycle)
    finally:
        grib_path.unlink(missing_ok=True)
