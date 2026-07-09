from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.core.config import settings
from src.models import Alert, StoredFile


engine = create_async_engine(settings.DB_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def list_alerts() -> list[Alert]:
    async with async_session_maker() as session:
        result = await session.execute(select(Alert).order_by(Alert.created_at.desc()))
        return list(result.scalars().all())


async def create_alert(file_id: str, level: str, message: str) -> Alert:
    alert = Alert(file_id=file_id, level=level, message=message)
    async with async_session_maker() as session:
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        return alert
