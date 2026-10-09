from pathlib import Path
from numpy import savez
from pydantic import BaseModel, ConfigDict, Field


class GridGeometry(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float
    dx: float = Field(gt=0)
    dy: float = Field(gt=0)
    nx: int = Field(gt=0)
    ny: int = Field(gt=0)

class GridBaseModel(GridGeometry):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, extra="forbid")

    cycle: str
    cycle_date: str

    def save_npz(self, path: Path):
        savez(path, **self.model_dump())