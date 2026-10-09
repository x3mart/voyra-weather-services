import numpy as np

from app.models import GridBaseModel


class WindGrid(GridBaseModel):
    u: np.ndarray
    v: np.ndarray