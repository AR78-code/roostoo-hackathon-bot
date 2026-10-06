from dataclasses import replace
import math
import unittest
from trading_bot.config import Config
from trading_bot.strategy import allocation, target_weight,rotation_targets
from trading_bot.backtesting.simulator import simulate
from test_backtesting import frames,spec


class ResearchPolicyTests(unittest.TestCase):
    def test_rotation_selects_strongest_eligible_asset(self):
        cfg=Config(strategy='rotation',fast_window=2,slow_window=4,signal_threshold=.006)
        histories={'BTC/USD':[(i*300,p) for i,p in enumerate([100,110,115,120])],
                   'ETH/USD':[(i*300,p) for i,p in enumerate([100,102,103,104])]}
        self.assertEqual(rotation_targets(histories,cfg),[('BTC/USD',.2,'rotation_entry'),('ETH/USD',0.0,'rotation_exit')])
        histories={pair:[(i*300,p) for i,p in enumerate([110,105,100,95])] for pair in cfg.pairs}
        self.assertTrue(all(weight==0 for _,weight,_ in rotation_targets(histories,cfg)))
        with self.assertRaises(ValueError):target_weight(histories['BTC/USD'],cfg)

    def test_rotation_ties_hold_and_alignment_is_required(self):
        cfg=Config(strategy='rotation',fast_window=2,slow_window=4,signal_threshold=.006)
        histories={pair:[(i*300,p) for i,p in enumerate([100,101,102,103])] for pair in cfg.pairs}
        self.assertTrue(all(weight is None for _,weight,_ in rotation_targets(histories,cfg)))
        histories['ETH/USD'][-1]=(901,103)
        self.assertTrue(all(reason=='unaligned_history' for _,_,reason in rotation_targets(histories,cfg)))
        with self.assertRaises(ValueError):replace(cfg,pairs=('BTC/USD',))

    def test_rotation_future_prices_do_not_change_past_trades(self):
        cfg=Config(strategy='rotation',fast_window=2,slow_window=4,signal_threshold=.006)
        data=frames(30)
        for i,f in enumerate(data):
            bar=f['ETH/USD'];price=(100-i*2)*.05
            f['ETH/USD']=replace(bar,open=price,high=price+.05,low=price-.05,close=price-.05)
        changed=[dict(f) for f in data]
        for f in changed[20:]:
            bar=f['ETH/USD'];f['ETH/USD']=replace(bar,open=bar.open*3,high=bar.high*3,low=bar.low*3,close=bar.close*3)
        before=simulate(data,cfg,spec());after=simulate(changed,cfg,spec())
        cutoff=data[20]['BTC/USD'].timestamp
        self.assertTrue([t for t in before.trades if t['timestamp']<cutoff])
        self.assertEqual([t for t in before.trades if t['timestamp']<cutoff],[t for t in after.trades if t['timestamp']<cutoff])
        self.assertEqual(before.curve[:21],after.curve[:21])
    def test_pullback_requires_long_trend_and_exits_at_recovery(self):
        cfg=Config(strategy='pullback',fast_window=3,slow_window=6,signal_threshold=.01)
        history=[(i*300,p) for i,p in enumerate([90,90,100,110,110,105])]
        self.assertEqual(target_weight(history,cfg),(.2,'pullback_entry'))
        history[-1]=(1500,111)
        self.assertEqual(target_weight(history,cfg),(0.0,'pullback_recovery_exit'))
        history[-1]=(1500,90)
        self.assertEqual(target_weight(history,cfg),(0.0,'pullback_trend_exit'))
    def test_default_baseline_unchanged(self):
        cfg=Config(fast_window=2,slow_window=4)
        history=[(i*300,100+i*10) for i in range(4)]
        self.assertEqual(target_weight(history,cfg),(.2,'uptrend'))
        self.assertEqual(target_weight(list(zip([0,300,600,900],[130,120,110,100])),cfg),(0.0,'downtrend'))

    def test_breakout_uses_previous_high_not_current_high(self):
        cfg=Config(strategy='breakout',fast_window=3,slow_window=5,signal_threshold=.001)
        history=[(i*300,p) for i,p in enumerate([100,101,102,103,105])]
        self.assertEqual(target_weight(history,cfg),(.2,'breakout_entry'))
        falling=[(i*300,p) for i,p in enumerate([100,103,102,101,99])]
        self.assertEqual(target_weight(falling,cfg),(0.0,'breakout_exit'))

    def test_breakout_neutral_holds(self):
        cfg=Config(strategy='breakout',fast_window=3,slow_window=5)
        history=[(i*300,p) for i,p in enumerate([100,103,101,102,102])]
        self.assertIsNone(target_weight(history,cfg)[0])

    def test_volatile_market_reduces_target_without_leverage(self):
        cfg=Config(slow_window=576,volatility_target=.01)
        prices=[100*math.exp((.03 if i%2 else -.03)) for i in range(576)]
        self.assertGreater(allocation(prices,cfg),0)
        self.assertLess(allocation(prices,cfg),cfg.max_pair_weight)
        self.assertEqual(allocation([100]*576,cfg),cfg.max_pair_weight)

    def test_invalid_strategy_or_short_vol_history_rejected(self):
        with self.assertRaises(ValueError):Config(strategy='unknown')
        with self.assertRaises(ValueError):Config(volatility_target=.01)
        with self.assertRaises(ValueError):Config(volatility_target=float('nan'))


if __name__=='__main__':unittest.main()
