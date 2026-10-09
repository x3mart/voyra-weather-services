import logging
from pathlib import Path
from attr import asdict

from app.weather.grid_io import load_grid
from app.weather.pressure.models import PressureGrid
from config import DATA_FOLDER, NPZ_TMP_FOLDER, PRESSURE_NPZ_FILENAME


logger = logging.getLogger(__name__)

def process_pressure(grib_path: Path, forecast: str, cycle: str) -> bool:
    pressure_grid = process_pressure_grid(grib_path, forecast, cycle)
    if pressure_grid is None:
        logger.warning("Не удалось обработать PressureGrid")
        return False

    output_path = NPZ_TMP_FOLDER / PRESSURE_NPZ_FILENAME
    pressure_grid.save_npz(output_path)
    output_path.replace(DATA_FOLDER / PRESSURE_NPZ_FILENAME)
    return True

def process_pressure_grid(path, cycle_date, cycle) -> PressureGrid | None:
    res = load_grid(path, {"typeOfLevel": "meanSea"}, ("prmsl",))
    if res is None:
        return None
    (p,), g = res
    return PressureGrid(**g.model_dump(), prmsl=p / 100.0, cycle_date=cycle_date, cycle=cycle)