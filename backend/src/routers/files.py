from fastapi import Depends, Form, File, UploadFile, APIRouter
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas import FileItem, FileUpdate
from src.services.files import FileService
from src.tasks import scan_file_for_threats

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("", response_model=list[FileItem])
async def list_files_view(db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    return await service.list_files()


@router.post("", response_model=FileItem, status_code=201)
async def create_file_view(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    service = FileService(db)
    file_item = await service.create_file(title=title, upload_file=file)
    scan_file_for_threats.delay(file_item.id)
    return file_item


@router.get("/{file_id}", response_model=FileItem)
async def get_file_view(file_id: str, db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    return await service.get_file(file_id)


@router.patch("/{file_id}", response_model=FileItem)
async def update_file_view(
    file_id: str,
    payload: FileUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = FileService(db)
    return await service.update_file(file_id=file_id, title=payload.title)


@router.get("/{file_id}/download")
async def download_file(file_id: str, db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    file_item, stored_path = await service.get_file_path(file_id)
    return FileResponse(
        path=stored_path,
        media_type=file_item.mime_type,
        filename=file_item.original_name,
    )


@router.delete("/{file_id}", status_code=204)
async def delete_file_view(file_id: str, db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    await service.delete_file(file_id)
