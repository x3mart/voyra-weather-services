import numpy as np

from app.models import GridBaseModel


class WaveGrid(GridBaseModel):
    swh: np.ndarray      # значимая высота волны, м — для цвета
    dir_u: np.ndarray    # unit-вектор направления, x-компонента
    dir_v: np.ndarray    # unit-вектор направления, y-компонента
    perpw: np.ndarray    # период, сек — для скорости анимации
