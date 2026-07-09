from fastapi import FastAPI, HTTPException, Depends
from fastapi import File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.core.config import settings
from src.schemas import AlertItem, FileItem, FileUpdate
from src.service import list_alerts
from src.services.alerts import AlertService
from src.services.files import FileService
from src.tasks import scan_file_for_threats

from src.core.database import get_db


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/files", response_model=list[FileItem])
async def list_files_view(db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    return await service.list_files()


@app.get("/alerts", response_model=list[AlertItem])
async def list_alerts_view(db: AsyncSession = Depends(get_db)):
    service = AlertService(db)
    return await service.list_alerts()


@app.post("/files", response_model=FileItem, status_code=201)
async def create_file_view(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    service = FileService(db)
    file_item = await service.create_file(title=title, upload_file=file)
    scan_file_for_threats.delay(file_item.id)
    return file_item


@app.get("/files/{file_id}", response_model=FileItem)
async def get_file_view(file_id: str, db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    return await service.get_file(file_id)


@app.patch("/files/{file_id}", response_model=FileItem)
async def update_file_view(
    file_id: str,
    payload: FileUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = FileService(db)
    return await service.update_file(file_id=file_id, title=payload.title)


@app.get("/files/{file_id}/download")
async def download_file(file_id: str, db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    file_item, stored_path = await service.get_file_path(file_id)
    return FileResponse(
        path=stored_path,
        media_type=file_item.mime_type,
        filename=file_item.original_name,
    )


@app.delete("/files/{file_id}", status_code=204)
async def delete_file_view(file_id: str, db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    await service.delete_file(file_id)
