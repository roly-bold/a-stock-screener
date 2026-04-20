import json
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

_SCHEDULER = None
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

_DEFAULT_SCHEDULE = {"enabled": False, "hour": 15, "minute": 30}
_runtime_schedule = None


def _load_config():
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(full_config):
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(full_config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_schedule():
    global _runtime_schedule
    if _runtime_schedule is not None:
        return _runtime_schedule.copy()
    env_enabled = os.environ.get("SCHEDULE_ENABLED", "")
    if env_enabled:
        return {
            "enabled": env_enabled.lower() in ("true", "1", "yes"),
            "hour": int(os.environ.get("SCHEDULE_HOUR", "15")),
            "minute": int(os.environ.get("SCHEDULE_MINUTE", "30")),
        }
    config = _load_config()
    return config.get("schedule", _DEFAULT_SCHEDULE.copy())


def update_schedule(enabled, hour, minute):
    global _runtime_schedule
    sched = {"enabled": enabled, "hour": hour, "minute": minute}
    _runtime_schedule = sched
    full = _load_config()
    full["schedule"] = sched
    _save_config(full)
    _apply_schedule()
    return sched


def _apply_schedule():
    if _SCHEDULER is None:
        return
    _SCHEDULER.remove_all_jobs()
    config = get_schedule()
    if config.get("enabled", False):
        from server import scan_runner
        _SCHEDULER.add_job(
            scan_runner.start_scan,
            CronTrigger(hour=config["hour"], minute=config["minute"]),
            id="daily_scan",
            replace_existing=True,
        )


def start_scheduler():
    global _SCHEDULER
    _SCHEDULER = AsyncIOScheduler()
    _apply_schedule()
    _SCHEDULER.start()


def stop_scheduler():
    global _SCHEDULER
    if _SCHEDULER:
        _SCHEDULER.shutdown()
        _SCHEDULER = None
