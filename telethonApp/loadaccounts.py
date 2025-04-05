import os
import asyncio
import logging
from config import settings
from loger_manager import setup_logger
from db.services.crud import create_account
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, UserDeactivatedBanError, AuthKeyError



logging.getLogger("telethon").setLevel(logging.CRITICAL) #(только критические ошибки)
logger = setup_logger()


SESSION_DIR = 'telethonApp/sessions'
TELETHON_HASH = settings.TELETHON_HASH
TELETHON_ID = settings.TELETHON_ID

async def check_session(session_file):
    """
        Подключение к Telegram и получение информации об аккаунте
    """
    session_name = os.path.splitext(session_file)[0]
    client = TelegramClient(os.path.join(SESSION_DIR,session_name), TELETHON_HASH, TELETHON_ID)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.info(f"check_session: session = {session_name} не авторизована или устарела!")
            return None
        
        me = await client.get_me()
        logger.info(f'check_session: Подключен аккаунт {me.first_name} (@{me.username})')
        return {
            'session': session_name,
            'user_id': me.id,
            'first_name': me.first_name,
            'last_name': me.last_name,
            'username': me.username,
            'phone': me.phone,  
        }
    except UserDeactivatedBanError:
        logger.error(f"check_session: [{session_name}] Аккаунт заблокирован.")
        return None
    except AuthKeyError:
        logger.error(f"check_session: [{session_name}] Ошибка авторизации, файл session некорректный.")
        return None
    finally:
        await client.disconnect()

async def process_session():
    session_files:list[str] = [f for f in os.listdir(SESSION_DIR) if f.endswith('.session')]
    tasks: list = [check_session(session_file=session_file) for session_file in session_files]
    results = await asyncio.gather(*tasks)

    for account_info in results:
        create_account(
            string_session=account_info['session'],
            phone=account_info['phone'],
            purpose='parsing'
        )