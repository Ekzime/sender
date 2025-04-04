from sqlalchemy.orm import declarative_base, sessionmaker, session
from sqlalchemy import (
    Enum,
    Text,
    String,
    Column,
    Integer,
    create_engine,
)
from sqlalchemy.orm import declarative_base
from config import settings


Base = declarative_base()


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    phone = Column(String(20), nullable=False, unique=True)
    string_session = Column(Text, nullable=False)
    f2a = Column(String(10), default="")
    send_count_message = Column(Integer, default=0)
    purpose = Column(Enum("parsing", "mailing", name="account_purpose"), nullable=False)
    status = Column(
        Enum("live", "ban", "shadow", name="account_status"),
        nullable=False,
        default="live",
    )

    def __repr__(self):
        return f"<Account(phone='{self.phone}', status='{self.status}', purpose='{self.purpose}')>"


class Message(Base):
    __tablename__ = "message"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)

    def __repr__(self):
        return f"<Message(id='{self.id}')>"


class Lead(Base):
    __tablename__ = "lead"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=True)
    telegram_id = Column(String(30), unique=True, nullable=True)
    message_count = Column(Integer, default=0)

    def __repr__(self):
        return (
            f"<Lead(username='{self.username}', message_count='{self.message_count}')>"
        )


# Подключение к БД, создание фабрики сессий
SQL_URL = settings.SQL_URL
engine = create_engine(SQL_URL, echo=False)

# Создаем все таблицы в базе данных
Base.metadata.create_all(engine)

# Создание сессии для работы с базой данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
