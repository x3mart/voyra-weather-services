from pydantic import BaseModel


class PressureGridResponse(BaseModel):
    min_x: float
    max_x: float

    min_y: float
    max_y: float

    nx: int
    ny: int

    prmsl: list