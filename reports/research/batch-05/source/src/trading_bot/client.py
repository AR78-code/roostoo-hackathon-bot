"""Read calls retry; order placement never retries an ambiguous request."""
from collections import deque
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


class APIError(RuntimeError):
    pass


class AmbiguousOrder(APIError):
    pass


def canonical(params):
    return "&".join(f"{key}={params[key]}" for key in sorted(params))


def signature(params, secret):
    return hmac.new(secret.encode(), canonical(params).encode(), hashlib.sha256).hexdigest()


class RateLimiter:
    def __init__(self, limit=25, clock=time.monotonic, sleep=time.sleep):
        self.limit, self.clock, self.sleep = limit, clock, sleep
        self.calls = deque()

    def acquire(self):
        while True:
            now = self.clock()
            while self.calls and now - self.calls[0] >= 60:
                self.calls.popleft()
            if len(self.calls) < self.limit:
                self.calls.append(now)
                return
            self.sleep(max(0.01, 60 - (now - self.calls[0])))


class Client:
    BASE_URL = "https://mock-api.roostoo.com"

    def __init__(self, key=None, secret=None, opener=urllib.request.urlopen, sleep=time.sleep):
        self.key = key if key is not None else os.getenv("ROOSTOO_API_KEY", "")
        self.secret = secret if secret is not None else os.getenv("ROOSTOO_SECRET_KEY", "")
        self.opener, self.sleep = opener, sleep
        self.limiter = RateLimiter(sleep=sleep)
        self.offset_ms = 0

    def request(self, method, path, params=None, signed=False, timestamp=True, mutation=False):
        if signed and (not self.key or not self.secret):
            raise APIError("ROOSTOO_API_KEY and ROOSTOO_SECRET_KEY are required")
        attempts = 1 if mutation else 3
        for attempt in range(attempts):
            self.limiter.acquire()
            payload = dict(params or {})
            if timestamp:
                payload["timestamp"] = int(time.time() * 1000) + self.offset_ms
            headers = {"Accept": "application/json", "User-Agent": "roostoo-hackathon-bot/0.1"}
            if signed:
                headers.update({"RST-API-KEY": self.key, "MSG-SIGNATURE": signature(payload, self.secret)})
            encoded = urllib.parse.urlencode(sorted(payload.items())).encode()
            url = self.BASE_URL + path
            body = None
            if method == "GET" and payload:
                url += "?" + encoded.decode()
            elif method == "POST":
                body = encoded
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            req = urllib.request.Request(url, body, headers, method=method)
            try:
                with self.opener(req, timeout=10) as response:
                    result = json.loads(response.read())
                if not isinstance(result, dict):
                    raise ValueError("Expected an API object")
            except urllib.error.HTTPError as exc:
                if mutation:
                    raise AmbiguousOrder(f"Order HTTP {exc.code}; reconciliation required") from None
                if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                    raise APIError(f"API HTTP {exc.code} on {path}") from None
                self.sleep(2 ** attempt)
                continue
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                if mutation:
                    raise AmbiguousOrder("Order response unavailable; reconciliation required") from None
                if attempt == attempts - 1:
                    raise APIError(f"Read request failed on {path}: {type(exc).__name__}") from None
                self.sleep(2 ** attempt)
                continue
            if result.get("Success") is False:
                # Explicit exchange rejection is distinguishable from transport uncertainty.
                raise APIError(f"Exchange rejected {path}: {str(result.get('ErrMsg', 'unknown'))[:200]}")
            return result
        raise APIError("Read retries exhausted")

    def sync_clock(self):
        start = time.time() * 1000
        response = self.request("GET", "/v3/serverTime", timestamp=False)
        end = time.time() * 1000
        self.offset_ms = int(response["ServerTime"] - (start + end) / 2)

    def exchange_info(self):
        return self.request("GET", "/v3/exchangeInfo", timestamp=False)

    def ticker(self):
        return self.request("GET", "/v3/ticker")

    def balance(self):
        return self.request("GET", "/v3/balance", signed=True)["Wallet"]

    def query_order(self, order_id):
        return self.request("POST", "/v3/query_order", {"order_id": str(order_id)}, signed=True)

    def place_order(self, pair, side, quantity):
        return self.request("POST", "/v3/place_order", {
            "pair": pair, "side": side, "type": "MARKET", "quantity": format(quantity, "f")
        }, signed=True, mutation=True)
