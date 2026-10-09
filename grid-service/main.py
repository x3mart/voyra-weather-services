import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Callable, Protocol, Self
from fastapi import FastAPI, Depends, HTTPException, Response #type: ignore
from datetime import datetime

from app.models.all_services_point_response import AllServicesPointResponse
from app.models.grid_base_model import GridBaseModel
from app.models.service_point_response import ServicePointResponse
from app.pressure.models.pressure_grid import PressureGrid
from app.wind.models.wind_grid import WindGrid
import logger_config
import logging

from config import PRESSURE_NPZ_PATH, TEMPERATURE_NPZ_PATH, WAVE_NPZ_PATH, WIND_NPZ_PATH
from app.wave.models.wave_grid import WaveGrid
from app.temperature.models.temperature_grid import TemperatureGrid
from app.wave.models.wave_grid_response import WaveGridResponse
from app.models.service_point_request import ServicePointRequest
from app.models.service_grid_request import ServiceGridRequest
from services import is_update_needed


logger = logging.getLogger(__name__)


class ServiceName(StrEnum):
    wave = "wave"
    wind = "wind"
    pressure = "pressure"
    temperature = "temperature"

assert set(AllServicesPointResponse.model_fields) == {s.value for s in ServiceName}


@dataclass(frozen=True)
class ServiceConfig:
    name: ServiceName
    path: Path
    cls: type[GridBaseModel]
    needs_update: Callable[[Any], bool] = is_update_needed
    interval: float = 300


SERVICES: dict[ServiceName, ServiceConfig] = {
    s.name: s
    for s in (
        ServiceConfig(ServiceName.wave, WAVE_NPZ_PATH, WaveGrid),
        ServiceConfig(ServiceName.wind, WIND_NPZ_PATH, WindGrid),
        ServiceConfig(ServiceName.pressure, PRESSURE_NPZ_PATH, PressureGrid),
        ServiceConfig(ServiceName.temperature, TEMPERATURE_NPZ_PATH, TemperatureGrid),
    )
}


async def load_grid(service: ServiceConfig):
    if not service.path.exists():
        logger.warning(f"[{service.name}] не найден файл NPZ {service.path}")
        return None
    try:
        return await asyncio.to_thread(service.cls.load, service.path)
    except Exception:
        logger.exception(f"[{service.name}] не удалось прочитать {service.path}")
        return None


async def grid_updater(app: FastAPI, service: ServiceConfig):
    while True:
        await asyncio.sleep(service.interval)
        try:
            current = app.state.grids.get(service.name)
            if service.needs_update(current):
                new_grid = await load_grid(service)
                if new_grid is not None:
                    app.state.grids[service.name] = new_grid
                    logger.info(
                        f"[{service.name}] сетка обновлена: "
                        f"{getattr(new_grid, 'cycle', '?')}, {getattr(new_grid, 'cycle_date', '?')}"
                    )
        except Exception:
            logger.exception(f"[{service.name}] ошибка при обновлении сетки в памяти")


@asynccontextmanager
async def lifespan(app: FastAPI):
    grids = await asyncio.gather(*(load_grid(s) for s in SERVICES.values()))
    app.state.grids = dict(zip(SERVICES, grids))

    tasks = [
        asyncio.create_task(grid_updater(app, s), name=f"{s.name}_updater")
        for s in SERVICES.values()
    ]

    yield

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

def get_grid(app: FastAPI, service: str) -> GridBaseModel:
    if service not in SERVICES:
        raise HTTPException(404, f"Неизвестный сервис: {service}")
    grid = app.state.grids.get(service)
    if grid is None:
        raise HTTPException(503, f"Сетка {service} ещё не загружена")
    return grid  


app = FastAPI(lifespan=lifespan)


@app.get("/grids/{service}")
async def get_grid_binary(
    service: str,
    request: ServiceGridRequest = Depends(),
) -> Response:
    grid = get_grid(app, service)

    return Response(
        content=grid.resample_binary(request),
        media_type="application/octet-stream"
    )

@app.get("/points/{service}")
async def get_service_point(
    service: str,
    request: ServicePointRequest = Depends(), 
) -> ServicePointResponse:
    grid = get_grid(app, service)
    return grid.sample_point(request.lon, request.lat)


@app.get("/points")
async def get_all_services_point(
    request: ServicePointRequest = Depends(),
) -> AllServicesPointResponse:
    result: dict[str, ServicePointResponse | None] = {}

    for name in ServiceName:
        grid = app.state.grids.get(name)
        if grid is None:
            result[name.value] = None
            continue
        try:
            result[name.value] = grid.sample_point(request.lon, request.lat)
        except Exception:
            logger.exception(f"[{name}] ошибка sample_point")
            result[name.value] = None

    return AllServicesPointResponse(**result) #type: ignore