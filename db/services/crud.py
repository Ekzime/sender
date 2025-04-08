from loger_manager import setup_logger
from sqlalchemy import delete, or_
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.sql.schema import Column
from db.services.manager import get_db_async_session
from db.models.model import Account, Message, Lead

logger = setup_logger()


# ---------------------------------------#
#              CRUD Accounts            #
# ---------------------------------------#
async def create_account(
    phone: str,
    string_session: str,
    purpose: str,
    f2a: str = "",
) -> None | dict[str, str]:
    "Создает запись в таблице Accounts"
    async with get_db_async_session() as db:
        result = await db.execute(select(Account).filter_by(phone=phone))
        acc = result.scalar_one_or_none()
        if acc:
            logger.error(
                f"create_account: Аккаунт уже есть в базе со статусом: {acc.status}"
            )
            return

        new_acc = Account(
            phone=phone,
            string_session=string_session,
            purpose=purpose,
            f2a=f2a,
        )
        db.add(new_acc)
        return {
            "phone": new_acc.phone,
            "string_session": new_acc.string_session,
            "f2a": new_acc.f2a,
        }


async def get_all_accounts_by_flag(purpose: str, status="live"):
    "Возвращает аккаунты все аккаунты по флагу purpose со статусом live"
    async with get_db_async_session() as db:
        result = await db.execute(
            select(Account).filter_by(status=status, purpose=purpose)
        )
        obj = result.scalars().all()
        accounts = []
        for acc in obj:
            accounts.append(
                {
                    "phone": acc.phone,
                    "string_session": acc.string_session,
                    "purpose": acc.purpose,
                    "status": acc.status,
                }
            )
        return accounts


async def update_account(acc, **kwargs):
    "Обновляет поля обьекта в таблице Account"
    acc_phone = acc.phone if hasattr(acc, "phone") else acc.get("phone")
    if not acc_phone:
        raise ValueError("Невозможно определить идентификатор аккаунта.")
    async with get_db_async_session() as db:
        result = await db.execute(select(Account).filter_by(phone=acc_phone))
        db_acc = result.scalar_one_or_none()
        if not db_acc:
            return None

        try:
            for k, v in kwargs.items():
                setattr(db_acc, k, v)
            db_acc.updated_at = datetime.utcnow()
            # logger.info(f"Аккаунт id={acc_phone} обновлён, поля={list(kwargs.keys())}")
            return db_acc
        except Exception as e:
            logger.error(f"Ошибка при обновлении аккаунта: {e}")
            raise e


# ---------------------------------------#
#              CRUD Messages            #
# ---------------------------------------#
async def create_message(text: str):
    """
    Создаеь заптсь в таблице Messages
    """
    async with get_db_async_session() as db:
        new_text = Message(text=text)
        db.add(new_text)
        # logger.info("create_message: Сообщение для спама записано!")


async def get_all_message():
    """
    Возвращает все сообщения из БД Messages
    """
    async with get_db_async_session() as db:
        result = await db.execute(select(Message))
        all_messages = result.scalars().all()
        return [{"text": message.text} for message in all_messages]


async def delete_all_message():
    """
    Удаляет все в таблице Message
    """
    async with get_db_async_session() as db:
        await db.execute(delete(Message))


# ---------------------------------------#
#              CRUD LEAD                #
# ---------------------------------------#
async def create_lead(username: str, phone: str, telegram_id: str):
    """
    Создает запись в таблице Lead
    """
    async with get_db_async_session() as db:
        # Ищем лида по телефону или telegram_id
        result = await db.execute(select(Lead).filter(Lead.telegram_id == telegram_id))
        lead = result.scalar_one_or_none()

        if lead:
            logger.error(f"create_lead: Лид уже есть в базе.")
            return None
        try:
            new_lead = Lead(username=username, phone=phone, telegram_id=telegram_id)
            db.add(new_lead)
            return True
        except Exception as e:
            logger.error(f"create_lead: Ошибка при создании лида: {e}")
            return False


async def update_lead(lead, **kwargs):
    """
    Обновляет параметры обьекта в таблице Lead
    """
    lead_telegram_id = (
        lead.telegram_id if hasattr(lead, "telegram_id") else lead.get("telegram_id")
    )
    if not lead_telegram_id:
        raise ValueError("update_lead: Невозможно определить идентификатор аккаунта.")
    async with get_db_async_session() as db:
        result = await db.execute(select(Lead).filter_by(telegram_id=lead_telegram_id))
        db_lead = result.scalar_one_or_none()
        if not db_lead:
            return None

        try:
            for k, v in kwargs.items():
                setattr(db_lead, k, v)
            db_lead.updated_at = datetime.utcnow()
            logger.info(
                f"update_lead: Аккаунт id={db_lead} обновлён, поля={list(kwargs.keys())}"
            )
            return db_lead
        except Exception as e:
            logger.error(f"update_lead: Ошибка при обновлении аккаунта: {e}")
            raise e


async def get_all_leads():
    """
    Возвращает список всех записей из таблицы Lead
    """
    async with get_db_async_session() as db:
        result = await db.execute(select(Lead))
        leads = result.scalars().all()
        if not leads:
            logger.warning("В таблице Leads сейчас пусто.")
            return
        leads_list = []
        for lead in leads:
            leads_list.append(
                {
                    "username": lead.username,
                    "phone": lead.phone,
                    "telegram_id": lead.telegram_id,
                    "message_count": lead.message_count,
                }
            )
        return leads_list


async def delete_all_leads():
    """
    Очищает таблицу с лидами
    """
    async with get_db_async_session() as db:
        await db.execute(delete(Lead))
