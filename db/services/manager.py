from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.model import async_session_factory

@asynccontextmanager
async def get_db_async_session():
    """
    Контекст-менеджер, который автоматически делает commit() при успехе
    или rollback() при ошибке, и закрывает сессию.
    """
    db: AsyncSession = async_session_factory()
    try:
        yield db
        await db.commit()   # если до этого не было ошибок, делаем commit
    except:
        await db.rollback() # при любой ошибке откатываем
        raise         # пробрасываем исключение выше
    finally:
        await db.close()    # закрываем сессию в любом случае