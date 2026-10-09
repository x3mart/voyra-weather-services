from pydantic import BaseModel


class WaveGridResponse(BaseModel):
    min_x: float
    max_x: float

    min_y: float
    max_y: float

    nx: int
    ny: int

    dir_u: list
    dir_v: list
    swh: list
    perpw: list