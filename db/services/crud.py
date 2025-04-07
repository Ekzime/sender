from loger_manager import setup_logger
from sqlalchemy import delete, or_
from datetime import datetime

from sqlalchemy.sql.schema import Column
from db.services.manager import get_db_session
from db.models.model import Account, Message, Lead

logger = setup_logger()


# ---------------------------------------#
#              CRUD Accounts            #
# ---------------------------------------#
def create_account(
    phone: str,
    string_session: str,
    purpose: str,
    f2a: str = "",
) -> None | dict[str, Column[str]]:
    "Создает запись в таблице Accounts"
    with get_db_session() as db:
        acc = db.query(Account).filter_by(phone=phone).first()
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
        db.commit()
        db.refresh(new_acc)
        return {
            "phone": new_acc.phone,
            "string_session": new_acc.string_session,
            "f2a": new_acc.f2a,
        }
    
def get_all_accounts_by_flag(purpose: str, status='live'):
    "Возвращает аккаунты все аккаунты по флагу purpose со статусом live"
    with get_db_session() as db:
        obj  = db.query(Account).filter_by(status=status, purpose=purpose).all()
        accounts = []
        for acc in obj:
            accounts.append({
                'phone': acc.phone,
                'string_session': acc.string_session,
                'purpose': acc.purpose,
                'status': acc.status    
            }) 
        return accounts
    


def update_account(acc, **kwargs):
    "Обновляет поля обьекта в таблице Account"
    acc_phone = acc.phone if hasattr(acc, "phone") else acc.get("phone")
    if not acc_phone:
        raise ValueError("Невозможно определить идентификатор аккаунта.")
    with get_db_session() as db:
        db_acc = db.query(Account).filter_by(phone=acc_phone).first()
        if not db_acc:
            return None

        try:
            for k, v in kwargs.items():
                setattr(db_acc, k, v)
            db_acc.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_acc)
            #logger.info(f"Аккаунт id={acc_phone} обновлён, поля={list(kwargs.keys())}")
            return db_acc
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при обновлении аккаунта: {e}")
            raise e

# ---------------------------------------#
#              CRUD Messages            #
# ---------------------------------------#
def create_message(text: str):
    """
    Создаеь заптсь в таблице Messages
    """
    with get_db_session() as db:
        new_text = Message(text=text)
        db.add(new_text)
        db.commit() 
        #logger.info("create_message: Сообщение для спама записано!")

def get_all_message():
    '''
        Возвращает все сообщения из БД Messages
    '''
    with get_db_session() as db:
        all_messages = db.query(Message).all()
        result = []
        for message in all_messages:
            result.append({'text': message.text})
        return result


def delete_all_message():
    '''
        Удаляет все в таблице Message
    '''
    with get_db_session() as db:
        db.query(Message).delete(synchronize_session=False)
        db.commit()


# ---------------------------------------#
#              CRUD LEAD                #
# ---------------------------------------#
def create_lead(username: str, phone: str, telegram_id: str):
    """
    Создает запись в таблице Lead
    """
    with get_db_session() as db:
        # Ищем лида по телефону или telegram_id
        lead = db.query(Lead).filter(Lead.telegram_id == telegram_id).first()

        if lead:
            logger.error(f"create_lead: Лид уже есть в базе.")
            return None
        try:
            new_lead = Lead(username=username, phone=phone, telegram_id=telegram_id)
            db.add(new_lead)
            db.commit()
            db.refresh(new_lead)
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"create_lead: Ошибка при создании лида: {e}")
            return False



def update_lead(lead, **kwargs):
    """
    Обновляет параметры обьекта в таблице Lead
    """
    lead_telegram_id = (
        lead.telegram_id if hasattr(lead, "telegram_id") else lead.get("telegram_id")
    )
    if not lead_telegram_id:
        raise ValueError("update_lead: Невозможно определить идентификатор аккаунта.")
    with get_db_session() as db:
        db_lead = db.query(Lead).filter_by(telegram_id=lead_telegram_id).first()
        if not db_lead:
            return None

        try:
            for k, v in kwargs.items():
                setattr(db_lead, k, v)
            db_lead.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_lead)
            logger.info(
                f"update_lead: Аккаунт id={db_lead} обновлён, поля={list(kwargs.keys())}"
            )   
            return db_lead
        except Exception as e:
            db.rollback()
            logger.error(f"update_lead: Ошибка при обновлении аккаунта: {e}")
            raise e

def get_all_leads():
    """
        Возвращает список всех записей из таблицы Lead
    """
    with get_db_session() as db:
        leads = db.query(Lead).all()
        if not leads:
            logger.info("get_all_leads: В таблице Leads сейчас пусто.")
            return
        results = []
        for lead in leads:
            results.append({
                'username': lead.username,
                'phone': lead.phone,
                'telegram_id': lead.telegram_id,
                'message_count': lead.message_count
            })
        return results

def delete_all_leads():
    """
    Очищает таблицу с лидами
    """
    with get_db_session() as db:
        db.query(Lead).delete(synchronize_session=False)
        db.commit()

