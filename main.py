import asyncio
import logging
from db.models.model import Account, session
from telethonApp.loadaccounts import process_session
from telethonApp.checkvalidaccount import check_and_sort_account
from telethonApp.parsinglead import join_and_parse_group

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main() -> None:
    while True:
        print(
            "\n1 - Загрузить сессии с файла .session \n2 - Проврека аккаунтов на валидность, сортировка\n3 - Парсинг группы\n"
        )
        event = input("select a process: ")
        if event == "1":
            await process_session()
        elif event == "2":
            await check_and_sort_account()
        elif event == "3":
            await join_and_parse_group()
        elif event == "q":
            break
        else:
            logger.info("")

    logger.info("Остановка программы")


if __name__ == "__main__":
    asyncio.run(main())
