import asyncio
import json
from datetime import date, datetime, timedelta
from typing import Literal

import aiohttp

from app.wave.utils import build_wave_url
from app.weather.utils import build_weather_url
from config import (
    CURRENT_CYCLE_JSON_FILENAME,
    DATA_FOLDER,
    GFS_CYCLES,
    GRIB_TMP_FOLDER,
    INITIAL_CURRENT_CYCLE_JSON,
    NPZ_TMP_FOLDER,
)

Product = Literal["wave", "weather"]
Cycle = tuple[date | None, str | None]

async def is_grib_exists(
    session: aiohttp.ClientSession, url: str
) -> bool:
    timeout = aiohttp.ClientTimeout(total=10)
    async with session.head(url, timeout=timeout) as response:
        if response.status == 404:
            return False
        response.raise_for_status()
        return response.status == 200

def get_current_cycle() -> tuple[date | None, str | None]:
    with open(DATA_FOLDER / CURRENT_CYCLE_JSON_FILENAME, 'rb') as j:
        cycle_dict: dict = json.load(j)
        cycle_str_date = cycle_dict.get('forecast', None)
        if not cycle_str_date:
            return None, None
        cycle_date = date.fromisoformat(
            cycle_str_date
        )
        current_cycle = cycle_date, cycle_dict.get('cycle', None)
        return current_cycle


def get_current_product_cycles() -> dict[Product, Cycle]:
    with open(DATA_FOLDER / CURRENT_CYCLE_JSON_FILENAME, "rb") as cycle_file:
        cycle_data: dict = json.load(cycle_file)

    legacy_cycle = get_current_cycle_from_data(cycle_data)
    product_cycles: dict[Product, Cycle] = {}
    for product in ("wave", "weather"):
        saved_cycle = cycle_data.get(product)
        if saved_cycle is None:
            product_cycles[product] = legacy_cycle
            continue

        forecast = saved_cycle.get("forecast")
        cycle = saved_cycle.get("cycle")
        if not forecast or cycle is None:
            product_cycles[product] = legacy_cycle
            continue

        product_cycles[product] = (date.fromisoformat(forecast), cycle)

    return product_cycles


def get_current_cycle_from_data(cycle_data: dict) -> Cycle:
    forecast = cycle_data.get("forecast")
    if not forecast:
        return None, None
    return date.fromisoformat(forecast), cycle_data.get("cycle")

async def get_latest_product_cycle(
    session: aiohttp.ClientSession,
    product: Product,
) -> Cycle:
    build_product_url = build_wave_url if product == "wave" else build_weather_url
    today = date.today()
    for forecast_date in (today, today - timedelta(days=1)):
        for cycle in GFS_CYCLES:
            url = build_product_url(forecast_date, cycle)
            if await is_grib_exists(session, url):
                return forecast_date, cycle

    return None, None


async def get_latest_cycles(
    session: aiohttp.ClientSession,
) -> dict[Product, Cycle]:
    wave_cycle, weather_cycle = await asyncio.gather(
        get_latest_product_cycle(session, "wave"),
        get_latest_product_cycle(session, "weather"),
    )
    return {"wave": wave_cycle, "weather": weather_cycle}

def remove_temp_grib() -> None:
    for filename in GRIB_TMP_FOLDER.iterdir():
        path = GRIB_TMP_FOLDER / filename
        if path.exists():
            path.unlink()


def check_required_folders() -> None:
    # Создаём все папки с родителями
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    GRIB_TMP_FOLDER.mkdir(parents=True, exist_ok=True)
    NPZ_TMP_FOLDER.mkdir(parents=True, exist_ok=True)
    
    json_path = DATA_FOLDER / CURRENT_CYCLE_JSON_FILENAME
    if not json_path.exists():
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(INITIAL_CURRENT_CYCLE_JSON, f, indent=2)

def update_product_cycle_json(
    product: Product,
    forecast: str,
    cycle: str,
) -> None:
    json_path = DATA_FOLDER / CURRENT_CYCLE_JSON_FILENAME
    with open(json_path, "r", encoding="utf-8") as cycle_file:
        data: dict = json.load(cycle_file)

    data[product] = {"forecast": forecast, "cycle": cycle}
    wave_cycle = data.get("wave")
    weather_cycle = data.get("weather")
    if wave_cycle == weather_cycle:
        data["forecast"] = forecast
        data["cycle"] = cycle
        data["created"] = datetime.now().isoformat()
        data["model"] = "GFS"
        data["grid"] = "0.25"

    with open(json_path, "w", encoding="utf-8") as cycle_file:
        json.dump(data, cycle_file, indent=2)
    
