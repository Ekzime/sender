from db.services.crud import create_message, get_all_message, delete_all_message
from loger_manager import setup_logger

logger = setup_logger()


async def load_message():
    print("\033[96m[?]\033[0m \033[92mЗадать сообщение для рассылки:\033[0m ")
    new_message = input("\033[96m └─>\033[0m \033[92m\033[0m ")
    create_message(new_message)
    logger.info("Сообщение для рассылки записано в базу данных")


async def check_message():
    messages = get_all_message()
    if messages:
        for msg_dict in messages:
            k, v = next(iter(msg_dict.items()))
            print(f"{k}: {v}")
    else:
        logger.warning("Нет сообщений для просмотра!")


async def cmd_delete_all_message():
    delete_all_message()
    logger.warning("Все сообщения удалены из базы данных")
