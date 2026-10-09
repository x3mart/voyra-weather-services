from pathlib import Path
from attrs import asdict
import numpy as np
import xarray as xr
import logging

from app.weather.grid_io import load_grid
from app.weather.wind.models import WindGrid
from config import DATA_FOLDER, NPZ_TMP_FOLDER, WIND_NPZ_FILENAME

logger = logging.getLogger(__name__)

def process_wind(grib_path: Path, forecast: str, cycle: str) -> bool:
    wind_grid = process_wind_grid(grib_path, forecast, cycle)
    if wind_grid is None:
        logger.warning("Не удалось обработать WindGrid")
        return False

    output_path = NPZ_TMP_FOLDER / WIND_NPZ_FILENAME
    wind_grid.save_npz(output_path)
    output_path.replace(DATA_FOLDER / WIND_NPZ_FILENAME)
    return True

def process_wind_grid(path, cycle_date, cycle) -> WindGrid | None:
    res = load_grid(path, {"typeOfLevel": "heightAboveGround", "level": 10}, ("u10", "v10"))
    if res is None:
        return None
    (u, v), g = res
    return WindGrid(**g.model_dump(), u=u, v=v, cycle_date=cycle_date, cycle=cycle)