from pydantic import BaseModel, field_validator



class TemperaturePointResponse(BaseModel):
    t2m: float | None

    @field_validator("t2m")
    @classmethod
    def _round(cls, t2m: float | None) -> float | None:
        return None if t2m is None else round(t2m, 1)
