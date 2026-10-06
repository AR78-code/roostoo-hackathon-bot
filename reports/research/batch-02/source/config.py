from dataclasses import dataclass, fields
from pathlib import Path
import math
import tomllib


@dataclass(frozen=True)
class Config:
    strategy: str = "sma"
    volatility_target: float = 0.0
    pairs: tuple[str, ...] = ("BTC/USD", "ETH/USD")
    interval_seconds: int = 300
    fast_window: int = 12
    slow_window: int = 48
    signal_threshold: float = 0.003
    max_pair_weight: float = 0.20
    max_total_weight: float = 0.40
    cash_reserve: float = 0.20
    max_order_usd: float = 2000
    min_order_usd: float = 25
    rebalance_band: float = 0.02
    max_spread: float = 0.005
    max_drawdown: float = 0.10
    fee_rate: float = 0.001
    slippage: float = 0.001
    max_quote_age_seconds: int = 30
    paper_cash: float = 100000

    def __post_init__(self):
        if self.strategy not in ("sma", "breakout"):
            raise ValueError("strategy must be sma or breakout")
        if not self.pairs or len(set(self.pairs)) != len(self.pairs):
            raise ValueError("pairs must be nonempty and unique")
        if any(not isinstance(p, str) or p.count("/") != 1 or not p.endswith("/USD") for p in self.pairs):
            raise ValueError("Only BASE/USD pairs are supported")
        for f in fields(self):
            if f.name in ("pairs", "strategy"):
                continue
            value = getattr(self, f.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{f.name} must be a finite number")
        for name in ("interval_seconds", "fast_window", "slow_window", "max_quote_age_seconds"):
            if not isinstance(getattr(self, name), int):
                raise ValueError(f"{name} must be an integer")
        if not 2 <= self.fast_window < self.slow_window <= 10000:
            raise ValueError("Require 2 <= fast_window < slow_window <= 10000")
        if self.interval_seconds < 60 or self.max_quote_age_seconds <= 0:
            raise ValueError("Polling interval must be >=60s; quote age must be positive")
        for name in ("max_pair_weight", "max_total_weight", "cash_reserve", "max_drawdown"):
            if not 0 < getattr(self, name) < 1:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in ("signal_threshold", "rebalance_band", "max_spread", "fee_rate", "slippage", "volatility_target"):
            if not 0 <= getattr(self, name) < 1:
                raise ValueError(f"{name} must be in [0, 1)")
        if self.volatility_target > 0 and self.slow_window < 289:
            raise ValueError("Volatility targeting requires at least 289 price samples")
        if not 0 < self.min_order_usd <= self.max_order_usd or self.paper_cash <= 0:
            raise ValueError("Invalid order or paper cash limits")
        if self.max_pair_weight > self.max_total_weight or self.max_total_weight > 1 - self.cash_reserve:
            raise ValueError("Exposure limits violate cash reserve")


def load(path: str) -> Config:
    values = tomllib.loads(Path(path).read_text())
    if "pairs" in values:
        values["pairs"] = tuple(values["pairs"])
    return Config(**values)
