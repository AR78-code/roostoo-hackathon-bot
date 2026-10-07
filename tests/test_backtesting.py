import csv
from dataclasses import replace
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from trading_bot.config import Config
from trading_bot.backtesting import cli
from trading_bot.backtesting.data import Bar, FIELDS, fetch_period, load_period, utc_date, validate_spec
from trading_bot.backtesting.metrics import composite_score, daily_returns, metrics
from trading_bot.backtesting.simulator import Result, benchmark, run_all, simulate


def spec():
    return {'interval_seconds':300,'spread_bps':2.0,'amount_precision':6,'exchange_min_order':1.0,
        'development':{'start':'2025-01-01','end':'2025-01-02'},
        'validation':{'start':'2025-01-02','end':'2025-01-03'},
        'test':{'start':'2025-01-03','end':'2025-01-04'}}


def frames(count=288,start=None):
    start=utc_date('2025-01-01') if start is None else start
    result=[]
    for i in range(count):
        frame={}
        for pair,mult in [('BTC/USD',1),('ETH/USD',.05)]:
            opening=(100+i)*mult
            close=(101+i)*mult
            frame[pair]=Bar(start+i*300,pair,opening,close,opening,close,1000)
        result.append(frame)
    return result


def write_frames(path,data):
    with Path(path).open('w',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(FIELDS)
        for frame in data:
            for pair,bar in frame.items():
                writer.writerow((bar.timestamp,pair,bar.open,bar.high,bar.low,bar.close,bar.volume))


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.cfg=Config(fast_window=2,slow_window=4,signal_threshold=.001,rebalance_band=.001)
        self.spec=spec()

    def test_next_open_execution_and_signal_precedes_fill(self):
        data=frames(12)
        result=simulate(data,self.cfg,self.spec)
        trade=result.trades[0]
        self.assertEqual(trade['timestamp'],data[4]['BTC/USD'].timestamp)
        self.assertLess(trade['signal_timestamp'],trade['timestamp'])
        expected=data[4]['BTC/USD'].open*(1+.0001)*(1+self.cfg.slippage)
        self.assertAlmostEqual(trade['price'],expected)
        self.assertGreater(trade['fee'],0)

    def test_current_bar_close_cannot_change_current_open_order(self):
        data=frames(15)
        baseline=simulate(data,self.cfg,self.spec)
        changed=[dict(f) for f in data]
        bar=changed[4]['BTC/USD']
        changed[4]['BTC/USD']=replace(bar,high=10000,close=10000)
        other=simulate(changed,self.cfg,self.spec)
        self.assertEqual(baseline.trades[0],other.trades[0])

    def test_future_changes_do_not_change_past_decisions(self):
        data=frames(30)
        changed=[dict(f) for f in data]
        for frame in changed[20:]:
            for p,b in frame.items():
                frame[p]=replace(b,open=b.open*3,high=b.high*3,low=b.low*3,close=b.close*3)
        a=simulate(data,self.cfg,self.spec)
        b=simulate(changed,self.cfg,self.spec)
        cutoff=data[20]['BTC/USD'].timestamp
        self.assertEqual([t for t in a.trades if t['timestamp']<cutoff],[t for t in b.trades if t['timestamp']<cutoff])
        self.assertEqual(a.curve[:21],b.curve[:21])

    def test_reuses_actual_strategy_and_risk(self):
        with patch('trading_bot.backtesting.simulator.target_weight',return_value=(.2,'test_signal')) as strategy, patch('trading_bot.backtesting.simulator.plan',return_value=None) as risk:
            result=simulate(frames(10),self.cfg,self.spec)
        self.assertTrue(strategy.called)
        self.assertTrue(risk.called)
        self.assertEqual(result.trades,[])

    def test_one_strategy_order_each_bar(self):
        result=simulate(frames(100),self.cfg,self.spec)
        timestamps=[t['timestamp'] for t in result.trades if t['reason']!='terminal_liquidation']
        self.assertEqual(len(timestamps),len(set(timestamps)))

    def test_terminal_liquidation_and_costs(self):
        data=frames(4)
        result=benchmark(data,self.cfg,self.spec,'btc',{'BTC/USD':1})
        entry,exit=result.trades
        self.assertEqual(exit['reason'],'terminal_liquidation')
        expected=self.cfg.paper_cash-entry['notional']-entry['fee']+exit['notional']-exit['fee']
        self.assertAlmostEqual(result.curve[-1]['equity'],expected)
        self.assertEqual(result.curve[-1]['exposure'],0)

    def test_costs_reduce_flat_market_returns(self):
        data=frames(10)
        for frame in data:
            for p,b in frame.items():
                frame[p]=replace(b,open=100,high=100,low=100,close=100)
        result=benchmark(data,self.cfg,self.spec,'btc',{'BTC/USD':1})
        self.assertLess(metrics(result)['net_return'],0)
        free_cfg=replace(self.cfg,fee_rate=0,slippage=0)
        no_spread={**self.spec,'spread_bps':0}
        free=benchmark(data,free_cfg,no_spread,'btc',{'BTC/USD':1})
        self.assertAlmostEqual(metrics(free)['net_return'],0)

    def test_benchmarks_and_allocation_weights(self):
        results=run_all(frames(10),self.cfg,self.spec)
        self.assertEqual([r.name for r in results],['strategy','cash','btc_buy_hold','allocation_matched'])
        self.assertEqual(metrics(results[1])['net_return'],0)
        self.assertEqual(metrics(results[1])['fees'],0)
        matched=results[3]
        entry_spending=sum(t['notional']+t['fee'] for t in matched.trades if t['reason']=='benchmark_entry')
        self.assertAlmostEqual(entry_spending/self.cfg.paper_cash,.4,places=7)

    def test_future_warmup_rejected(self):
        data=frames(10)
        with self.assertRaises(ValueError):simulate(data,self.cfg,self.spec,frames(4,start=data[-1]['BTC/USD'].timestamp+300))

    def test_prior_only_warmup(self):
        earlier=frames(4)
        later=frames(10,start=earlier[-1]['BTC/USD'].timestamp+300)
        result=simulate(later,self.cfg,self.spec,earlier)
        self.assertEqual(result.trades[0]['timestamp'],later[0]['BTC/USD'].timestamp)
        self.assertLess(result.trades[0]['signal_timestamp'],result.trades[0]['timestamp'])

    def test_drawdown_latches_no_subsequent_buys(self):
        data=frames(100)
        for frame in data[30:]:
            for p,b in frame.items():
                frame[p]=replace(b,open=b.open*.05,high=b.high*.05,low=b.low*.05,close=b.close*.05)
        result=simulate(data,self.cfg,self.spec)
        self.assertIsNotNone(result.halt_timestamp)
        self.assertFalse(any(t['side']=='BUY' and t['timestamp']>=result.halt_timestamp for t in result.trades))


class MetricTests(unittest.TestCase):
    def result(self,values):
        result=Result('sample')
        result.curve=[{'timestamp':i*86400,'equity':v,'cash':v,'exposure':0} for i,v in enumerate(values)]
        return result

    def test_hand_calculated_return_drawdown_sharpe_sortino(self):
        stats=metrics(self.result([100,110,99]))
        self.assertAlmostEqual(stats['net_return'],-.01)
        self.assertAlmostEqual(stats['max_drawdown'],.1)
        self.assertAlmostEqual(stats['sharpe'],0)
        self.assertAlmostEqual(stats['sortino'],0)
        self.assertAlmostEqual(stats['calmar'],((.99)**(365/2)-1)/.1)

    def test_composite_formula_and_undefined_values(self):
        self.assertAlmostEqual(composite_score(2, 1, 3), 2.0)
        self.assertIsNone(composite_score(None, 1, 3))
        self.assertIsNone(composite_score(2, float('inf'), 3))
        self.assertIsNone(metrics(self.result([100, 100, 100]))['composite_score'])

    def test_nonzero_ratios_against_hand_formula(self):
        stats=metrics(self.result([100,110,99,108.9]))
        mean=.1/3
        sd=math.sqrt(((.1-mean)**2+(-.1-mean)**2+(.1-mean)**2)/2)
        downside=math.sqrt(.01/3)
        self.assertAlmostEqual(stats['sharpe'],mean/sd*math.sqrt(365))
        self.assertAlmostEqual(stats['sortino'],mean/downside*math.sqrt(365))

    def test_cash_undefined_ratios_are_none(self):
        stats=metrics(self.result([100,100,100]))
        for name in ['sharpe','sortino','calmar']:
            self.assertIsNone(stats[name])

    def test_no_downside_sortino_is_none(self):
        stats=metrics(self.result([100,110,115]))
        self.assertIsNone(stats['sortino'])
        self.assertGreater(stats['sharpe'],0)

    def test_daily_resampling_ignores_partial_days(self):
        r=self.result([100,110,99])
        r.curve.insert(1,{'timestamp':300,'equity':10000})
        self.assertEqual(len(daily_returns(r.curve)),2)
        short=Result('short',curve=[{'timestamp':0,'equity':100,'exposure':0},{'timestamp':300,'equity':110,'exposure':0}])
        self.assertIsNone(metrics(short)['sharpe'])

    def test_turnover_and_fees(self):
        result=self.result([100,110,120])
        result.trades=[{'notional':50,'fee':1,'reason':'signal'},{'notional':60,'fee':2,'reason':'terminal_liquidation'}]
        stats=metrics(result)
        self.assertEqual(stats['turnover'],1)
        self.assertEqual(stats['fees'],3)
        self.assertEqual(stats['strategy_trade_count'],1)


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.spec=spec();self.pairs=('BTC/USD','ETH/USD')

    def tearDown(self):self.temp.cleanup()

    def test_load_complete_aligned_data(self):
        path=self.root/'development.csv';write_frames(path,frames())
        self.assertEqual(len(load_period(path,'development',self.spec,self.pairs)),288)

    def test_duplicates_missing_and_outside_period_rejected(self):
        for data in [frames()[:-1],frames()+frames(1),frames(start=utc_date('2025-01-03'))]:
            path=self.root/'bad.csv';write_frames(path,data)
            with self.assertRaises(ValueError):load_period(path,'development',self.spec,self.pairs)

    def test_invalid_ohlcv_rejected(self):
        bar=frames(1)[0]['BTC/USD']
        for bad in [replace(bar,close=float('nan')),replace(bar,low=999),replace(bar,volume=-1)]:
            with self.assertRaises(ValueError):bad.validate()

    def test_split_overlap_rejected(self):
        self.spec['validation']['start']='2025-01-01'
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_microsecond_and_millisecond_archives(self):
        for divisor in (1000,1000000):
            archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w') as z:
                rows=[]
                for frame in frames():
                    b=frame['BTC/USD']
                    rows.append(f'{b.timestamp*divisor},{b.open},{b.high},{b.low},{b.close},{b.volume},0,0,0,0,0,0')
                z.writestr('data.csv','\n'.join(rows))
            raw=archive.getvalue()
            import hashlib
            checksum=hashlib.sha256(raw).hexdigest().encode()
            folder=self.root/str(divisor)
            with patch('trading_bot.backtesting.data.fetch_bytes',side_effect=lambda url:checksum if url.endswith('.CHECKSUM') else raw):
                fetch_period(folder,'development',self.spec,self.pairs)
            self.assertEqual(len(load_period(folder/'development.csv','development',self.spec,self.pairs)),288)
            mapping={'BNB/USD':'BNBUSDT','SOL/USD':'SOLUSDT','PAXG/USD':'PAXGUSDT'}
            extra=folder/'expanded'
            with patch('trading_bot.backtesting.data.fetch_bytes',side_effect=lambda url:checksum if url.endswith('.CHECKSUM') else raw):
                fetch_period(extra,'development',self.spec,tuple(mapping),mapping)
            self.assertEqual(len(load_period(extra/'development.csv','development',self.spec,tuple(mapping))),288)

    def test_checksum_failure_rejected(self):
        with patch('trading_bot.backtesting.data.fetch_bytes',side_effect=[b'zip',b'bad']):
            with self.assertRaises(ValueError):fetch_period(self.root,'development',self.spec,self.pairs)

    def test_explicit_symbol_map_rejects_mismatches_and_url_paths(self):
        for mapping in ({'BTC/USD':'BTCUSDT'}, {'BTC/USD':'../BTCUSDT','ETH/USD':'ETHUSDT'}, {'BTC/USD':42,'ETH/USD':'ETHUSDT'}, {'BTC/USD':'ETHUSDT','ETH/USD':'BTCUSDT'}):
            with patch('trading_bot.backtesting.data.fetch_bytes',side_effect=AssertionError('network')):
                with self.assertRaises(ValueError):fetch_period(self.root,'development',self.spec,self.pairs,mapping)


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.cfg=Config(fast_window=2,slow_window=4,signal_threshold=.001)
        self.spec=spec()
        for p in ('development','validation'):
            write_frames(self.root/f'{p}.csv',frames(start=utc_date(self.spec[p]['start'])))
        self.report=self.root/'report';self.selection=self.root/'selection.json'

    def tearDown(self):self.temp.cleanup()

    def test_research_never_loads_or_fetches_test(self):
        with patch('trading_bot.backtesting.cli.fetch_period',side_effect=AssertionError('network')):
            summary=cli.research(self.root,self.report,self.cfg,self.spec)
        self.assertEqual(set(summary['periods']),{'development','validation'})
        self.assertFalse((self.root/'test.csv').exists())
        cli.freeze(self.root,self.report,self.selection,self.cfg,self.spec)
        self.assertTrue(self.selection.exists())

    def test_final_requires_explicit_access(self):
        with self.assertRaises(ValueError):cli.final(self.root,self.root/'final',self.selection,False)
        self.assertFalse((self.root/'test-access.json').exists())

    def test_freeze_rejects_config_change(self):
        cli.research(self.root,self.report,self.cfg,self.spec)
        with self.assertRaises(ValueError):cli.freeze(self.root,self.report,self.selection,replace(self.cfg,slippage=.002),self.spec)

    def test_final_consumed_once_and_rejects_code_change(self):
        cli.research(self.root,self.report,self.cfg,self.spec)
        cli.freeze(self.root,self.report,self.selection,self.cfg,self.spec)
        with patch('trading_bot.backtesting.cli.code_hashes',return_value={}):
            with self.assertRaises(ValueError):cli.final(self.root,self.root/'final',self.selection,True)
        self.assertFalse((self.root/'test-access.json').exists())
        write_frames(self.root/'test.csv',frames(start=utc_date(self.spec['test']['start'])))
        summary=cli.final(self.root,self.root/'final',self.selection,True)
        self.assertEqual(set(summary['periods']),{'test'})
        self.assertTrue(json.loads((self.root/'test-access.json').read_text())['completed'])
        with self.assertRaises(ValueError):cli.final(self.root,self.root/'another',self.selection,True)

    def test_final_rejects_changed_earlier_data(self):
        cli.research(self.root,self.report,self.cfg,self.spec)
        cli.freeze(self.root,self.report,self.selection,self.cfg,self.spec)
        path=self.root/'validation.csv'
        path.write_text(path.read_text()+'\n')
        with self.assertRaises(ValueError):cli.final(self.root,self.root/'final',self.selection,True)
        self.assertFalse((self.root/'test-access.json').exists())

    def test_selection_checksum_detects_tampering(self):
        cli.research(self.root,self.report,self.cfg,self.spec)
        cli.freeze(self.root,self.report,self.selection,self.cfg,self.spec)
        envelope=json.loads(self.selection.read_text())
        envelope['selection']['config']['slippage']=0
        self.selection.write_text(json.dumps(envelope))
        with self.assertRaises(ValueError):cli.final(self.root,self.root/'final',self.selection,True)


if __name__=='__main__':unittest.main()
