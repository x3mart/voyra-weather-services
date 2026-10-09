from pydantic import BaseModel, field_validator



class PressurePointResponse(BaseModel):
    prmsl: float | None

    @field_validator("prmsl")
    @classmethod
    def _round(cls, prmsl: float | None) -> float | None:
        return None if prmsl is None else round(prmsl, 1)
