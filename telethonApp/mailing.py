import asyncio
import os
from random import choice
from loger_manager import setup_logger
from telethon import TelegramClient, errors
from config import settings
from db.services.crud import (
    get_all_accounts_by_flag,
    get_all_leads,
    update_account,
    update_lead,
    get_all_message,
)

logger = setup_logger()

TELETHON_ID = settings.TELETHON_ID
TELETHON_HASH = settings.TELETHON_HASH
SESSION_DIR = 'telethonApp/sessions/mailing'

# Значения по умолчанию
MESSAGE_LIMIT = 4
LEADS_PER_MESSAGE = 150
ACCOUNT_TIMEOUT = 5


def get_session_file_path(account: dict) -> str:
    # Получаем путь к файлу сессии для аккаунта
    return os.path.join(SESSION_DIR, f"{account['string_session']}.session")


def load_state(state_file='mailing_state.txt'):
    # Загружаем сохранённое состояние рассылки (индекс аккаунта и ID последнего обработанного лида)
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            line = f.readline().strip()
            if line:
                last_index, last_lead_id = line.split(',')
                return int(last_index), int(last_lead_id)
    return 0, 0


def save_state(current_index, last_lead_id, state_file='mailing_state.txt'):
    # Сохраняем текущее состояние рассылки
    with open(state_file, 'w') as f:
        f.write(f"{current_index},{last_lead_id}")


async def send_message():
    global MESSAGE_LIMIT, LEADS_PER_MESSAGE, ACCOUNT_TIMEOUT

    # Запрашиваем у пользователя настройки или используем значения по умолчанию
    print("\033[96m[?]\033[0m \033[92mВведите количество сообщений на аккаунт (по умолчанию 4)(Enter - skip): \033[0m ")
    message_limit = input("\033[96m └─>\033[0m \033[92m\033[0m ")
    MESSAGE_LIMIT = int(message_limit) if message_limit else MESSAGE_LIMIT

    print("\033[96m[?]\033[0m \033[92mВведите количество лидов для смены сообщения (по умолчанию 150): \033[0m ")
    lead_per_message = input("\033[96m └─>\033[0m \033[92m\033[0m ")
    LEADS_PER_MESSAGE = int(lead_per_message) if lead_per_message else LEADS_PER_MESSAGE

    print("\033[96m[?]\033[0m \033[92mВведите интервал между сообщениями (по умолчанию 5с):  \033[0m ")
    account_timeout = input("\033[96m └─>\033[0m \033[92m\033[0m ")
    ACCOUNT_TIMEOUT = int(account_timeout) if account_timeout else ACCOUNT_TIMEOUT

    # Получаем аккаунты, предназначенные для рассылки
    accounts = get_all_accounts_by_flag(purpose='mailing')
    if not accounts:
        logger.warning("Не найдено аккаунтов для рассылки.")
        return

    # Получаем лиды из базы
    leads = get_all_leads()
    if not leads:
        logger.warning("Не найдено лидов для рассылки.")
        return

    # Получаем сообщения из базы
    messages = get_all_message()
    if not messages:
        logger.warning('В базе нет сообщений.')
        return

    current_message_index = 0  # Индекс текущего сообщения
    leads_since_last_message = 0  # Счетчик лидов, которым отправлено текущее сообщение

    # Загружаем состояние рассылки
    current_account_index, last_processed_lead_id = load_state()

    total_accounts = len(accounts)
    total_leads = len(leads)

    # Определяем индекс следующего лида после последнего обработанного
    lead_index = next((i for i, lead in enumerate(leads) if lead['telegram_id'] == last_processed_lead_id), 0)

    while lead_index < total_leads:
        # Проверка, не исчерпаны ли все аккаунты
        if all(acc.get('send_count_message', 0) >= MESSAGE_LIMIT for acc in accounts):
            logger.error("Все аккаунты достигли лимита сообщений!")
            break

        account = accounts[current_account_index]

        # Проверка лимита сообщений текущего аккаунта
        if account.get('send_count_message', 0) >= MESSAGE_LIMIT:
            logger.warning(f"Аккаунт {account['phone']} достиг лимита.")
            current_account_index = (current_account_index + 1) % total_accounts
            continue

        session_path = get_session_file_path(account)
        client = TelegramClient(session_path, TELETHON_ID, TELETHON_HASH)

        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(f"Аккаунт {account['phone']} не авторизован.")
                current_account_index = (current_account_index + 1) % total_accounts
                continue

            lead = leads[lead_index]

            # Проверяем наличие username у лида
            if not lead['username']:
                logger.warning(f"Лид {lead['telegram_id']} без username, пропущен.")
                lead_index += 1
                continue

            # Определяем сообщение для отправки
            message_text = messages[current_message_index % len(messages)]['text']

            try:
                # Отправляем сообщение лиду
                await client.send_message(lead['username'], message_text)
                # Обновляем счетчики отправок
                update_account({'phone': account['phone']}, send_count_message=account.get('send_count_message', 0) + 1)
                update_lead({'telegram_id': lead['telegram_id']}, message_count=lead['message_count'] + 1)
                logger.info(f"Отправлено {lead['username']} через {account['phone']}")
            except errors.FloodWaitError as e:
                # Обработка ошибки FloodWait
                logger.error(f"FloodWait {e.seconds}s для {account['phone']}")
                await asyncio.sleep(e.seconds)
            except errors.PeerFloodError:
                # Обработка ошибки PeerFlood
                logger.error(f"PeerFlood на {account['phone']}, статус изменён.")
                update_account({'phone': account['phone']}, status='shadow')
            except Exception as e:
                # Общая обработка других исключений
                logger.error(f"Ошибка отправки через {account['phone']}: {e}")
            finally:
                await client.disconnect()

            lead_index += 1
            leads_since_last_message += 1
            save_state(current_account_index, lead['telegram_id'])

            # Смена сообщения после указанного количества лидов
            if leads_since_last_message >= LEADS_PER_MESSAGE:
                leads_since_last_message = 0
                current_message_index += 1

            current_account_index = (current_account_index + 1) % total_accounts
            await asyncio.sleep(ACCOUNT_TIMEOUT)

        except Exception as ex:
            logger.error(f"Ошибка с аккаунтом {account['phone']}: {ex}")
            current_account_index = (current_account_index + 1) % total_accounts

    logger.info("Рассылка завершена.")  