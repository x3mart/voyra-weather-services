import numpy as np

from app.models import GridBaseModel


class TemperatureGrid(GridBaseModel):
    t2m: np.ndarray
