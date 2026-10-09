from pydantic import BaseModel, field_validator


class WindPointResponse(BaseModel):
    speed: float | None
    direction: str | None

    @field_validator("speed")
    @classmethod
    def _round(cls, v: float | None) -> float | None:
        return None if v is None else round(v * 1.94384, 1)
