import mimetypes
import os
import aiofiles
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.core.config import settings
from src.models import Alert, StoredFile


engine = create_async_engine(settings.DB_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def list_files() -> list[StoredFile]:
    async with async_session_maker() as session:
        result = await session.execute(select(StoredFile).order_by(StoredFile.created_at.desc()))
        return list(result.scalars().all())


async def list_alerts() -> list[Alert]:
    async with async_session_maker() as session:
        result = await session.execute(select(Alert).order_by(Alert.created_at.desc()))
        return list(result.scalars().all())


async def get_file(file_id: str) -> StoredFile:
    async with async_session_maker() as session:
        file_item = await session.get(StoredFile, file_id)
        if not file_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return file_item


async def create_file(title: str, upload_file: UploadFile) -> StoredFile:
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
        mime_type=upload_file.content_type or mimetypes.guess_type(stored_name)[0] or "application/octet-stream",
        size=file_size,
        processing_status="uploaded",
    )
    async with async_session_maker() as session:
        session.add(file_item)
        await session.commit()
        await session.refresh(file_item)
    return file_item


async def update_file(file_id: str, title: str) -> StoredFile:
    async with async_session_maker() as session:
        file_item = await session.get(StoredFile, file_id)
        if not file_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        file_item.title = title
        await session.commit()
        await session.refresh(file_item)
        return file_item


async def delete_file(file_id: str) -> None:
    async with async_session_maker() as session:
        file_item = await session.get(StoredFile, file_id)
        if not file_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        stored_path = settings.STORAGE_DIR / file_item.stored_name
        if stored_path.exists():
            stored_path.unlink()
        await session.delete(file_item)
        await session.commit()


async def get_file_path(file_id: str) -> tuple[StoredFile, Path]:
    file_item = await get_file(file_id)
    stored_path = settings.STORAGE_DIR / file_item.stored_name
    if not stored_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return file_item, stored_path


async def create_alert(file_id: str, level: str, message: str) -> Alert:
    alert = Alert(file_id=file_id, level=level, message=message)
    async with async_session_maker() as session:
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        return alert
