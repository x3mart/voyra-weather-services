from pathlib import Path
from attrs import asdict
import logging


from app.weather.grid_io import load_grid
from app.weather.temperature.models import TemperatureGrid
from config import DATA_FOLDER, NPZ_TMP_FOLDER, TEMPERATURE_NPZ_FILENAME

logger = logging.getLogger(__name__)


def process_temperature(grib_path: Path, forecast: str, cycle: str) -> bool:
    temperature_grid = process_temperature_grid(grib_path, forecast, cycle)
    if temperature_grid is None:
        logger.warning("Не удалось обработать TemperatureGrid")
        return False

    output_path = NPZ_TMP_FOLDER / TEMPERATURE_NPZ_FILENAME
    temperature_grid.save_npz(output_path)
    output_path.replace(DATA_FOLDER / TEMPERATURE_NPZ_FILENAME)
    return True

def process_temperature_grid(path, cycle_date, cycle) -> TemperatureGrid | None:
    res = load_grid(path, {"typeOfLevel": "heightAboveGround", "level": 2}, ("t2m",))
    if res is None:
        return None
    (t,), g = res
    return TemperatureGrid(**g.model_dump(), t2m=t - 273.15, cycle_date=cycle_date, cycle=cycle)