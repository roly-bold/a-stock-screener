from fastapi import APIRouter

from server.models import WatchlistAddRequest, WatchlistItem
from server import watchlist

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
def list_watchlist():
    items = watchlist.get_watchlist()
    return {"items": [WatchlistItem(**item) for item in items]}


@router.post("")
def add_to_watchlist(req: WatchlistAddRequest):
    ok = watchlist.add_to_watchlist(req.code, req.name, req.entry_price, req.entry_date)
    if not ok:
        return {"status": "already_exists"}
    return {"status": "added"}


@router.delete("/{code}")
def remove_from_watchlist(code: str):
    watchlist.remove_from_watchlist(code)
    return {"status": "removed"}


@router.post("/refresh")
def refresh_watchlist():
    alerts = watchlist.refresh_watchlist()
    return {"alerts": alerts, "count": len(alerts)}


@router.get("/alerts")
def get_alerts():
    alerts = watchlist.get_alerts()
    return {"alerts": alerts}
