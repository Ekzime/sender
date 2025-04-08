import asyncio
import sys
from loger_manager import setup_logger
from db.models.model import engine, init_db
from telethonApp.loadaccounts import process_sessions
from telethonApp.checkvalidaccount import check_and_sort_account
from telethonApp.parsinglead import join_and_parse_group
from telethonApp.utils import *
from telethonApp.mailing import send_message

# модули для оформления в консоли
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
import pyfiglet

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = setup_logger()

console = Console()


async def banner_menu():
    ascii_banner = pyfiglet.figlet_format(" E X O D U S ")
    print(f"\033[92m{ascii_banner} v1.2\033[0m")
    console.print(
        Panel.fit(
            "[bold green]load_acc[/] - Загрузить сессии с файла .session\n"
            "[bold green]check_acc[/] - Проверка аккаунтов на валидность, сортировка\n"
            "[bold green]parsing[/] - Парсинг группы\n"
            "[bold green]write_mes[/] - Записать сообщение для рассылки\n"
            "[bold green]read_mes[/] - Просмотреть сообщения для рассылки\n"
            "[bold green]send_mes[/] - Рассылка сообщений\n"
            "[bold green]info_lead[/] - Просмотреть количество лидов в БД\n"
            "[bold yellow]del_mes[/] - Удалить все сообщения для рассылки\n"
            "[bold yellow]del_lead[/] - Очистить таблицу с лидами\n"
            "[bold red]q[/] - Выход",
            title="[bold cyan]Главное меню",
            border_style="cyan",
        )
    )


# Начало работы
async def main() -> None:
    console.clear()
    await init_db(engine)
    while True:
        await banner_menu()
        print("\033[96m[?]\033[0m \033[92mВыберите действие:\033[0m ")
        event = input("\033[96m └─>\033[0m \033[92m\033[0m ")
        console.clear()

        if event == "load_acc":
            await process_sessions()
        elif event == "check_acc":
            await check_and_sort_account()
        elif event == "parsing":
            await join_and_parse_group()
        elif event == "write_mes":
            await load_message()
        elif event == "read_mes":
            await check_message()
        elif event == "del_mes":
            await cmd_delete_all_message()
        elif event == "send_mes":
            await send_message()
        elif event == "del_lead":
            await cmd_delete_all_leads()
        elif event == "info_lead":
            await cmd_get_lead_count()
        elif event == "q":
            break
        else:
            logger.warning("Нет такой команды")

    logger.info("Остановка программы")
    await asyncio.sleep(0.1)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
