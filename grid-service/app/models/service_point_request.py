from pydantic import BaseModel


class ServicePointRequest(BaseModel):
    lon: float
    lat: float