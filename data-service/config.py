from pathlib import Path

SERVICE_ROOT = Path(__file__).parent.absolute()
PROJECT_ROOT = SERVICE_ROOT.parent.absolute()

HOME = Path.home()

GFS_CYCLES= ["18", "12", "06", "00"]
DATA_FOLDER = PROJECT_ROOT / "npz"
GRIB_TMP_FOLDER = DATA_FOLDER / "grib_tmp"
NPZ_TMP_FOLDER = DATA_FOLDER / "npz_tmp"
CURRENT_CYCLE_JSON_FILENAME = "current_cycle.json"
INITIAL_CURRENT_CYCLE_JSON = {
  "forecast": "1972-03-23",
  "cycle": "0",
  "created": "1972-03-23T02:31:53.344777",
  "model": "GFS",
  "grid": "0.25"
}

WAVE_NPZ_FILENAME = "wave_data.npz"
WIND_NPZ_FILENAME = "wind_data.npz"
TEMPERATURE_NPZ_FILENAME = "temperature_data.npz"
PRESSURE_NPZ_FILENAME = "pressure_data.npz"

GRIB_SERVER_BASE_URL = "https://noaa-gfs-bdp-pds.s3.amazonaws.com" 