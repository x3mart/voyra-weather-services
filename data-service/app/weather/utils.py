from datetime import date, datetime

from config import GRIB_SERVER_BASE_URL


def build_weather_url(forecast_date: date, cycle: str) -> str:
    date_str = datetime.strftime(forecast_date, "%Y%m%d")
    return (
        f"{GRIB_SERVER_BASE_URL}/gfs.{date_str}/{cycle}/atmos/"
        f"gfs.t{cycle}z.pgrb2.0p25.f000"
    )
