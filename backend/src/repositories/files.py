from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import StoredFile


class FileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> list[StoredFile]:
        result = await self.session.execute(
            select(StoredFile).order_by(StoredFile.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, file_id: str) -> Optional[StoredFile]:
        return await self.session.get(StoredFile, file_id)
