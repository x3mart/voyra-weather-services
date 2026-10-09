import numpy as np

from app.models import GridBaseModel


class PressureGrid(GridBaseModel):
    prmsl: np.ndarray