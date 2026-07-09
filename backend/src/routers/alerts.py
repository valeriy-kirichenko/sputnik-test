from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas import AlertItem
from src.services.alerts import AlertService


router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertItem])
async def list_alerts_view(db: AsyncSession = Depends(get_db)):
    service = AlertService(db)
    return await service.list_alerts()
