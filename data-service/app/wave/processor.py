from pathlib import Path
import numpy as np
import xarray as xr
import logging

from app.wave.models import WaveGrid

logger = logging.getLogger(__name__)

def process_wave_grid(path: Path, cycle_date: str, cycle: str) -> WaveGrid | None:
        
        with xr.open_dataset(
            path,
            engine="cfgrib",
            backend_kwargs={
                "filter_by_keys": {
                    "typeOfLevel": "surface",   # вместо heightAboveGround
                }
            },
        ) as ds:
            required = ("swh", "dirpw", "perpw")  # высота, направление, период"

            logger.info(ds)
            logger.info(ds.data_vars)

            for name in required:
                if name not in ds:
                    logger.warning(f"{name} не найдено в файле {path}")
                    return None
                
            perpw = ds["perpw"].values.astype(np.float32)
            swh = ds["swh"].values.astype(np.float32)
            dirpw = ds["dirpw"].values.astype(np.float32)
        
            latitudes = ds.latitude.values
            longitudes = ds.longitude.values
        
        longitudes = ((longitudes + 180) % 360) - 180

        order = np.argsort(longitudes)
        longitudes = longitudes[order]
        perpw = perpw[:, order]
        swh = swh[:, order]
        dirpw = dirpw[:, order]

        if latitudes[0] < latitudes[-1]:
            latitudes = latitudes[::-1]
            perpw = perpw[::-1, :]
            swh = swh[::-1, :]
            dirpw = dirpw[::-1, :]

        dir_to_rad = np.deg2rad(dirpw + 180) % (2 * np.pi)
        dir_u = np.sin(dir_to_rad)
        dir_v = np.cos(dir_to_rad)

        if not (perpw.shape == swh.shape == dirpw.shape):
            raise ValueError(
                f"Не совпадают размеры: perpw={perpw.shape}, swh={swh.shape}, dirpw={dirpw.shape}"
            )

        ny, nx = swh.shape

        dx = float(abs(longitudes[1] - longitudes[0]))
        dy = float(abs(latitudes[1] - latitudes[0]))

        assert np.allclose(np.diff(longitudes), dx, rtol=1e-3, atol=1e-3), "нерегулярная сетка по долготе"

        return WaveGrid(
            min_lon=float(longitudes.min()),
            max_lon=float(longitudes.max()),
            min_lat=float(latitudes.min()),
            max_lat=float(latitudes.max()),
            dx=dx,
            dy=dy,
            nx=nx,
            ny=ny,
            swh=swh,
            dir_u=dir_u,
            dir_v=dir_v,
            perpw=perpw,
            cycle_date=cycle_date,
            cycle=cycle
        )