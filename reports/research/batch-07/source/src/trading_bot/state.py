import fcntl
import json
from pathlib import Path
import sqlite3
import time


class ProcessLock:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(path, "a+")
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            raise RuntimeError("Another bot process is using this state directory") from None

    def close(self):
        self.handle.close()


class State:
    def __init__(self, path, mode, initial_cash):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS samples (pair TEXT, ts REAL, price REAL, PRIMARY KEY(pair, ts));
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts REAL, kind TEXT, detail TEXT);
        CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, ts REAL, pair TEXT,
            side TEXT, quantity TEXT, status TEXT, exchange_id TEXT, detail TEXT);
        """)
        previous = self.get("mode")
        if previous is not None and previous != mode:
            self.db.close()
            raise ValueError("State directory belongs to another mode; use a separate directory")
        self.set("mode", mode)
        if self.get("paper_wallet") is None:
            self.set("paper_wallet", {"USD": initial_cash})

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, json.dumps(value, allow_nan=False)))

    def event(self, kind, detail):
        with self.db:
            self.db.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)", (time.time(), kind, json.dumps(detail, allow_nan=False)))

    def sample(self, pair, ts, price, keep):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO samples VALUES(?,?,?)", (pair, ts, price))
            self.db.execute("DELETE FROM samples WHERE pair=? AND ts NOT IN (SELECT ts FROM samples WHERE pair=? ORDER BY ts DESC LIMIT ?)", (pair, pair, keep))

    def history(self, pair):
        return self.db.execute("SELECT ts,price FROM samples WHERE pair=? ORDER BY ts", (pair,)).fetchall()

    def intent(self, pair, side, quantity):
        with self.db:
            cursor = self.db.execute("INSERT INTO orders(ts,pair,side,quantity,status) VALUES(?,?,?,?,?)", (time.time(), pair, side, str(quantity), "SUBMITTING"))
        return cursor.lastrowid

    def finish(self, local_id, status, detail, exchange_id=None, wallet=None):
        with self.db:
            self.db.execute("UPDATE orders SET status=?, detail=?, exchange_id=? WHERE id=?", (status, json.dumps(detail, allow_nan=False), str(exchange_id) if exchange_id is not None else None, local_id))
            if wallet is not None:
                self.db.execute("INSERT OR REPLACE INTO kv VALUES('paper_wallet',?)", (json.dumps(wallet, allow_nan=False),))

    def unresolved(self):
        return self.db.execute("SELECT id,exchange_id FROM orders WHERE status IN ('SUBMITTING','UNKNOWN','PENDING')").fetchall()

    def close(self):
        self.db.close()
