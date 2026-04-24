import asyncio
import json
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from server.models import ScanResults, SignalResult, ScanStartRequest
from server import scan_runner

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.get("/results")
def get_results():
    results, timestamp = scan_runner.get_results()
    signals = [SignalResult(**s) for s in results]
    return ScanResults(timestamp=timestamp, count=len(signals), signals=signals)


@router.post("/start")
def start_scan(req: ScanStartRequest = None):
    if req is None:
        req = ScanStartRequest()
    params = req.strategy.model_dump()
    scope = req.scope.model_dump()
    ok = scan_runner.start_scan(days=req.days, delay=req.delay, strategy_params=params, scope=scope)
    if not ok:
        return {"status": "already_running"}
    return {"status": "started"}


@router.get("/params")
def get_params():
    return scan_runner.get_strategy_params()


@router.get("/universe")
def get_scan_universe(market_board: str | None = Query(default=None)):
    return scan_runner.get_scan_options(market_board=market_board)


@router.get("/history")
def get_scan_history():
    return {"runs": scan_runner.get_scan_history()}


@router.get("/state")
def scan_state():
    return scan_runner.get_state()


@router.post("/stop")
def stop_scan():
    ok = scan_runner.stop_scan()
    return {"status": "stopping" if ok else "not_running"}


@router.get("/status")
async def scan_status(request: Request):
    queue = scan_runner.create_queue()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    if event.get("type") in ("complete", "error", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            scan_runner.remove_queue(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
