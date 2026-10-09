import asyncio
import logging
from datetime import date

import aiohttp

import logging_config
import app.utils as utils
from app.utils import Cycle, Product
from app.wave.tasks import process_wave_task
from app.weather.tasks import process_weather_task

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 300
CYCLE_CHECK_DELAY_SECONDS = 3600


async def process_cycle(session: aiohttp.ClientSession) -> int:
    current_cycles = utils.get_current_product_cycles()
    latest_cycles = await utils.get_latest_cycles(session)

    logger.info(
        "Текущие циклы - %s, циклы на сервере NOAA - %s",
        current_cycles,
        latest_cycles,
    )

    tasks: list[asyncio.Task[bool]] = []
    for product in ("weather", "wave"):
        latest_date, latest_hour = latest_cycles[product]
        if latest_date is None or latest_hour is None:
            logger.info("Новый цикл %s пока недоступен на NOAA", product)
            continue

        current_cycle = current_cycles[product]
        if current_cycle[0] is not None and not _cycle_is_newer(
            (latest_date, latest_hour), current_cycle
        ):
            continue

        tasks.append(
            asyncio.create_task(
                process_product_task(
                    product,
                    session,
                    latest_date,
                    latest_hour,
                ),
                name=f"process-{product}",
            )
        )

    results = (
        await asyncio.gather(*tasks, return_exceptions=True)
        if tasks
        else []
    )

    for result in results:
        if isinstance(result, BaseException):
            raise result

    if any(result is False for result in results):
        logger.warning("Не удалось обработать один или несколько файлов; повтор")
        return RETRY_DELAY_SECONDS

    wave_latest = latest_cycles["wave"]
    weather_latest = latest_cycles["weather"]
    if wave_latest[0] is None or weather_latest[0] is None:
        return RETRY_DELAY_SECONDS

    if wave_latest != weather_latest:
        logger.info("Циклы wave и weather пока не совпадают; повторная проверка")
        return RETRY_DELAY_SECONDS

    updated_cycles = utils.get_current_product_cycles()
    if updated_cycles["wave"] != wave_latest or updated_cycles["weather"] != weather_latest:
        return RETRY_DELAY_SECONDS

    logger.info("Все доступные циклы обработаны, ждем следующий цикл")
    return CYCLE_CHECK_DELAY_SECONDS


def _cycle_is_newer(latest: Cycle, current: Cycle) -> bool:
    latest_date, latest_hour = latest
    current_date, current_hour = current
    if latest_date is None or latest_hour is None:
        return False
    if current_date is None or current_hour is None:
        return True
    return (latest_date, int(latest_hour)) > (current_date, int(current_hour))


async def process_product_task(
    product: Product,
    session: aiohttp.ClientSession,
    forecast_date: date,
    cycle: str,
) -> bool:
    if product == "wave":
        processed = await process_wave_task(session, forecast_date, cycle)
    else:
        processed = await process_weather_task(session, forecast_date, cycle)

    if processed:
        utils.update_product_cycle_json(
            product,
            forecast_date.strftime("%Y-%m-%d"),
            cycle,
        )
    return processed


async def main() -> None:
    utils.check_required_folders()

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                delay = await process_cycle(session)
            except Exception:
                logger.exception("Ошибка обработки данных; повтор через 5 минут")
                delay = RETRY_DELAY_SECONDS

            await asyncio.sleep(delay)


if __name__ == "__main__":
    asyncio.run(main())
