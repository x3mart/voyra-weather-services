
import asyncio
import logging
from pathlib import Path

import aiohttp

from config import GRIB_TMP_FOLDER

logger = logging.getLogger(__name__)


async def download_grib(
    session: aiohttp.ClientSession, url: str
) -> Path | None:
    filename = url.rsplit("/", maxsplit=1)[-1]
    path = GRIB_TMP_FOLDER / filename
    logger.info("Скачиваем файл %s", filename)
    downloaded = False

    try:
        timeout = aiohttp.ClientTimeout(
            total=None,
            sock_connect=30,
            sock_read=120,
        )
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                logger.warning(
                    "Не удалось скачать файл %s: HTTP %s",
                    url,
                    response.status,
                )
                return None

            with path.open("wb") as output:
                async for chunk in response.content.iter_chunked(64 * 1024):
                    await asyncio.to_thread(output.write, chunk)

        downloaded = True
        return path
    except asyncio.TimeoutError:
        logger.warning("Таймаут при загрузке GRIB %s", url)
        return None
    except (aiohttp.ClientError, OSError):
        logger.exception("Ошибка при загрузке GRIB %s", url)
        return None
    finally:
        if not downloaded:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Не удалось удалить неполный GRIB-файл %s", path)
