from pydantic import BaseModel, field_validator


class WavePointResponse(BaseModel):
    swh: float | None
    dir_deg: float | None
    perpw: float | None


    @field_validator("swh", "dir_deg", "perpw")
    @classmethod
    def _round(cls, v: float | None) -> float | None:
        if v is None:
            return None
        return round(v, 2)