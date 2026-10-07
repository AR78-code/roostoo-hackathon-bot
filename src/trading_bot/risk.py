from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
import math


@dataclass(frozen=True)
class Quote:
    last: float
    bid: float
    ask: float

    @classmethod
    def parse(cls, row):
        quote = cls(float(row["LastPrice"]), float(row["MaxBid"]), float(row["MinAsk"]))
        if any(not math.isfinite(v) or v <= 0 for v in (quote.last, quote.bid, quote.ask)) or quote.ask < quote.bid:
            raise ValueError("Invalid price or crossed quote")
        return quote

    @property
    def spread(self):
        return (self.ask - self.bid) / self.last


def normalize_wallet(raw):
    wallet, free = {}, {}
    for coin, balance in raw.items():
        available, locked = float(balance["Free"]), float(balance["Lock"])
        if not math.isfinite(available) or not math.isfinite(locked) or available < -0.02 or locked < 0:
            raise ValueError("Invalid wallet balance")
        free[coin] = max(0, available)
        wallet[coin] = max(0, available) + locked
    return wallet, free


def equity(wallet, quotes):
    result = wallet.get("USD", 0)
    for coin, qty in wallet.items():
        if coin == "USD" or qty == 0:
            continue
        pair = coin + "/USD"
        if pair not in quotes:
            raise ValueError(f"Cannot value holding {coin}; missing quote")
        result += qty * quotes[pair].last
    if not math.isfinite(result) or result <= 0:
        raise ValueError("Invalid portfolio equity")
    return result


def plan(pair, weight, wallet, free, quotes, rules, total, halted, cfg):
    if weight is None:
        return None
    quote = quotes[pair]
    if quote.spread > cfg.max_spread:
        return None
    coin = pair.split("/")[0]
    held = wallet.get(coin, 0) * quote.last
    delta = weight * total - held
    # The allocation deadband limits incidental rebalancing, but a deliberate
    # cash target should unwind holdings down to exchange/order-size dust.
    threshold = cfg.min_order_usd if weight == 0 else max(cfg.min_order_usd, cfg.rebalance_band * total)
    if abs(delta) < threshold:
        return None
    side = "BUY" if delta > 0 else "SELL"
    price = quote.ask * (1 + cfg.slippage) if side == "BUY" else quote.bid * (1 - cfg.slippage)
    budget = min(abs(delta), cfg.max_order_usd)
    if side == "BUY":
        if halted:
            return None
        invested = total - wallet.get("USD", 0)
        budget = min(budget, (cfg.max_pair_weight * total - held) / (1 + cfg.fee_rate),
                     (cfg.max_total_weight * total - invested) / (1 + cfg.fee_rate),
                     (free.get("USD", 0) - cfg.cash_reserve * total) / (1 + cfg.fee_rate))
        raw_qty = max(0, budget) / price
    else:
        raw_qty = min(max(0, budget) / price, free.get(coin, 0))
    precision = int(rules["AmountPrecision"])
    if not 0 <= precision <= 18:
        raise ValueError("Invalid quantity precision")
    qty = Decimal(str(raw_qty)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_DOWN)
    minimum = max(cfg.min_order_usd, float(rules["MiniOrder"]))
    if qty <= 0 or float(qty) * price <= minimum:
        return None
    return side, qty, price
