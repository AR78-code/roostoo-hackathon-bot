import logging
import math
import time

from .client import APIError, AmbiguousOrder
from .risk import Quote, equity, normalize_wallet, plan
from .strategy import target_weight

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, client, state, config, mode="paper"):
        self.client, self.state, self.cfg, self.mode = client, state, config, mode

    def reconcile(self):
        for local_id, exchange_id in self.state.unresolved():
            if exchange_id is None:
                log.error("Uncertain order %s has no exchange ID; orders remain blocked", local_id)
                continue
            try:
                rows = self.client.query_order(exchange_id)["OrderMatched"]
                matching = [row for row in rows if str(row["OrderID"]) == exchange_id]
                if len(matching) != 1:
                    raise ValueError("Order query did not uniquely match")
                row = matching[0]
                status = row["Status"]
                if status in ("FILLED", "CANCELED", "REJECTED"):
                    self.state.finish(local_id, status, row, exchange_id)
                    self.state.event("reconciled", {"local_id": local_id, "status": status})
            except (APIError, KeyError, ValueError, TypeError):
                log.error("Reconciliation failed for local order %s", local_id)

    def submit(self, pair, side, qty, price):
        local_id = self.state.intent(pair, side, qty)
        if self.mode != "live":
            wallet = self.state.get("paper_wallet")
            coin = pair.split("/")[0]
            notional, fee = float(qty) * price, float(qty) * price * self.cfg.fee_rate
            if side == "BUY":
                wallet["USD"] -= notional + fee
                wallet[coin] = wallet.get(coin, 0) + float(qty)
            else:
                wallet["USD"] += notional - fee
                wallet[coin] = wallet.get(coin, 0) - float(qty)
            self.state.finish(local_id, "FILLED", {"paper": True, "price": price, "fee": fee}, wallet=wallet)
        else:
            try:
                response = self.client.place_order(pair, side, qty)
                row = response["OrderDetail"]
                exchange_id = row["OrderID"]
                status = row["Status"]
                if status not in ("FILLED", "CANCELED", "REJECTED", "PENDING"):
                    status = "UNKNOWN"
                self.state.finish(local_id, status, row, exchange_id)
            except AmbiguousOrder:
                self.state.finish(local_id, "UNKNOWN", {"reason": "ambiguous_response"})
                log.error("Order %s uncertain; subsequent orders blocked", local_id)
                return
            except APIError:
                self.state.finish(local_id, "REJECTED", {"reason": "exchange_rejection"})
                raise
            except (KeyError, ValueError, TypeError):
                self.state.finish(local_id, "UNKNOWN", {"reason": "malformed_response"})
                return
        self.state.event("order", {"local_id": local_id, "pair": pair, "side": side, "quantity": str(qty), "mode": self.mode})
        log.info("%s %s %s quantity=%s", self.mode, side, pair, qty)

    def cycle(self):
        self.client.sync_clock()
        info = self.client.exchange_info()
        if info.get("IsRunning") is not True:
            raise ValueError("Exchange is not running")
        rules = info["TradePairs"]
        for pair in self.cfg.pairs:
            if pair not in rules or rules[pair].get("CanTrade") is not True:
                raise ValueError(f"Pair unavailable: {pair}")
        if self.mode == "live":
            self.reconcile()
        snapshot = self.client.ticker()
        received = time.time()
        server_ms = float(snapshot["ServerTime"])
        age = (received * 1000 + self.client.offset_ms - server_ms) / 1000
        if not math.isfinite(age) or age > self.cfg.max_quote_age_seconds or age < -5:
            raise ValueError("Ticker snapshot is stale or timestamp is invalid")
        quotes = {pair: Quote.parse(row) for pair, row in snapshot["Data"].items()}
        for pair in self.cfg.pairs:
            if pair not in quotes:
                raise ValueError(f"Missing ticker: {pair}")
        # One sample per polling bucket, using local UTC time corrected to server time.
        ts = int(server_ms / 1000 // self.cfg.interval_seconds) * self.cfg.interval_seconds
        for pair in self.cfg.pairs:
            self.state.sample(pair, ts, quotes[pair].last, self.cfg.slow_window)
        if self.mode == "live":
            wallet, free = normalize_wallet(self.client.balance())
        else:
            wallet = self.state.get("paper_wallet")
            free = dict(wallet)
        total = equity(wallet, quotes)
        high = max(total, self.state.get("high_water", total))
        self.state.set("high_water", high)
        if (high - total) / high >= self.cfg.max_drawdown:
            self.state.set("drawdown_halt", True)
        halted = self.state.get("drawdown_halt", False)
        self.state.event("portfolio", {"equity": total, "drawdown": (high - total) / high, "buy_halt": halted, "mode": self.mode})
        decisions = []
        for pair in self.cfg.pairs:
            target, reason = target_weight(self.state.history(pair), self.cfg)
            decisions.append({"pair": pair, "target": target, "reason": reason})
        self.state.event("signals", decisions)
        if self.state.unresolved():
            log.error("Orders blocked by unresolved journal entries")
            return total
        # At most one market order each polling cycle; refresh balance next cycle.
        for decision in sorted(decisions, key=lambda d: d["target"] if d["target"] is not None else 1):
            order = plan(decision["pair"], decision["target"], wallet, free, quotes, rules[decision["pair"]], total, halted, self.cfg)
            if order:
                if (time.time() - received) > self.cfg.max_quote_age_seconds:
                    raise ValueError("Quote expired before execution")
                self.submit(decision["pair"], *order)
                break
        log.info("cycle equity=%.2f buy_halt=%s signals=%s", total, halted, decisions)
        self.state.set("last_success", time.time())
        return total
