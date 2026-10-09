from datetime import date, datetime

from config import GRIB_SERVER_BASE_URL


def build_wave_url(forecast_date: date, cycle: str) -> str:
    date_str = datetime.strftime(forecast_date, "%Y%m%d")
    return (
        f"{GRIB_SERVER_BASE_URL}/gfs.{date_str}/{cycle}/wave/gridded/"
        f"gfswave.t{cycle}z.global.0p25.f000.grib2"
    )
