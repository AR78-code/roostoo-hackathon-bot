import argparse
from dataclasses import asdict
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import sys
import threading

from .client import APIError, Client
from .config import load
from .demo import DemoClient
from .engine import Engine
from .state import ProcessLock, State


def main():
    parser = argparse.ArgumentParser(description="Autonomous Roostoo paper/live bot")
    parser.add_argument("command", choices=("run", "preflight", "demo", "status"))
    parser.add_argument("--config", default="config/bot.toml")
    parser.add_argument("--mode", choices=("paper", "live"), default="paper")
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--cycles", type=int, default=180, help="Offline demo cycles")
    args = parser.parse_args()
    cfg = load(args.config)
    if args.cycles < 1:
        parser.error("--cycles must be positive")
    mode = "demo" if args.command == "demo" else args.mode
    root = Path(args.state_dir or f"state/{mode}")
    root.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(root / "bot.log", maxBytes=5_000_000, backupCount=4)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.StreamHandler(), handler])
    log = logging.getLogger(__name__)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    lock = ProcessLock(root / "bot.lock")
    state = None
    try:
        state = State(root / "bot.sqlite3", mode, cfg.paper_cash)
        fingerprint = {"pairs": list(cfg.pairs), "interval_seconds": cfg.interval_seconds}
        old = state.get("sampling_config")
        if old is not None and old != fingerprint:
            raise ValueError("Sampling config changed; use a new state directory")
        state.set("sampling_config", fingerprint)
        state.event("startup", {"mode": mode, "config": asdict(cfg)})
        if args.command == "status":
            print(json.dumps({"mode": mode, "last_success": state.get("last_success"), "drawdown_halt": state.get("drawdown_halt", False), "unresolved_orders": state.unresolved(), "paper_wallet": state.get("paper_wallet") if mode != "live" else None}, indent=2))
            return 0
        client = DemoClient(cfg) if mode == "demo" else Client()
        if mode == "live" and (not client.key or not client.secret):
            raise ValueError("Live mode requires ROOSTOO_API_KEY and ROOSTOO_SECRET_KEY")
        if args.command == "preflight":
            client.sync_clock()
            info = client.exchange_info()
            data = client.ticker()
            for pair in cfg.pairs:
                if not info["TradePairs"].get(pair, {}).get("CanTrade") or pair not in data["Data"]:
                    raise ValueError(f"Configured pair is not available: {pair}")
            if mode == "live":
                client.balance()
            print("Preflight passed: server time, exchange rules, tickers" + (", authentication" if mode == "live" else " (public endpoints only)"))
            return 0
        engine = Engine(client, state, cfg, mode)
        failures = 0
        iterations = 0
        while not stop.is_set():
            try:
                engine.cycle()
                failures = 0
            except (APIError, ValueError, KeyError, TypeError) as exc:
                failures += 1
                log.error("Cycle skipped: %s", exc)
                state.event("cycle_error", {"type": type(exc).__name__, "message": str(exc)[:250]})
                if args.once or mode == "demo":
                    return 1
            iterations += 1
            if args.once or (mode == "demo" and iterations >= args.cycles):
                break
            if mode != "demo":
                stop.wait(min(3600, cfg.interval_seconds * 2 ** min(failures, 3)))
        if mode == "demo":
            count = state.db.execute("SELECT COUNT(*) FROM orders WHERE status='FILLED'").fetchone()[0]
            print(f"Offline demo complete: {iterations} cycles, {count} paper fills; state: {root}")
        return 0
    finally:
        if state is not None:
            state.close()
        lock.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Bot stopped: {exc}", file=sys.stderr)
        sys.exit(1)
