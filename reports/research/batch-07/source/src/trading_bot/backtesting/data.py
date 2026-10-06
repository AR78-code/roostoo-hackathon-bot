from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import time
import tomllib
import urllib.request
import zipfile

PERIODS = ("development", "validation", "test")
FIELDS = ("timestamp", "pair", "open", "high", "low", "close", "volume")


def utc_date(value):
    return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


@dataclass(frozen=True)
class Bar:
    timestamp: int
    pair: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def validate(self):
        values = (self.open, self.high, self.low, self.close, self.volume)
        if any(not math.isfinite(v) for v in values) or min(values[:4]) <= 0 or self.volume < 0:
            raise ValueError(f"Invalid OHLCV at {self.pair} {self.timestamp}")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.low > self.high:
            raise ValueError(f"Inconsistent OHLC at {self.pair} {self.timestamp}")


def load_spec(path):
    spec = tomllib.loads(Path(path).read_text())
    validate_spec(spec)
    return spec


def validate_spec(spec):
    if not isinstance(spec["interval_seconds"], int) or spec["interval_seconds"] < 60:
        raise ValueError("Invalid historical bar interval")
    if not 0 <= spec["spread_bps"] < 10000 or not math.isfinite(spec["spread_bps"]):
        raise ValueError("Invalid assumed spread")
    if not isinstance(spec["amount_precision"], int) or not 0 <= spec["amount_precision"] <= 18:
        raise ValueError("Invalid amount precision")
    if not math.isfinite(spec["exchange_min_order"]) or spec["exchange_min_order"] < 0:
        raise ValueError("Invalid exchange minimum")
    previous = None
    for name in PERIODS:
        start, end = utc_date(spec[name]["start"]), utc_date(spec[name]["end"])
        if start >= end or (previous is not None and start != previous):
            raise ValueError("Periods must be chronological, nonoverlapping and contiguous")
        if start % spec["interval_seconds"] or end % spec["interval_seconds"]:
            raise ValueError("Period boundaries must align with bar interval")
        previous = end


def load_period(path, name, spec, pairs):
    start, end = utc_date(spec[name]["start"]), utc_date(spec[name]["end"])
    step = spec["interval_seconds"]
    by_pair = {p: {} for p in pairs}
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"CSV columns must be {','.join(FIELDS)}")
        for row in reader:
            pair, ts = row["pair"], int(row["timestamp"])
            if pair not in by_pair or not start <= ts < end or ts % step:
                raise ValueError(f"Unexpected pair, timestamp or period in {path}: {pair} {ts}")
            bar = Bar(ts, pair, *(float(row[k]) for k in FIELDS[2:]))
            bar.validate()
            if ts in by_pair[pair]:
                raise ValueError(f"Duplicate bar: {pair} {ts}")
            by_pair[pair][ts] = bar
    expected = set(range(start, end, step))
    for pair, values in by_pair.items():
        if set(values) != expected:
            missing = sorted(expected - set(values))
            raise ValueError(f"Incomplete {name} data for {pair}: {len(missing)} missing bars; no implicit filling")
    return [{p: by_pair[p][ts] for p in pairs} for ts in sorted(expected)]


def months(start, end):
    current = datetime.fromtimestamp(start, timezone.utc).replace(day=1)
    while current.timestamp() < end:
        yield current.strftime("%Y-%m")
        current = current.replace(year=current.year + 1, month=1) if current.month == 12 else current.replace(month=current.month + 1)


def fetch_bytes(url):
    # Only downloads; no authentication, exchange requests or order endpoints.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def fetch_period(root, name, spec, pairs):
    """Download official Binance monthly Spot archives and verify SHA256."""
    if set(pairs) != {"BTC/USD", "ETH/USD"}:
        raise ValueError("Downloader currently supports BTC/USD and ETH/USD proxies only")
    intervals = {60:"1m", 180:"3m", 300:"5m", 900:"15m", 1800:"30m", 3600:"1h"}
    if spec["interval_seconds"] not in intervals:
        raise ValueError("Unsupported downloader interval")
    start, end = utc_date(spec[name]["start"]), utc_date(spec[name]["end"])
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    output = root / f"{name}.csv"
    if output.exists():
        raise ValueError(f"{output} exists; downloads never overwrite research data")
    provenance = []
    rows = []
    for pair in pairs:
        symbol = pair.split("/")[0] + "USDT"
        for month in months(start, end):
            interval = intervals[spec["interval_seconds"]]
            filename = f"{symbol}-{interval}-{month}.zip"
            url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/{interval}/{filename}"
            print(f"Downloading {filename}", flush=True)
            raw = fetch_bytes(url)
            expected = fetch_bytes(url + ".CHECKSUM").decode().split()[0].lower()
            actual = hashlib.sha256(raw).hexdigest()
            if expected != actual:
                raise ValueError(f"Checksum mismatch: {filename}")
            provenance.append({"url": url, "sha256": actual, "symbol":symbol})
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = [n for n in archive.namelist() if n.endswith('.csv')]
                if len(members) != 1:
                    raise ValueError("Expected one CSV per archive")
                with archive.open(members[0]) as handle:
                    for values in csv.reader(io.TextIOWrapper(handle)):
                        if not values:
                            continue
                        stamp = int(values[0])
                        divisor = 1_000_000 if stamp >= 100_000_000_000_000 else 1000
                        ts = stamp // divisor
                        if start <= ts < end:
                            rows.append((ts, pair, *values[1:6]))
    temporary = output.with_suffix('.csv.part')
    with temporary.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        writer.writerows(sorted(rows, key=lambda r:(r[0],r[1])))
    load_period(temporary, name, spec, pairs)
    temporary.replace(output)
    (root / f"{name}.source.json").write_text(json.dumps({
        "period":name, "csv_sha256":digest(output), "archives":provenance,
        "quote_currency_assumption":"BTCUSDT/ETHUSDT treated as BTC/USD/ETH/USD; USDT assumed equal to USD"
    }, indent=2))
    return output
