import asyncio
import logging
from config import settings
from loger_manager import setup_logger
from db.services.crud import create_lead, get_all_accounts_by_flag
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors.rpcerrorlist import UserAlreadyParticipantError, UserAlreadyInvitedError
from telethonApp.checkvalidaccount import get_session_file_path

from pyfiglet import Figlet

logging.getLogger("telethon").setLevel(logging.CRITICAL)  # только критические ошибки
logger = setup_logger()

TELETHON_ID = settings.TELETHON_ID
TELETHON_HASH = settings.TELETHON_HASH

async def join_group(client: TelegramClient, group_link: str):
    try:
        if group_link.startswith("https://t.me/+"):
            # Извлекаем invite hash из ссылки-приглашения
            invite_hash = group_link.split("+")[-1]
            await client(ImportChatInviteRequest(invite_hash))
        else:
            await client(JoinChannelRequest(group_link))
        logger.info(f"Успешный вход в группу {group_link}")
        return True
    except (UserAlreadyInvitedError, UserAlreadyParticipantError):
        logger.info("Клиент уже состоит в группе.")
        return False
    except Exception as e:
        logger.error(f"Ошибка при попытке войти в группу: {e}")
        await client.disconnect()
        return False


async def join_and_parse_group():
    try:
        print("\033[96m[?]\033[0m \033[92mВведите полную ссылку в группу:\033[0m ")
        GROUP_LINK = input("\033[96m └─>\033[0m \033[92m\033[0m ")
        
        accounts = get_all_accounts_by_flag('parsing')
        if not accounts:
            logger.error("Нет аккаунтов для парсинга. Проверьте статус аккаунтов в БД.")
            return

        valid_client = None
        valid_account = None

        # Перебираем аккаунты по очереди и ищем первый авторизованный
        for account in accounts:
            session_path = get_session_file_path(account)  # Получаем полный путь к файлу сессии
            client = TelegramClient(session_path, TELETHON_ID, TELETHON_HASH)
            await client.connect()
            if await client.is_user_authorized():
                valid_client = client
                valid_account = account
                logger.info(f"Используем аккаунт {account['phone']} для парсинга.")
                break
            else:
                logger.warning(f"Аккаунт {account['phone']} не авторизован. Пробуем следующий.")
                await client.disconnect()

        if not valid_client:
            logger.error("Нет авторизованных аккаунтов для парсинга.")
            return

        # Входим в группу, используя корректный запрос в зависимости от формата ссылки
        check_join = await join_group(valid_client, GROUP_LINK)
        if not check_join: return

        logger.info(f"Успешный вход в группу {GROUP_LINK}")
        logger.info("Запуск процесса парсинга группы")

        # Парсим участников группы
        async for user in valid_client.iter_participants(GROUP_LINK):
            # Если у пользователя нет username, пропускаем его
            if not user.username:
                logger.info(f"Пропущен пользователь {user.id} — отсутствует username")
                continue

            username = user.username
            phone = user.phone or "нет телефона"
            telegram_id = user.id

            create_lead(
                username=username,
                phone=phone,
                telegram_id=telegram_id,
            )
            logger.info(f"parse lead: username={username}, phone={phone}, telegram_id={telegram_id}")

        await valid_client.disconnect()
    except Exception as e:
        logger.error(f'Ошибка: {e}')



