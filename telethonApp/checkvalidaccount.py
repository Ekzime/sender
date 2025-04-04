import os
import shutil
import asyncio
import logging
from config import settings
from db.models.model import Account
from telethon import TelegramClient
from db.services.crud import update_account
from db.services.manager import get_db_session
from telethon.errors import UserDeactivatedBanError, AuthKeyError, FloodWaitError

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("telethon").setLevel(logging.CRITICAL)  # только критические ошибки
logger = logging.getLogger(__name__)

TELETHON_HASH = settings.TELETHON_HASH
TELETHON_ID = settings.TELETHON_ID

BASE_SESSION_DIR = 'telethonApp/sessions'
STATUS_DIRS = {
    'live': {
        'parsing': os.path.join(BASE_SESSION_DIR, 'parsing'),
        'mailing': os.path.join(BASE_SESSION_DIR, 'mailing'),
    },
    'shadow': os.path.join(BASE_SESSION_DIR, 'shadow'),
    'ban': os.path.join(BASE_SESSION_DIR, 'ban')
}

def get_session_file_path(account: dict) -> str:
    """
    Ищет файл сессии для аккаунта в следующих папках (в порядке приоритета):
      1. Папка ban
      2. Папка shadow
      3. Папка live, соответствующая purpose (parsing или mailing)
      4. Базовая папка (BASE_SESSION_DIR)
    Возвращает путь к файлу, если он найден, иначе возвращает путь в базовой папке.
    """
    session_filename = account["string_session"] + ".session"
    candidate_paths = [
        os.path.join(STATUS_DIRS["ban"], session_filename),
        os.path.join(STATUS_DIRS["shadow"], session_filename),
    ]
    if account["purpose"] in STATUS_DIRS["live"]:
        candidate_paths.append(os.path.join(STATUS_DIRS["live"][account["purpose"]], session_filename))
    candidate_paths.append(os.path.join(BASE_SESSION_DIR, session_filename))
    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return os.path.join(BASE_SESSION_DIR, session_filename)

async def check_account_on_valid(account: dict) -> str:
    """
    Подключается к аккаунту, используя файл сессии, найденный с помощью get_session_file_path.
    Если авторизация не проходит, возвращается статус 'ban' или 'shadow', иначе 'live'.
    """
    session_path = get_session_file_path(account)
    client = TelegramClient(session_path, TELETHON_ID, TELETHON_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning(f"Аккаунт {account['phone']} не авторизован.")
            return 'ban'
        try:
            await client.get_me()
            logger.info(f"Аккаунт {account['phone']} живой.")
            return 'live'
        except FloodWaitError as e:
            logger.warning(f"Аккаунт {account['phone']} в теневом бане: ждать {e.seconds} сек.")
            return 'shadow'
        except UserDeactivatedBanError:
            logger.error(f"Аккаунт {account['phone']} заблокирован.")
            return 'ban'
    except AuthKeyError:
        logger.error(f"Ошибка авторизации аккаунта {account['phone']}.")
        return 'ban'
    finally:
        await client.disconnect()

async def move_session_file(account: dict, status: str):
    """
    Перемещает файл сессии в нужную подпапку в зависимости от нового статуса:
      - Если 'live' — в папку, соответствующую purpose (parsing или mailing)
      - Если 'shadow' или 'ban' — в соответствующую папку
    """
    session_filename = account["string_session"] + ".session"
    src_path = get_session_file_path(account)
    if status == 'live':
        dest_dir = STATUS_DIRS['live'][account['purpose']]
    else:
        dest_dir = STATUS_DIRS[status]
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, session_filename)
    if os.path.exists(src_path):
        shutil.move(src_path, dest_path)
        #logger.info(f"Файл {session_filename} перемещен в {dest_dir}")
    else:
        logger.warning(f"Файл {session_filename} не найден для перемещения.")

async def check_and_sort_account():
    """
    Получает аккаунты из базы, проверяет их статус и обновляет запись в БД.
    Затем перемещает файл сессии в папку, соответствующую новому статусу.
    """
    with get_db_session() as db:
        accounts = [
            {
                "phone": acc.phone,
                "string_session": acc.string_session,
                "purpose": acc.purpose,
                "status": acc.status  
            }
            for acc in db.query(Account).all()
        ]
    
    tasks = [check_account_on_valid(acc) for acc in accounts]
    results = await asyncio.gather(*tasks)

    for account, status in zip(accounts, results):
        if account.get("status") == "ban":
            # logger.warning(f"Пропущен аккаунт {account['phone']} — ранее был забанен.")
            continue
        update_account({"phone": account["phone"]}, status=status)
        await move_session_file(account=account, status=status)
