from pydantic import BaseModel


class WindGridResponse(BaseModel):
    min_x: float
    max_x: float

    min_y: float
    max_y: float

    nx: int
    ny: int

    u: list
    v: list