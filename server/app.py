import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.api import scan, stock, schedule, watchlist
from server import scan_runner, scheduler

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scan_runner.set_loop(asyncio.get_event_loop())
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="A股量化选股", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router)
app.include_router(stock.router)
app.include_router(schedule.router)
app.include_router(watchlist.router)


@app.get("/api/health")
def health():
    from data_fetcher import _load_config, get_data_source_name
    config = _load_config()
    has_ts = bool(config.get("tushare_token"))
    has_ifind = bool(config.get("ifind_access_token"))
    return {
        "status": "ok",
        "data_source": get_data_source_name(),
        "tushare_configured": has_ts,
        "ifind_configured": has_ifind,
    }


@app.get("/api/config/datasource")
def get_datasource():
    from data_fetcher import _load_config, get_data_source_name
    config = _load_config()
    return {
        "current": get_data_source_name(),
        "options": ["tushare", "ifind"],
        "tushare_configured": bool(config.get("tushare_token")),
        "ifind_configured": bool(config.get("ifind_access_token")),
    }


@app.post("/api/config/datasource")
async def set_datasource(request: Request):
    from data_fetcher import set_data_source
    from server.api.stock import clear_stock_list_cache
    body = await request.json()
    ds = body.get("data_source", "tushare")
    if ds not in ("tushare", "ifind"):
        raise HTTPException(status_code=400, detail="无效数据源，可选 tushare / ifind")
    set_data_source(ds)
    clear_stock_list_cache()
    return {"data_source": ds, "status": "ok"}


if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(STATIC_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
