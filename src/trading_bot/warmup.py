"""Seed only completed public price observations into an unused state database.

Binance USDT closes are proxies for Roostoo USD ticker samples. This command
places no orders and never imports another mode's wallet or execution journal.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

from .client import Client
from .config import load
from .state import ProcessLock, State


def fetch_closes(pair, count, cutoff, opener=urllib.request.urlopen):
    if not re.fullmatch(r"[A-Z0-9]{2,20}/USD", pair):
        raise ValueError("Unsupported public-history pair")
    start = cutoff - count * 300
    cursor = start
    prices = []
    hashes = []
    while cursor < cutoff:
        query = urllib.parse.urlencode(dict(symbol=pair[:-4] + "USDT", interval="5m",
            startTime=cursor * 1000, endTime=cutoff * 1000 - 1, limit=1000))
        with opener("https://data-api.binance.vision/api/v3/klines?" + query, timeout=20) as response:
            raw = response.read()
        hashes.append(hashlib.sha256(raw).hexdigest())
        rows = json.loads(raw)
        if not isinstance(rows, list) or not rows:
            raise ValueError("Public history is missing")
        for row in rows:
            ts = int(row[0])
            close_time = int(row[6])
            price = float(row[4])
            if (ts != cursor * 1000 or close_time != ts + 299999
                    or close_time >= cutoff * 1000 or not math.isfinite(price) or price <= 0):
                raise ValueError("History gap, unfinished bar or invalid price")
            prices.append((cursor, price))
            cursor += 300
    if len(prices) != count:
        raise ValueError("Unexpected history length")
    return prices, hashes


def seed(state, cfg, histories, cutoff, snapshot, now):
    """Validate every pair before one atomic insertion; refuse used state."""
    if cfg.interval_seconds != 300:
        raise ValueError("Warm-up supports five-minute sampling only")
    if (state.db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
            or state.db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            or state.get("last_success") is not None or state.get("high_water") is not None):
        raise ValueError("Warm-up requires unused state; existing history and orders are preserved")
    if int(now // 300) * 300 != cutoff:
        raise ValueError("History became stale; fetch again in the current bucket")
    fingerprint = {"pairs": list(cfg.pairs), "interval_seconds": 300}
    if state.get("sampling_config", fingerprint) != fingerprint:
        raise ValueError("State sampling configuration differs")
    if set(histories) != set(cfg.pairs):
        raise ValueError("History pair set differs")
    expected = list(range(cutoff - cfg.slow_window * 300, cutoff, 300))
    server_time = float(snapshot["ServerTime"]) / 1000
    if not math.isfinite(server_time) or abs(server_time - now) > cfg.max_quote_age_seconds:
        raise ValueError("Roostoo comparison snapshot is stale")
    records = []
    for pair in cfg.pairs:
        rows = histories[pair]
        if [ts for ts, _ in rows] != expected:
            raise ValueError("History must be complete, aligned and strictly earlier")
        if any(not math.isfinite(p) or p <= 0 for _, p in rows):
            raise ValueError("Invalid history price")
        quote = float(snapshot["Data"][pair]["LastPrice"])
        if not math.isfinite(quote) or quote <= 0 or abs(rows[-1][1] / quote - 1) > .02:
            raise ValueError("Public close differs from Roostoo by more than 2%; refuse seeding")
        # The current Roostoo observation is already known, not a future close.
        # Include it so an immediate start across a bucket boundary has no gap.
        records.extend((pair, ts, p) for ts, p in rows[1:])
        records.append((pair, cutoff, quote))
    detail = {"source": "Binance completed USDT closes plus current public Roostoo ticker",
        "cutoff": cutoff, "count_per_pair": cfg.slow_window,
        "quote_assumption": "USDT proxies USD; price check tolerance2%, not proof of identical feeds",
        "sha256": hashlib.sha256(json.dumps(records).encode()).hexdigest()}
    with state.db:
        state.db.executemany("INSERT INTO samples VALUES(?,?,?)", records)
        state.db.execute("INSERT OR REPLACE INTO kv VALUES('sampling_config',?)", (json.dumps(fingerprint),))
        state.db.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)", (now, "historical_warmup", json.dumps(detail)))
    return detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", choices=("paper", "live"), required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--paper-check", action="store_true", help="Immediately run one paper cycle under the same process lock")
    args = parser.parse_args()
    if args.paper_check and args.mode != "paper":
        parser.error("--paper-check is permitted only in paper mode")
    cfg = load(args.config)
    if cfg.interval_seconds != 300:
        parser.error("Only five-minute configurations are supported")
    root = Path(args.state_dir)
    lock = ProcessLock(root / "bot.lock")
    state = None
    try:
        state = State(root / "bot.sqlite3", args.mode, cfg.paper_cash)
        cutoff = int(time.time() // 300) * 300
        histories, hashes = {}, {}
        for pair in cfg.pairs:
            histories[pair], hashes[pair] = fetch_closes(pair, cfg.slow_window, cutoff)
        # Public endpoints only, explicitly prevent loading credentials.
        snapshot = Client(key="", secret="").ticker()
        detail = seed(state, cfg, histories, cutoff, snapshot, time.time())
        state.event("historical_warmup_responses", hashes)
        print(json.dumps(detail, indent=2))
        print("Price history seeded. No competition orders submitted; bot service has not been started.")
        if args.paper_check:
            from .engine import Engine
            import logging
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
            Engine(Client(key="", secret=""), state, cfg, "paper").cycle()
            print("Immediate paper cycle completed. No competition orders submitted.")
    finally:
        if state is not None:
            state.close()
        lock.close()


if __name__ == "__main__":
    main()
