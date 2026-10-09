import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "data-service.log",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler],
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger("data_service")