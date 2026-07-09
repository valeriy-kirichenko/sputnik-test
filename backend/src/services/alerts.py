from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Alert
from src.repositories.alerts import AlertRepository


class AlertService:
    def __init__(self, session: AsyncSession):
        self.repo = AlertRepository(session)
        self.session = session

    async def list_alerts(self) -> list[Alert]:
        return await self.repo.list_all()

    async def create_alert(
        self, file_id: str, level: str, message: str
    ) -> Alert:
        alert = Alert(file_id=file_id, level=level, message=message)
        return await self.repo.create(alert)
