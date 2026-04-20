import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from server.models import ScanResults, SignalResult, ScanStartRequest, StrategyParams
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
    ok = scan_runner.start_scan(days=req.days, delay=req.delay, strategy_params=params)
    if not ok:
        return {"status": "already_running"}
    return {"status": "started"}


@router.get("/params")
def get_params():
    return scan_runner.get_strategy_params()


@router.get("/state")
def scan_state():
    return {"status": scan_runner.get_status()}


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
                    if event.get("type") in ("complete", "error"):
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
