import os
import asyncio
import logging
import shutil
from config import settings
from loger_manager import setup_logger
from db.services.crud import create_account as crud_create_account
from telethon import TelegramClient
from telethon.errors import (
    UserDeactivatedBanError,
    AuthKeyError,
    SessionPasswordNeededError,
    FloodWaitError,
)


# Определяем настройки
class Settings:
    TELETHON_ID = settings.TELETHON_ID
    TELETHON_HASH = settings.TELETHON_HASH


settings = Settings()


async def create_account(string_session: str, phone: str, purpose: str):
    await crud_create_account(
        phone=phone, purpose=purpose, string_session=string_session
    )
    logger.info(
        f"[DB Stub] Добавление аккаунта: Телефон={phone}, Сессия={string_session}, Назначение={purpose}"
    )


# Настраиваем логгер
logging.getLogger("telethon").setLevel(logging.CRITICAL)
logger = setup_logger()

# Пути к директориям
BASE_SESSION_DIR = "telethonApp/sessions"
PARSING_SESSION_DIR = os.path.join(BASE_SESSION_DIR, "parsing")
MAILING_SESSION_DIR = os.path.join(BASE_SESSION_DIR, "mailing")

os.makedirs(PARSING_SESSION_DIR, exist_ok=True)
os.makedirs(MAILING_SESSION_DIR, exist_ok=True)

TELETHON_ID = settings.TELETHON_ID
TELETHON_HASH = settings.TELETHON_HASH


async def check_session(session_file_path: str) -> dict | None:
    """
    Подключаемся к Telegram через данный файл сессии и получаем информацию об аккаунте.
    Если сессия не авторизована, устарела или аккаунт заблокирован — возвращаем None.
    """
    session_name = os.path.basename(session_file_path).replace(".session", "")
    client = TelegramClient(session_file_path, TELETHON_ID, TELETHON_HASH)
    account_info = None

    try:
        logger.debug(f"[{session_name}] Попытка подключения...")
        await client.connect()

        if not await client.is_user_authorized():
            logger.warning(f"[{session_name}] Сессия не авторизована или устарела.")
            return None

        me = await client.get_me()
        if me:
            logger.info(
                f"[{session_name}] Успешно подключен аккаунт: {me.first_name} (@{me.username}), ID: {me.id}, Phone: {me.phone}"
            )
            account_info = {
                "session": session_name,
                "user_id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
                "full_path": session_file_path,
            }
        else:
            logger.error(
                f"[{session_name}] Не удалось получить информацию об аккаунте (get_me вернул None)."
            )
    except UserDeactivatedBanError:
        logger.error(
            f"[{session_name}] Аккаунт заблокирован (UserDeactivatedBanError)."
        )
    except AuthKeyError:
        logger.error(
            f"[{session_name}] Файл сессии некорректный или ключ авторизации недействителен (AuthKeyError)."
        )
    except ConnectionError as e:
        logger.error(f"[{session_name}] Ошибка подключения: {e}")
    except FloodWaitError as e:
        logger.error(
            f"[{session_name}] Слишком много запросов (FloodWaitError): подождите {e.seconds} секунд."
        )
    except Exception as e:
        logger.error(
            f"[{session_name}] Непредвиденная ошибка при проверке сессии: {e}",
            exc_info=True,
        )
    finally:
        if client.is_connected():
            await client.disconnect()
            logger.debug(f"[{session_name}] Соединение закрыто.")
    return account_info


async def process_sessions():
    """
    Сканирует базовую директорию на наличие .session-файлов,
    предлагает пользователю выбрать сессии для обработки,
    запрашивает назначение для каждой выбранной сессии,
    проверяет сессию, перемещает файл и сохраняет данные в БД.
    """
    # 1. Поиск .session файлов
    try:
        all_session_files = [
            f
            for f in os.listdir(BASE_SESSION_DIR)
            if f.endswith(".session")
            and os.path.isfile(os.path.join(BASE_SESSION_DIR, f))
        ]
    except FileNotFoundError:
        logger.error(f"Базовая директория сессий не найдена: {BASE_SESSION_DIR}")
        return
    except Exception as e:
        logger.error(f"Ошибка при чтении директории {BASE_SESSION_DIR}: {e}")
        return

    if not all_session_files:
        logger.warning(f"В директории {BASE_SESSION_DIR} не найдено .session файлов.")
        return

    print("\033[96m[?]\033[0m \033[92m \nНайденные файлы сессий:\033[0m ")
    for i, fname in enumerate(all_session_files):
        print(f"\033[96m[?]\033[0m \033[92m {i + 1}. {fname} \033[0m ")

    # 2. Асинхронно получаем ввод пользователя для выбора сессий
    selected_indices = set()
    while True:
        try:
            prompt = (
                "\033[96m\n[?]\033[0m \033[92mВведите номера сессий для обработки через запятую или пробел "
                "(например: 1,3,5 или 1 3 5), или 'all' для выбора всех, или 'q' для выхода:\033[0m \n"
                "\033[96m └─>\033[0m \033[92m"
            )
            user_input = (await asyncio.to_thread(input, prompt)).strip().lower()
            if user_input == "q":
                print("Выход.")
                return
            if user_input == "all":
                selected_indices = set(range(len(all_session_files)))
                break

            parts = user_input.replace(",", " ").split()
            invalid_input = False
            temp_indices = set()
            for part in parts:
                if not part.isdigit():
                    print(f"Ошибка: '{part}' не является числом.")
                    invalid_input = True
                    break
                index = int(part) - 1
                if 0 <= index < len(all_session_files):
                    temp_indices.add(index)
                else:
                    print(
                        f"Ошибка: Номер {part} вне допустимого диапазона (1-{len(all_session_files)})."
                    )
                    invalid_input = True
                    break
            if not invalid_input:
                selected_indices = temp_indices
                break
        except ValueError:
            print("Ошибка ввода. Пожалуйста, введите числа.")
        except Exception as e:
            print(f"Произошла ошибка: {e}")

    if not selected_indices:
        print("Не выбрано ни одной сессии для обработки.")
        return

    print("\033[96m[?]\033[0m \033[92m \nВыбранные сессии для обработки:\033[0m ")
    selected_files_map = {idx: all_session_files[idx] for idx in selected_indices}
    for idx, fname in selected_files_map.items():
        print(f"- {fname} (Номер {idx+1})")

    # 3. Обработка выбранных сессий
    processed_count = 0
    failed_count = 0
    tasks = []
    print("\nНачинаем обработку выбранных сессий...")
    for index in selected_indices:
        session_file = all_session_files[index]
        session_path = os.path.join(BASE_SESSION_DIR, session_file)

        # Запрашиваем назначение асинхронно
        while True:
            purpose_prompt = (
                f"\033[96m[?]\033[0m \033[92m Для сессии '{session_file}':\033[0m \n"
                "\033[96m[?]\033[0m \033[92m 1 - Парсинг\n"
                "\033[96m[?]\033[0m \033[92m 2 - Рассылка\n"
                "\033[96m └─>\033[0m \033[92m"
            )
            purpose_choice = (await asyncio.to_thread(input, purpose_prompt)).strip()
            if purpose_choice == "1":
                purpose = "parsing"
                target_dir = PARSING_SESSION_DIR
                break
            elif purpose_choice == "2":
                purpose = "mailing"
                target_dir = MAILING_SESSION_DIR
                break
            else:
                print("Неверный выбор. Пожалуйста, введите 1 или 2.")

        async def check_and_process(s_path, s_purpose, t_dir, s_file_name):
            account_info = await check_session(s_path)
            if account_info:
                target_path = os.path.join(t_dir, s_file_name)
                try:
                    # Перемещаем файл сессии в отдельном потоке, чтобы не блокировать event loop
                    await asyncio.to_thread(
                        shutil.move, account_info["full_path"], target_path
                    )
                    logger.info(
                        f"[{account_info['session']}] Файл сессии перемещен в {t_dir}"
                    )
                    # Сохраняем аккаунт в БД
                    await create_account(
                        string_session=account_info[
                            "session"
                        ],  # Используем только имя файла
                        phone=account_info["phone"],
                        purpose=s_purpose,
                    )
                    logger.info(
                        f"Аккаунт {account_info['phone']} ({account_info['session']}) успешно зарегистрирован как '{s_purpose}'."
                    )
                    return True
                except OSError as e:
                    logger.error(
                        f"[{account_info['session']}] Не удалось переместить файл сессии из {account_info['full_path']} в {target_path}: {e}"
                    )
                    print(
                        f"Ошибка: Не удалось переместить файл {s_file_name}. Подробности в логах."
                    )
                    return False
                except Exception as e:
                    logger.error(
                        f"[{account_info['session']}] Ошибка при сохранении в БД или другой операции: {e}",
                        exc_info=True,
                    )
                    print(
                        f"Ошибка: Произошла ошибка при обработке аккаунта {s_file_name}. Подробности в логах."
                    )
                    return False
            else:
                logger.warning(
                    f"Сессия из файла {s_file_name} не прошла проверку (невалидна, заблокирована или не авторизована). Файл не перемещен."
                )
                print(
                    f"\033[96m[?]\033[0m \033[92m Предупреждение: Сессия {s_file_name} невалидна или не авторизована. Пропущена.\033[0m "
                )
                return None

        tasks.append(check_and_process(session_path, purpose, target_dir, session_file))

    # 4. Запускаем все задачи одновременно и собираем результаты
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error(
                f"Непредвиденная ошибка в задаче обработки сессии: {result}",
                exc_info=result,
            )
            failed_count += 1
        elif result is True:
            processed_count += 1
        elif result is False:
            failed_count += 1
        elif result is None:
            pass

    print("\033[96m[?]\033[0m \033[92m \n--- Обработка завершена ---\033[0m ")
    print(
        f"\033[96m[?]\033[0m \033[92mУспешно обработано и перемещено: {processed_count} \033[0m "
    )
    print(
        f"\033[96m[?]\033[0m \033[92m Пропущено (невалидные/неавторизованные): {len(selected_indices) - processed_count - failed_count}\033[0m "
    )
    print(
        f"\033[96m[?]\033[0m \033[92m Возникло ошибок при обработке (перемещение/БД): {failed_count}\033[0m "
    )
    print(
        f"\033[96m[?]\033[0m \033[92m Осталось необработанных сессий в '{BASE_SESSION_DIR}': {len(all_session_files) - len(selected_indices)}\033[0m "
    )
