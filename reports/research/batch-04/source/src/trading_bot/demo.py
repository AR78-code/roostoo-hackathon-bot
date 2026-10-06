"""Deterministic offline exchange for exercising the complete paper path."""
import time


class DemoClient:
    offset_ms = 0

    def __init__(self, config):
        self.config = config
        self.index = 0
        self.now = time.time()

    def sync_clock(self):
        self.now += self.config.interval_seconds
        self.offset_ms = int((self.now - time.time()) * 1000)

    def exchange_info(self):
        return {"IsRunning": True, "TradePairs": {p: {"CanTrade": True, "AmountPrecision": 6, "MiniOrder": 1} for p in self.config.pairs}}

    def ticker(self):
        self.index += 1
        phase = self.index % 160
        factor = 1 + min(phase, 80) * .003 if phase <= 80 else 1.24 - (phase - 80) * .004
        data = {}
        for p in self.config.pairs:
            price = (60000 if p.startswith("BTC") else 3000) * factor
            data[p] = {"LastPrice": price, "MaxBid": price * .9999, "MinAsk": price * 1.0001}
        return {"Success": True, "ServerTime": int(self.now * 1000), "Data": data}
