import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from trading_bot.config import Config
from trading_bot.state import State
from trading_bot.warmup import fetch_closes, seed


class WarmupTests(unittest.TestCase):
    def fixture(self, state):
        cfg = Config(fast_window=2, slow_window=4)
        cutoff = 3000
        rows = [(t, 100.0) for t in range(1800, 3000, 300)]
        histories = {p: list(rows) for p in cfg.pairs}
        snapshot = {'ServerTime': 3010000, 'Data': {p: {'LastPrice': 100} for p in cfg.pairs}}
        return cfg, histories, cutoff, snapshot, 3010

    def test_seed_only_history_preserves_wallet_and_no_orders(self):
        with tempfile.TemporaryDirectory() as directory:
            state = State(Path(directory)/'state.db', 'live', 100000)
            try:
                original = state.get('paper_wallet')
                seed(state, *self.fixture(state))
                self.assertEqual(len(state.history('BTC/USD')), 4)
                self.assertEqual(state.history('BTC/USD')[-1], (3000,100.0))
                self.assertEqual(state.get('paper_wallet'), original)
                self.assertEqual(state.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 0)
                with self.assertRaises(ValueError): seed(state, *self.fixture(state))
            finally: state.close()

    def test_current_roostoo_sample_bridges_start_in_next_bucket(self):
        from trading_bot.strategy import target_weight
        with tempfile.TemporaryDirectory() as directory:
            state = State(Path(directory)/'state.db', 'paper', 100000)
            try:
                cfg,histories,cutoff,snapshot,now=self.fixture(state)
                snapshot['Data']['BTC/USD']['LastPrice']=101
                seed(state,cfg,histories,cutoff,snapshot,now)
                self.assertEqual(state.history('BTC/USD')[-1],(cutoff,101))
                state.sample('BTC/USD',cutoff+300,102,cfg.slow_window)
                _,reason=target_weight(state.history('BTC/USD'),cfg)
                self.assertNotIn(reason,('warming_up','history_gap'))
            finally: state.close()

    def test_gap_or_price_mismatch_in_second_pair_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            state = State(Path(directory)/'state.db', 'live', 100000)
            try:
                cfg, histories, cutoff, snapshot, now = self.fixture(state)
                histories['ETH/USD'] = histories['ETH/USD'][1:]
                with self.assertRaises(ValueError): seed(state,cfg,histories,cutoff,snapshot,now)
                self.assertEqual(state.history('BTC/USD'), [])
                cfg, histories, cutoff, snapshot, now = self.fixture(state)
                snapshot['Data']['ETH/USD']['LastPrice'] = 80
                with self.assertRaises(ValueError): seed(state,cfg,histories,cutoff,snapshot,now)
                self.assertEqual(state.history('BTC/USD'), [])
            finally: state.close()

    def test_stale_seed_and_used_journal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            state = State(Path(directory)/'state.db', 'live', 100000)
            try:
                cfg,histories,cutoff,snapshot,now=self.fixture(state)
                with self.assertRaises(ValueError): seed(state,cfg,histories,cutoff,snapshot,now+300)
                state.intent('BTC/USD','BUY','0.01')
                with self.assertRaises(ValueError): seed(state,cfg,histories,cutoff,snapshot,now)
                self.assertEqual(state.history('BTC/USD'), [])
            finally: state.close()

    def test_public_fetch_rejects_unfinished_or_missing_bars(self):
        def opener(url, timeout):
            return io.BytesIO(json.dumps([[1800000,0,0,0,'100',0,2099999],
                [2100000,0,0,0,'100',0,2399999]]).encode())
        rows,_=fetch_closes('BTC/USD',2,2400,opener)
        self.assertEqual(rows,[(1800,100),(2100,100)])
        with self.assertRaises(ValueError): fetch_closes('BTC/USD',2,2700,opener)
        def unfinished(url,timeout):
            return io.BytesIO(json.dumps([[1800000,0,0,0,'100',0,2400000]]).encode())
        with self.assertRaises(ValueError): fetch_closes('BTC/USD',2,2400,unfinished)

    def test_immediate_paper_check_is_rejected_in_live_mode(self):
        from trading_bot.warmup import main
        with patch('sys.argv',['warmup','--config','config/bot.toml','--mode','live','--state-dir','unused','--paper-check']), patch('sys.stderr',io.StringIO()), patch('trading_bot.warmup.Client') as client:
            with self.assertRaises(SystemExit) as raised: main()
            self.assertEqual(raised.exception.code,2)
            client.assert_not_called()


if __name__ == '__main__': unittest.main()
