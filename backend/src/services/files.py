import mimetypes
import os
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models import StoredFile
from src.repositories.files import FileRepository


class FileService:
    def __init__(self, session: AsyncSession):
        self.repo = FileRepository(session)
        self.session = session

    async def get_file(self, file_id: int) -> StoredFile:
        file_item = await self.repo.get_by_id(file_id)
        if not file_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        return file_item

    async def list_files(self) -> list[StoredFile]:
        return await self.repo.list_all()

    async def create_file(self, title: str, upload_file: UploadFile) -> StoredFile:
        file_id = str(uuid4())
        suffix = Path(upload_file.filename or "").suffix
        stored_name = f"{file_id}{suffix}"
        stored_path = settings.STORAGE_DIR / stored_name

        file_size = 0

        # ОПТИМИЗАЦИЯ: Асинхронная потоковая запись на диск без загрузки в RAM
        async with aiofiles.open(stored_path, "wb") as buffer:
            while chunk := await upload_file.read(1024 * 1024):
                await buffer.write(chunk)
                file_size += len(chunk)

        file_size = os.path.getsize(stored_path)
        if file_size == 0:
            stored_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty"
            )

        file_item = StoredFile(
            id=file_id,
            title=title,
            original_name=upload_file.filename or stored_name,
            stored_name=stored_name,
            mime_type=upload_file.content_type or
                      mimetypes.guess_type(stored_name)[
                          0] or "application/octet-stream",
            size=file_size,
            processing_status="uploaded",
        )
        return await self.repo.create(file_item)

    async def update_file(self, file_id: str, title: str) -> StoredFile:
        file_item = await self.repo.update(file_id, title)
        if not file_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        return file_item

    async def delete_file(self, file_id: str) -> None:
        file_item = await self.repo.get_by_id(file_id)
        if not file_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        # Удаляем файл с диска
        stored_path = settings.STORAGE_DIR / file_item.stored_name
        if stored_path.exists():
            stored_path.unlink()

        # Удаляем запись из БД
        await self.repo.delete(file_id)

    async def get_file_path(self, file_id: str) -> tuple[StoredFile, Path]:
        """
        Возвращает метаданные файла и путь к нему на диске.
        Используется для скачивания файла.
        """
        file_item = await self.get_file(file_id)
        stored_path = settings.STORAGE_DIR / file_item.stored_name

        if not stored_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored file not found"
            )

        return file_item, stored_path
