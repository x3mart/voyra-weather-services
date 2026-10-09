from pydantic import BaseModel


class TemperatureGridResponse(BaseModel):
    min_x: float
    max_x: float

    min_y: float
    max_y: float

    nx: int
    ny: int

    t2m: list