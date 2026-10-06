import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from decimal import Decimal
import urllib.error

from trading_bot.client import APIError, AmbiguousOrder, Client, RateLimiter, signature
from trading_bot.config import Config, load
from trading_bot.demo import DemoClient
from trading_bot.engine import Engine
from trading_bot.risk import Quote, equity, normalize_wallet, plan
from trading_bot.state import ProcessLock, State
from trading_bot.strategy import target_weight


class ClientTests(unittest.TestCase):
    def test_official_signature_vector(self):
        params = dict(timestamp=1580774512000, pair='BNB/USD', quantity=2000, side='BUY', type='MARKET')
        secret = 'S1XP1e3UZj6A7H5fATj0jNhqPxxdSJYdInClVN65XAbvqqMKjVHjA7PZj4W12oep'
        self.assertEqual(signature(params, secret), '20b7fd5550b67b3bf0c1684ed0f04885261db8fdabd38611e9e6af23c19b7fff')

    def test_timeout_does_not_retry_order(self):
        calls = []
        def opener(req, **kwargs):
            calls.append(req)
            raise TimeoutError()
        client = Client('key', 'secret', opener=opener, sleep=lambda _: None)
        with self.assertRaises(AmbiguousOrder):
            client.place_order('BTC/USD', 'BUY', Decimal('0.01'))
        self.assertEqual(len(calls), 1)

    def test_read_retries_and_signing(self):
        calls = []
        def opener(req, **kwargs):
            calls.append(req)
            if len(calls) < 3:
                raise urllib.error.URLError('offline')
            return io.BytesIO(b'{"Wallet":{"USD":{"Free":100,"Lock":0}}}')
        client = Client('key', 'secret', opener=opener, sleep=lambda _: None)
        self.assertEqual(client.balance()['USD']['Free'], 100)
        self.assertEqual(len(calls), 3)
        self.assertIn('Rst-api-key', dict(calls[-1].header_items()))

    def test_exchange_rejection(self):
        client = Client('key', 'secret', opener=lambda *_a, **_k: io.BytesIO(b'{"Success":false,"ErrMsg":"insufficient balance"}'))
        with self.assertRaises(APIError) as ctx:
            client.place_order('BTC/USD', 'BUY', Decimal('1'))
        self.assertNotIsInstance(ctx.exception, AmbiguousOrder)

    def test_malformed_order_response_is_ambiguous(self):
        client = Client('key', 'secret', opener=lambda *_a, **_k: io.BytesIO(b'not json'))
        with self.assertRaises(AmbiguousOrder):
            client.place_order('BTC/USD', 'BUY', Decimal('1'))

    def test_rate_limit_sliding_window(self):
        now = [0.0]
        waits = []
        def sleep(seconds):
            waits.append(seconds)
            now[0] += seconds
        limiter = RateLimiter(2, lambda: now[0], sleep)
        for _ in range(3):
            limiter.acquire()
        self.assertEqual(waits, [60])
        self.assertEqual(len(limiter.calls), 1)


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.quotes = {'BTC/USD': Quote(100, 99.99, 100.01)}
        self.rules = {'AmountPrecision': 3, 'MiniOrder': 1}

    def test_size_precision_and_cap(self):
        side, qty, price = plan('BTC/USD', .2, {'USD':100000}, {'USD':100000}, self.quotes, self.rules, 100000, False, self.cfg)
        self.assertEqual(side, 'BUY')
        self.assertEqual(qty.as_tuple().exponent, -3)
        self.assertLessEqual(float(qty)*price, 2000)

    def test_drawdown_blocks_buys_but_allows_exit(self):
        self.assertIsNone(plan('BTC/USD', .2, {'USD':100000}, {'USD':100000}, self.quotes, self.rules, 100000, True, self.cfg))
        order = plan('BTC/USD', 0, {'USD':80000, 'BTC':200}, {'USD':80000,'BTC':200}, self.quotes, self.rules, 100000, True, self.cfg)
        self.assertEqual(order[0], 'SELL')

    def test_cash_reserve_and_total_exposure(self):
        self.assertIsNone(plan('BTC/USD', .2, {'USD':20000}, {'USD':20000}, self.quotes, self.rules, 100000, False, self.cfg))
        self.assertIsNone(plan('BTC/USD', .2, {'USD':60000}, {'USD':60000}, self.quotes, self.rules, 100000, False, self.cfg))

    def test_locked_coins_not_sold(self):
        self.assertIsNone(plan('BTC/USD', 0, {'USD':80000, 'BTC':200}, {'USD':80000, 'BTC':0}, self.quotes, self.rules, 100000, False, self.cfg))

    def test_wide_spread_blocks_orders(self):
        self.quotes['BTC/USD'] = Quote(100, 99, 101)
        self.assertIsNone(plan('BTC/USD', .2, {'USD':100000}, {'USD':100000}, self.quotes, self.rules, 100000, False, self.cfg))

    def test_quote_validation(self):
        for price in (-1, float('nan'), float('inf'), 0):
            with self.assertRaises(ValueError):
                Quote.parse({'LastPrice':price, 'MaxBid':99, 'MinAsk':101})

    def test_missing_holding_quote_blocks_valuation(self):
        with self.assertRaises(ValueError):
            equity({'USD':10, 'DOGE':1}, self.quotes)

    def test_wallet_total_and_free(self):
        total, free = normalize_wallet({'USD':{'Free':100, 'Lock':10}})
        self.assertEqual(total['USD'],110)
        self.assertEqual(free['USD'],100)


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(fast_window=2, slow_window=4)

    def test_warmup_uptrend_and_downtrend(self):
        self.assertIsNone(target_weight([(0,100)],self.cfg)[0])
        history = [(i*300,100+i*10) for i in range(4)]
        self.assertEqual(target_weight(history,self.cfg)[0], .2)
        history = [(i*300,130-i*10) for i in range(4)]
        self.assertEqual(target_weight(history,self.cfg)[0], 0)

    def test_history_gap_requires_new_window(self):
        history = [(0,100),(300,110),(1200,120),(1500,130)]
        self.assertEqual(target_weight(history,self.cfg)[1], 'history_gap')

    def test_config_rejects_unsafe_values(self):
        for values in ({'interval_seconds':1},{'max_total_weight':.99},{'fee_rate':float('nan')},{'fast_window':2.5},{'pairs':('BTC/USD','BTC/USD')}):
            with self.assertRaises(ValueError):
                Config(**values)
        load('config/bot.toml')


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'bot.sqlite3'
        self.cfg = Config(fast_window=2, slow_window=4, rebalance_band=.001, signal_threshold=.001)
        self.state = State(self.path, 'paper', 100000)

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def test_offline_end_to_end_buy_sell_and_restart(self):
        client = DemoClient(self.cfg)
        engine = Engine(client,self.state,self.cfg)
        for _ in range(150):
            engine.cycle()
        sides = {r[0] for r in self.state.db.execute('SELECT side FROM orders')}
        self.assertEqual(sides, {'BUY','SELL'})
        before = self.state.get('paper_wallet')
        self.state.close()
        self.state = State(self.path,'paper',100000)
        self.assertEqual(self.state.get('paper_wallet'),before)
        self.assertGreaterEqual(before['USD'],0)
        self.assertFalse(self.state.unresolved())

    def test_restart_during_submission_blocks_new_orders(self):
        self.state.intent('BTC/USD','BUY',Decimal('.01'))
        engine = Engine(DemoClient(self.cfg),self.state,self.cfg)
        for _ in range(10):
            engine.cycle()
        self.assertEqual(self.state.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],1)

    def test_ambiguous_live_order_blocks_future_submissions(self):
        self.state.close()
        self.state = State(self.path.with_name('live.sqlite3'),'live',100000)
        class Uncertain:
            def place_order(self,*_):
                raise AmbiguousOrder('timeout')
        engine = Engine(Uncertain(),self.state,self.cfg,'live')
        engine.submit('BTC/USD','BUY',Decimal('.01'),100)
        self.assertEqual(len(self.state.unresolved()),1)
        self.assertEqual(self.state.db.execute('SELECT status FROM orders').fetchone()[0],'UNKNOWN')

    def test_pending_order_reconciles(self):
        local_id = self.state.intent('BTC/USD','BUY',Decimal('.01'))
        self.state.finish(local_id,'PENDING',{},123)
        class Reconciler:
            def query_order(self,_):
                return {'OrderMatched':[{'OrderID':123,'Status':'FILLED'}]}
        Engine(Reconciler(),self.state,self.cfg,'live').reconcile()
        self.assertFalse(self.state.unresolved())

    def test_stale_ticker_rejected_before_trade(self):
        client = DemoClient(self.cfg)
        original = client.ticker
        def stale():
            row = original()
            row['ServerTime'] -= 60000
            return row
        client.ticker = stale
        with self.assertRaises(ValueError):
            Engine(client,self.state,self.cfg).cycle()
        self.assertEqual(self.state.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)

    def test_drawdown_halt_survives_restart(self):
        self.state.set('high_water', 120000)
        Engine(DemoClient(self.cfg),self.state,self.cfg).cycle()
        self.assertTrue(self.state.get('drawdown_halt'))
        self.state.close()
        self.state = State(self.path,'paper',100000)
        self.assertTrue(self.state.get('drawdown_halt'))

    def test_one_order_per_cycle(self):
        client = DemoClient(self.cfg)
        engine = Engine(client,self.state,self.cfg)
        count = 0
        for _ in range(25):
            engine.cycle()
            current = self.state.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
            self.assertLessEqual(current - count, 1)
            count = current
        self.assertGreater(count, 0)

    def test_mode_cannot_share_database(self):
        with self.assertRaises(ValueError):
            State(self.path,'live',100000)

    def test_duplicate_process_lock(self):
        first = ProcessLock(Path(self.temp.name)/'bot.lock')
        try:
            with self.assertRaises(RuntimeError):
                ProcessLock(Path(self.temp.name)/'bot.lock')
        finally:
            first.close()

    def test_sample_bucket_deduplication(self):
        self.state.sample('BTC/USD',0,100,4)
        self.state.sample('BTC/USD',0,101,4)
        self.assertEqual(self.state.history('BTC/USD'),[(0,100)])


if __name__ == '__main__':
    unittest.main()
