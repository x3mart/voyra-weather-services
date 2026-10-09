import json
from fastapi import FastAPI, HTTPException
import logging

from app.temperature.models.temperature_grid import WindGrid
from config import CURRENT_CYCLE_JSON_PATH
from app.temperature.models.temperature_grid import WindGrid

logger = logging.getLogger(__name__)



def get_wind_grid(app: FastAPI) -> WindGrid:
    windgrid = getattr(app.state, "wind_grid", None)
    if windgrid is None:
        raise HTTPException(status_code=503, detail="Данные ветра еще загружаются")
    return windgrid


def is_update_needed(windgrid: WindGrid | None) -> bool:
    if not CURRENT_CYCLE_JSON_PATH.exists():
        logger.info("Не найден JSON")
        return False
    
    with open(CURRENT_CYCLE_JSON_PATH, 'rb') as f:
        current_cycle = json.load(f)
    
    if windgrid is None:
        logger.info("windgrid пустой")
        return True

    if (current_cycle["cycle"] != windgrid.cycle
        or current_cycle["forecast"] != windgrid.cycle_date):
        logger.info("Новый npz")
        return True
    
    return False


