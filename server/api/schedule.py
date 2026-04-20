from fastapi import APIRouter

from server.models import ScheduleConfig
from server import scheduler

router = APIRouter(prefix="/api/scan/schedule", tags=["schedule"])


@router.get("")
def get_schedule():
    config = scheduler.get_schedule()
    return ScheduleConfig(**config)


@router.put("")
def update_schedule(config: ScheduleConfig):
    result = scheduler.update_schedule(config.enabled, config.hour, config.minute)
    return ScheduleConfig(**result)
