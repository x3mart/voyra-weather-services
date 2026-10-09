from pydantic import BaseModel


class ServiceGridRequest(BaseModel):
    min_x: float
    max_x: float

    min_y: float
    max_y: float

    nx: int = 128
    ny: int = 128