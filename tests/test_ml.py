from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
import math
from trading_bot.config import Config
from trading_bot.ml import FEATURE_NAMES,LOOKBACK,features,load_model,probability,expected_return
from trading_bot.strategy import target_weight
from trading_bot.backtesting import cli
from trading_bot.backtesting.simulator import simulate
from test_backtesting import spec,frames,write_frames
from trading_bot.backtesting.data import utc_date


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'model.json'
        self.model={'feature_names':list(FEATURE_NAMES),'interval_seconds':300,'mean':[0]*7,'scale':[1]*7,'coefficients':[0]*7,'intercept':2,'available_at':0}
        self.path.write_text(json.dumps(self.model))
        self.cfg=Config(strategy='logistic',slow_window=LOOKBACK,model_path=str(self.path))
        self.history=[(i*300,100+i*.01) for i in range(LOOKBACK)]

    def tearDown(self):load_model.cache_clear();self.temp.cleanup()

    def test_features_use_price_prefix_only(self):
        prices=[row[1] for row in self.history]
        before=features(prices)
        future=prices+[10000]*10
        self.assertEqual(features(future[:LOOKBACK]),before)
        self.assertEqual(len(before),len(FEATURE_NAMES))
        with self.assertRaises(ValueError):features(prices[:-1])

    def test_ridge_thresholds_and_artifact_type(self):
        self.model.update(model_type='ridge',intercept=.004)
        self.path.write_text(json.dumps(self.model))
        cfg=replace(self.cfg,strategy='ridge')
        self.assertEqual(expected_return(self.history,cfg),.004)
        self.assertEqual(target_weight(self.history,cfg),(.2,'ridge_entry'))
        self.assertEqual(target_weight(self.history,replace(cfg,model_entry_return=.005)),(None,'ridge_hold'))
        self.model['intercept']=-.001;self.path.write_text(json.dumps(self.model))
        self.assertEqual(target_weight(self.history,cfg),(0.0,'ridge_exit'))
        with self.assertRaises(ValueError):probability(self.history,self.cfg)
        with self.assertRaises(ValueError):replace(cfg,model_exit_return=.006)

    def test_ridge_future_artifact_and_freeze_integrity(self):
        self.model.update(model_type='ridge',intercept=.004,available_at=self.history[-1][0]+600)
        self.path.write_text(json.dumps(self.model))
        cfg=replace(self.cfg,strategy='ridge')
        with self.assertRaises(ValueError):expected_return(self.history,cfg)
        self.model['available_at']=0;self.path.write_text(json.dumps(self.model));self.cfg=cfg
        self.test_freeze_and_final_detect_model_replacement()

    def test_chronological_model_updates_preserve_prior_trades(self):
        self.model.update(model_type='ridge',intercept=.004)
        self.path.write_text(json.dumps(self.model))
        cfg=replace(self.cfg,strategy='ridge')
        data=frames(20,start=1000000)
        warm=frames(LOOKBACK,start=1000000-LOOKBACK*300)
        baseline=simulate(data,cfg,spec(),warm)
        later_path=self.root/'later.json'
        self.model.update(intercept=-.004,available_at=data[5]['BTC/USD'].timestamp-1)
        later_path.write_text(json.dumps(self.model))
        later=replace(cfg,model_path=str(later_path))
        effective=data[5]['BTC/USD'].timestamp-1e-6
        changed=simulate(data,cfg,spec(),warm,[(effective,later)])
        cutoff=data[5]['BTC/USD'].timestamp
        self.assertEqual([t for t in baseline.trades if t['timestamp']<cutoff],
                         [t for t in changed.trades if t['timestamp']<cutoff])
        exits=[t for t in changed.trades if t['reason']=='ridge_exit']
        self.assertTrue(exits)
        self.assertEqual(exits[0]['timestamp'],cutoff)
        self.assertNotEqual(changed.curve[5]['cash'],cfg.paper_cash)
        with self.assertRaises(ValueError):simulate(data,cfg,spec(),warm,[(effective,replace(later,max_drawdown=.2))])
        with self.assertRaises(ValueError):simulate(data,cfg,spec(),warm,[(effective,later),(effective,later)])
        with self.assertRaises(ValueError):simulate(data,cfg,spec(),warm,[(float('nan'),later)])

    def test_model_prediction_and_policy_threshold(self):
        self.assertAlmostEqual(probability(self.history,self.cfg),.8807970779778823)
        self.assertEqual(target_weight(self.history,self.cfg),(.2,'model_entry'))

    def test_scaled_allocation_is_bounded_and_rejects_future_model(self):
        cfg=replace(self.cfg,strategy='logistic_scaled',model_exit_probability=.5)
        for score,weight in ((.4,0),(.5,0),(.55,.1),(.6,.2),(.9,.2)):
            self.model['intercept']=math.log(score/(1-score))
            self.path.write_text(json.dumps(self.model))
            actual,reason=target_weight(self.history,cfg)
            self.assertAlmostEqual(actual,weight)
            self.assertEqual(reason,'model_scaled')
        self.model['available_at']=self.history[-1][0]+600
        self.path.write_text(json.dumps(self.model))
        with self.assertRaises(ValueError):target_weight(self.history,cfg)
        self.assertEqual(target_weight(self.history[:-1],cfg),(None,'warming_up'))

    def test_scaled_artifact_freeze_integrity(self):
        self.cfg=replace(self.cfg,strategy='logistic_scaled')
        self.test_freeze_and_final_detect_model_replacement()

    def test_trend_filter_rejects_downtrend_despite_confident_model(self):
        cfg=replace(self.cfg,strategy='logistic_trend')
        self.assertEqual(target_weight(self.history,cfg),(.2,'model_entry'))
        falling=[(i*300,120-i*.01) for i in range(LOOKBACK)]
        self.assertEqual(target_weight(falling,cfg),(0.0,'model_trend_exit'))
        self.model['available_at']=self.history[-1][0]+600
        self.path.write_text(json.dumps(self.model))
        with self.assertRaises(ValueError):target_weight(self.history,cfg)

    def test_trend_artifact_freeze_integrity(self):
        self.cfg=replace(self.cfg,strategy='logistic_trend')
        self.test_freeze_and_final_detect_model_replacement()

    def test_future_trained_model_rejected(self):
        self.model['available_at']=self.history[-1][0]+600
        self.path.write_text(json.dumps(self.model))
        with self.assertRaises(ValueError):probability(self.history,self.cfg)

    def test_replaced_artifact_is_not_stale_in_cache(self):
        self.assertGreater(probability(self.history,self.cfg),.8)
        self.model['intercept']=-2
        self.path.write_text(json.dumps(self.model))
        self.assertLess(probability(self.history,self.cfg),.2)
        self.model['available_at']=self.history[-1][0]+600
        self.path.write_text(json.dumps(self.model))
        with self.assertRaises(ValueError):probability(self.history,self.cfg)

    def test_invalid_model_schema_rejected(self):
        self.model['scale'][0]=0;self.path.write_text(json.dumps(self.model))
        with self.assertRaises(ValueError):load_model(str(self.path))

    def test_invalid_probability_policy_rejected(self):
        with self.assertRaises(ValueError):replace(self.cfg,model_exit_probability=.7)
        with self.assertRaises(ValueError):replace(self.cfg,model_path='')
        with self.assertRaises(ValueError):replace(self.cfg,interval_seconds=3600)

    def test_freeze_and_final_detect_model_replacement(self):
        specification=spec()
        for period in ('development','validation'):
            write_frames(self.root/f'{period}.csv',frames(start=utc_date(specification[period]['start'])))
        report=self.root/'report';selection=self.root/'selection.json'
        cli.research(self.root,report,self.cfg,specification)
        cli.freeze(self.root,report,selection,self.cfg,specification)
        self.path.write_text(self.path.read_text()+'\n')
        with self.assertRaises(ValueError):cli.final(self.root,self.root/'final',selection,True)
        self.assertFalse((self.root/'test-access.json').exists())

    def test_freeze_detects_change_after_research(self):
        specification=spec()
        for period in ('development','validation'):
            write_frames(self.root/f'{period}.csv',frames(start=utc_date(specification[period]['start'])))
        report=self.root/'report';selection=self.root/'selection.json'
        cli.research(self.root,report,self.cfg,specification)
        self.path.write_text(self.path.read_text()+'\n')
        with self.assertRaises(ValueError):cli.freeze(self.root,report,selection,self.cfg,specification)


if __name__=='__main__':unittest.main()
