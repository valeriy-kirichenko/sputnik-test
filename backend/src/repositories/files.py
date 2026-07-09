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

    async def create(self, file_item: StoredFile) -> StoredFile:
        self.session.add(file_item)
        await self.session.flush()
        await self.session.refresh(file_item)
        return file_item

    async def update(self, file_id: str, title: str) -> Optional[StoredFile]:
        file_item = await self.session.get(StoredFile, file_id)
        if not file_item:
            return None
        file_item.title = title
        await self.session.flush()
        await self.session.refresh(file_item)
        return file_item

    async def delete(self, file_id: str) -> bool:
        file_item = await self.session.get(StoredFile, file_id)
        if not file_item:
            return False
        await self.session.delete(file_item)
        await self.session.flush()
        return True
