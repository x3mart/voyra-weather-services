import json
from fastapi import FastAPI, HTTPException
import logging

from app.models.grid_base_model import GridBaseModel
from config import CURRENT_CYCLE_JSON_PATH
from app.wind.models.wind_grid import WindGrid

logger = logging.getLogger(__name__)



def get_wind_grid(app: FastAPI, grid_name: str) -> WindGrid:
    grid = getattr(app.state, grid_name, None)
    if grid is None:
        raise HTTPException(status_code=503, detail="Данные ветра еще загружаются")
    return grid


def is_update_needed(grid: GridBaseModel | None) -> bool:
    if not CURRENT_CYCLE_JSON_PATH.exists():
        logger.info("Не найден JSON")
        return False
    
    with open(CURRENT_CYCLE_JSON_PATH, 'rb') as f:
        current_cycle = json.load(f)
    
    if grid is None:
        logger.info("grid пустой")
        return True

    if (current_cycle["cycle"] != grid.cycle
        or current_cycle["forecast"] != grid.cycle_date):
        logger.info("Новый npz")
        return True
    
    return False


