from pydantic import BaseModel


class StrategyParams(BaseModel):
    vol_ma_window: int = 20
    vol_ratio_threshold: float = 2.0
    rise_threshold: float = 9.5
    cons_min_days: int = 3
    cons_max_days: int = 15
    vol_shrink_ratio: float = 0.5


class ScanStartRequest(BaseModel):
    days: int = 120
    delay: float = 0.05
    strategy: StrategyParams = StrategyParams()


class SignalResult(BaseModel):
    code: str
    name: str
    breakout_date: str
    pivot_high: float
    support_price: float
    breakout_vol: int
    consolidation_end: str
    entry_date: str
    entry_price: float
    entry_vol: int
    latest_date: str
    latest_close: float
    exit_triggered: bool
    pnl_pct: float
    winner_rate: float = 0
    weight_avg_cost: float = 0
    cost_50pct: float = 0
    broker_count: int = 0
    brokers: list[str] = []


class ScanResults(BaseModel):
    timestamp: str = ""
    count: int = 0
    signals: list[SignalResult] = []


class ScanProgress(BaseModel):
    phase: str
    current: int
    total: int
    percent: float


class StockHistoryBar(BaseModel):
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    pct_change: float


class StockSearchResult(BaseModel):
    code: str
    name: str


class ScheduleConfig(BaseModel):
    enabled: bool = False
    hour: int = 15
    minute: int = 30


class WatchlistItem(BaseModel):
    code: str
    name: str
    entry_price: float
    entry_date: str
    added_at: str = ""
    exit_triggered: bool = False
    latest_close: float | None = None
    pnl_pct: float | None = None


class WatchlistAddRequest(BaseModel):
    code: str
    name: str
    entry_price: float
    entry_date: str
