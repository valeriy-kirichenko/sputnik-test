from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.schemas import AlertItem, FileItem, FileUpdate
from src.services.alerts import AlertService
from src.routers import files, alerts
from src.services.files import FileService
from src.tasks import scan_file_for_threats

from src.core.database import get_db


def create_app() -> FastAPI:
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

    app.include_router(files.router)
    app.include_router(alerts.router)

    return app


app = create_app()
