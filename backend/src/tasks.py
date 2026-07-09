import asyncio
from pathlib import Path

import aiofiles
from celery import Celery
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.core.config import settings
from src.models import Alert, StoredFile
from src.services.alerts import AlertService


celery_app = Celery(
    "file_tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL
)


def get_session_maker():
    engine = create_async_engine(settings.DB_URL, poolclass=NullPool)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _scan_file_for_threats(file_id: str) -> None:
    async_session_maker = get_session_maker()
    async with async_session_maker() as session:
        file_item = await session.get(StoredFile, file_id)
        if not file_item:
            return

        file_item.processing_status = "processing"
        reasons: list[str] = []
        extension = Path(file_item.original_name).suffix.lower()

        if extension in {".exe", ".bat", ".cmd", ".sh", ".js"}:
            reasons.append(f"suspicious extension {extension}")

        if file_item.size > 10 * 1024 * 1024:
            reasons.append("file is larger than 10 MB")

        if extension == ".pdf" and file_item.mime_type not in {"application/pdf", "application/octet-stream"}:
            reasons.append("pdf extension does not match mime type")

        file_item.scan_status = "suspicious" if reasons else "clean"
        file_item.scan_details = ", ".join(reasons) if reasons else "no threats found"
        file_item.requires_attention = bool(reasons)
        await session.commit()

    extract_file_metadata.delay(file_id)


async def _extract_file_metadata(file_id: str) -> None:
    async_session_maker = get_session_maker()
    async with async_session_maker() as session:
        file_item = await session.get(StoredFile, file_id)
        if not file_item:
            return

        stored_path = settings.STORAGE_DIR / file_item.stored_name
        if not stored_path.exists():
            file_item.processing_status = "failed"
            file_item.scan_status = file_item.scan_status or "failed"
            file_item.scan_details = "stored file not found during metadata extraction"
            await session.commit()
            send_file_alert.delay(file_id)
            return

        metadata = {
            "extension": Path(file_item.original_name).suffix.lower(),
            "size_bytes": file_item.size,
            "mime_type": file_item.mime_type,
        }

        if file_item.mime_type.startswith("text/"):
            # ОПТИМИЗАЦИЯ: Асинхронное построчное чтение вместо read_text()
            line_count = 0
            char_count = 0
            async with aiofiles.open(
                stored_path, "r", encoding="utf-8", errors="ignore"
            ) as f:
                async for line in f:
                    line_count += 1
                    char_count += len(line)
            metadata["line_count"] = line_count
            metadata["char_count"] = char_count
        elif file_item.mime_type == "application/pdf":
            # ОПТИМИЗАЦИЯ: Асинхронное потоковое чтение чанками
            # для подсчета страниц PDF
            async with aiofiles.open(stored_path, "rb") as f:
                chunk_size = 1024 * 1024 * 10
                page_count = 0
                overlap = len(b"/Type /Page") - 1
                prev_chunk = b""
                while chunk := await f.read(chunk_size):
                    combined = prev_chunk + chunk
                    page_count += combined.count(b"/Type /Page")
                    prev_chunk = chunk[-overlap:] if len(
                        chunk) >= overlap else chunk
                metadata["approx_page_count"] = max(page_count, 1)

        file_item.metadata_json = metadata
        file_item.processing_status = "processed"
        await session.commit()

    send_file_alert.delay(file_id)


async def _send_file_alert(file_id: str) -> None:
    async_session_maker = get_session_maker()
    async with async_session_maker() as session:
        service = AlertService(session)
        file_item = await session.get(StoredFile, file_id)
        if not file_item:
            return

        params = {
            'file_id': file_id,
            'level': 'info',
            'message': 'File processed successfully'
        }

        if file_item.processing_status == "failed":
            params['level'] = 'critical'
            params['message'] = 'File processing failed'
        elif file_item.requires_attention:
            params['level'] = 'warning'
            params['message'] = (
                f'File requires attention: {file_item.scan_details}'
            )

        await service.create_alert(**params)


@celery_app.task
def scan_file_for_threats(file_id: str) -> None:
    asyncio.run(_scan_file_for_threats(file_id))


@celery_app.task
def extract_file_metadata(file_id: str) -> None:
    asyncio.run(_extract_file_metadata(file_id))


@celery_app.task
def send_file_alert(file_id: str) -> None:
    asyncio.run(_send_file_alert(file_id))
