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

# Константы и пути
BASE_SESSION_DIR = "telethonApp/sessions"
PARSING_SESSION_DIR = os.path.join(BASE_SESSION_DIR, "parsing")
MAILING_SESSION_DIR = os.path.join(BASE_SESSION_DIR, "mailing")

# Убедимся, что директории существуют
os.makedirs(PARSING_SESSION_DIR, exist_ok=True)
os.makedirs(MAILING_SESSION_DIR, exist_ok=True)

TELETHON_ID = settings.TELETHON_ID
TELETHON_HASH = settings.TELETHON_HASH


async def check_session(session_file_path: str) -> dict | None:
    """
    Подключаемся к Telegram и получаем информацию об аккаунте из файла сессии.
    Если не авторизован, заблокирован или файл сессии некорректный — возвращаем None.

    Args:
        session_file_path (str): Полный путь к файлу сессии.

    Returns:
        dict | None: Словарь с информацией об аккаунте или None в случае ошибки/неавторизации.
    """
    session_name = os.path.basename(session_file_path).replace(
        ".session", ""
    )  # Получаем имя сессии из пути
    client = TelegramClient(session_file_path, TELETHON_ID, TELETHON_HASH)
    account_info = None

    try:
        logger.debug(f"[{session_name}] Попытка подключения...")
        await client.connect()

        if not await client.is_user_authorized():
            logger.warning(f"[{session_name}] Сессия не авторизована или устарела.")
            return None  # Пока просто пропускаем неавторизованные

        me = await client.get_me()
        if me:
            logger.info(
                f"[{session_name}] Успешно подключен аккаунт: {me.first_name} (@{me.username}), ID: {me.id}, Phone: {me.phone}"
            )
            account_info = {
                "session": session_name,  # Сохраняем только имя файла без пути и расширения
                "user_id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
                "full_path": session_file_path,  # Сохраняем полный путь для перемещения
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
        )  # Логируем traceback
    finally:
        if client.is_connected():
            await client.disconnect()
            logger.debug(f"[{session_name}] Соединение закрыто.")
    return account_info


async def process_sessions():
    """
    Сканирует базовую директорию на наличие .session файлов,
    предлагает пользователю выбрать сессии для обработки,
    запрашивает назначение для каждой выбранной сессии,
    проверяет сессию, перемещает файл и сохраняет данные в БД.
    """
    # 1. Ищем все .session-файлы в базовой директории
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

    # 2. Запрашиваем у пользователя, какие сессии обработать
    selected_indices = set()
    while True:
        try:
            print(
                f"\033[96m\n[?]\033[0m \033[92mВведите номера сессий для обработки через запятую или пробел (например: 1,3,5 или 1 3 5), или 'all' для выбора всех, или 'q' для выхода:\033[0m "
            )
            user_input = input("\033[96m └─>\033[0m \033[92m\033[0m ").strip().lower()
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
                break  # Выходим из цикла while, если ввод корректен
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

    # 3. Обрабатываем каждую выбранную сессию
    processed_count = 0
    failed_count = 0
    tasks = []

    print("\nНачинаем обработку выбранных сессий...")
    for index in selected_indices:
        session_file = all_session_files[index]
        session_path = os.path.join(BASE_SESSION_DIR, session_file)

        # Запрашиваем назначение
        while True:
            print(f"\033[96m[?]\033[0m \033[92m Для сессии '{session_file}': \033[0m ")
            print("\033[96m[?]\033[0m \033[92m 1 - Парсинг\033[0m ")
            print("\033[96m[?]\033[0m \033[92m 2 - Рассылка\033[0m ")
            purpose_choice = input("\033[96m └─>\033[0m \033[92m\033[0m ").strip()
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

        # Добавляем задачу проверки сессии в список
        async def check_and_process(s_path, s_purpose, t_dir, s_file_name):
            account_info = await check_session(s_path)
            if account_info:
                # Перемещаем файл сессии
                target_path = os.path.join(t_dir, s_file_name)
                try:
                    shutil.move(account_info["full_path"], target_path)
                    logger.info(
                        f"[{account_info['session']}] Файл сессии перемещен в {t_dir}"
                    )

                    # Сохраняем аккаунт в БД
                    create_account(
                        string_session=account_info["session"],
                        phone=account_info["phone"],
                        purpose=s_purpose,
                    )
                    logger.info(
                        f"Аккаунт {account_info['phone']} ({account_info['session']}) успешно зарегистрирован как '{s_purpose}'."
                    )
                    return True  # Успех

                except OSError as e:
                    logger.error(
                        f"[{account_info['session']}] Не удалось переместить файл сессии из {account_info['full_path']} в {target_path}: {e}"
                    )
                    print(
                        f"Ошибка: Не удалось переместить файл {s_file_name}. Подробности в логах."
                    )
                    return False  # Неудача перемещения
                except Exception as e:
                    logger.error(
                        f"[{account_info['session']}] Ошибка при сохранении в БД или другой операции: {e}",
                        exc_info=True,
                    )
                    print(
                        f"Ошибка: Произошла ошибка при обработке аккаунта {s_file_name}. Подробности в логах."
                    )
                    # Решаем, нужно ли пытаться переместить файл обратно или оставить как есть
                    return False  # Неудача обработки
            else:
                logger.warning(
                    f"Сессия из файла {s_file_name} не прошла проверку (невалидна, заблокирована или не авторизована). Файл не перемещен."
                )
                print(
                    f"\033[96m[?]\033[0m \033[92m Предупреждение: Сессия {s_file_name} невалидна или не авторизована. Пропущена.\033[0m "
                )
                return None  # Сессия не прошла проверку

        tasks.append(check_and_process(session_path, purpose, target_dir, session_file))

    # 4. Запускаем асинхронные задачи и собираем результаты
    results = await asyncio.gather(
        *tasks, return_exceptions=True
    )  # Ловим исключения из корутин

    # 5. Подводим итоги
    for result in results:
        if isinstance(result, Exception):
            # Если gather поймал исключение из самой корутины check_and_process
            logger.error(
                f"Непредвиденная ошибка в задаче обработки сессии: {result}",
                exc_info=result,
            )
            failed_count += 1
        elif result is True:
            processed_count += 1
        elif result is False:
            # Означает ошибку перемещения или записи в БД, но сессия была валидна
            failed_count += 1
        elif result is None:
            # Означает, что сессия не прошла проверку check_session
            # Не считаем это как ошибку обработки, просто пропуск
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
