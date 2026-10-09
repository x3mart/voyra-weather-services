import json
from fastapi import FastAPI, HTTPException
import logging

from app.wave.models.wave_grid import WaveGrid
from config import CURRENT_CYCLE_JSON_PATH
from app.wave.models.wave_grid import WaveGrid

logger = logging.getLogger(__name__)



def get_wave_grid(app: FastAPI) -> WaveGrid:
    wavegrid = getattr(app.state, "wave_grid", None)
    if wavegrid is None:
        raise HTTPException(status_code=503, detail="Данные ветра еще загружаются")
    return wavegrid


def is_update_needed(wavegrid: WaveGrid | None) -> bool:
    if not CURRENT_CYCLE_JSON_PATH.exists():
        logger.info("Не найден JSON")
        return False
    
    with open(CURRENT_CYCLE_JSON_PATH, 'rb') as f:
        current_cycle = json.load(f)
    
    if wavegrid is None:
        logger.info("wavegrid пустой")
        return True

    if (current_cycle["cycle"] != wavegrid.cycle
        or current_cycle["forecast"] != wavegrid.cycle_date):
        logger.info("Новый npz")
        return True
    
    return False


