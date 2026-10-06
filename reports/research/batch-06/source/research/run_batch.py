"""Recorded, manually specified candidate batch. Never opens validation/test data."""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import sys

from trading_bot.config import load
from trading_bot.backtesting.cli import code_hashes
from trading_bot.backtesting.data import digest, load_period, load_spec
from trading_bot.backtesting.metrics import metrics
from trading_bot.backtesting.report import write_csv
from trading_bot.backtesting.simulator import simulate


# Frozen candidate list before viewing candidate results: hypothesis, not a search grid.
CANDIDATES = [
    ('baseline', {}, 'Reference: original one-hour/four-hour SMA'),
    ('threshold_006', {'signal_threshold':.006}, 'Require stronger evidence before switching position'),
    ('threshold_010', {'signal_threshold':.010}, 'Stronger hysteresis reduces short-term reversals'),
    ('trend_3h_12h', {'fast_window':36,'slow_window':144,'signal_threshold':.006}, 'Slower signal reduces turnover'),
    ('trend_6h_1d', {'fast_window':72,'slow_window':288,'signal_threshold':.006}, 'Follow intraday-to-daily trends'),
    ('trend_12h_2d', {'fast_window':144,'slow_window':576,'signal_threshold':.006}, 'Follow multi-day trends'),
    ('trend_1d_4d', {'fast_window':288,'slow_window':1152,'signal_threshold':.006}, 'Daily/multi-day trend regime'),
    ('trend_1d_4d_003', {'fast_window':288,'slow_window':1152,'signal_threshold':.003}, 'Nearby sensitivity check: earlier entry/exit'),
    ('trend_1d_4d_010', {'fast_window':288,'slow_window':1152,'signal_threshold':.010}, 'Nearby sensitivity check: less switching'),
    ('trend_2d_8d', {'fast_window':576,'slow_window':2304,'signal_threshold':.006}, 'Longer trend filter'),
    ('trend_2d_8d_010', {'fast_window':576,'slow_window':2304,'signal_threshold':.010}, 'Nearby slower-trend threshold'),
    ('trend_12h_2d_band04', {'fast_window':144,'slow_window':576,'signal_threshold':.006,'rebalance_band':.04}, 'Reduce incidental rebalancing'),
    ('trend_1d_4d_band04', {'fast_window':288,'slow_window':1152,'signal_threshold':.006,'rebalance_band':.04}, 'Reduce turnover around daily trend'),
]


def finite_median(values):
    values=[v for v in values if v is not None and math.isfinite(v)]
    return statistics.median(values) if values else None


def segments(frames,kind):
    if kind=='monthly':
        start=0
        for i in range(1,len(frames)+1):
            previous=datetime.fromtimestamp(frames[i-1]['BTC/USD'].timestamp,timezone.utc).month
            current=datetime.fromtimestamp(frames[i]['BTC/USD'].timestamp,timezone.utc).month if i<len(frames) else None
            if current!=previous:
                yield datetime.fromtimestamp(frames[start]['BTC/USD'].timestamp,timezone.utc).strftime('%Y-%m'),start,i
                start=i
    elif kind=='fortnight':
        count=14*86400//300
        for start in range(0,len(frames)-count+1,count):
            yield datetime.fromtimestamp(frames[start]['BTC/USD'].timestamp,timezone.utc).strftime('%Y-%m-%d'),start,start+count


def evaluate_segment(frames,start,end,cfg,spec):
    warm=frames[max(0,start-cfg.slow_window):start] or None
    result=simulate(frames[start:end],cfg,spec,warm)
    stats=metrics(result)
    dates={datetime.fromtimestamp(t['timestamp'],timezone.utc).date().isoformat() for t in result.trades if t['reason']!='terminal_liquidation'}
    stats['active_days']=len(dates)
    stats['start']=frames[start]['BTC/USD'].timestamp
    stats['end']=frames[end-1]['BTC/USD'].timestamp+300
    return stats


def write_candidate(path,cfg):
    values=asdict(cfg)
    lines=[]
    for key,value in values.items():
        if isinstance(value,(tuple,list)):
            encoded=json.dumps(list(value))
        elif isinstance(value,str):encoded=json.dumps(value)
        else:encoded=str(value).lower()
        lines.append(f'{key} = {encoded}')
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='reports/research/batch-01')
    args=parser.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    cfg=load('config/bot.toml');spec=load_spec('config/backtest.toml')
    fingerprints={'data_sha256':digest('data/historical/development.csv'),'code_sha256':code_hashes(),'research_script_sha256':digest(__file__)}
    registry={'created_at':datetime.now(timezone.utc).isoformat(),'candidates':[{'name':n,'changes':c,'hypothesis':h} for n,c,h in CANDIDATES],**fingerprints,
        'protocol':'Development only. Monthly and 14-day resets. Chronological parameter selection uses earlier monthly results only. Test remains absent.'}
    registry_path=root/'registry.json'
    if registry_path.exists():
        prior=json.loads(registry_path.read_text())
        for k in ('data_sha256','code_sha256','research_script_sha256','candidates'):
            if prior[k]!=registry[k]:raise ValueError('Cannot resume batch with changed code/data/candidates')
    else:
        registry_path.write_text(json.dumps(registry,indent=2))
    frames=load_period('data/historical/development.csv','development',spec,cfg.pairs)
    results=[]
    for name,changes,hypothesis in CANDIDATES:
        path=root/f'{name}.json'
        if path.exists():
            results.append(json.loads(path.read_text()));print(f'Resuming: {name} already recorded',flush=True);continue
        candidate=replace(cfg,**changes)
        print(f'Evaluating {name}',flush=True)
        write_candidate(f'config/candidates/{name}.toml',candidate)
        overall=evaluate_segment(frames,0,len(frames),candidate,spec)
        monthly=[{'window':label,**evaluate_segment(frames,start,end,candidate,spec)} for label,start,end in segments(frames,'monthly')]
        fortnight=[{'window':label,**evaluate_segment(frames,start,end,candidate,spec)} for label,start,end in segments(frames,'fortnight')]
        # Cost stress is development-only and holds all other parameters fixed.
        stress=evaluate_segment(frames,0,len(frames),replace(candidate,fee_rate=cfg.fee_rate*2,slippage=cfg.slippage*2),spec)
        entry={'name':name,'hypothesis':hypothesis,'config':asdict(candidate),'overall':overall,'monthly':monthly,'fortnight':fortnight,'double_cost_stress':stress,
            'monthly_median_score':finite_median([m['composite_score'] for m in monthly]),
            'fortnight_median_score':finite_median([m['composite_score'] for m in fortnight]),
            'positive_months':sum(m['net_return']>0 for m in monthly),
            'positive_fortnights':sum(m['net_return']>0 for m in fortnight)}
        path.write_text(json.dumps(entry,indent=2,allow_nan=False));results.append(entry)
        print(f"{name}: return={overall['net_return']:.2%}, score={overall['composite_score']}, fees=${overall['fees']:.0f}",flush=True)
    rows=[]
    for result in results:
        rows.append({'candidate':result['name'],**result['overall'],'monthly_median_score':result['monthly_median_score'],'fortnight_median_score':result['fortnight_median_score'],
            'positive_months':result['positive_months'],'positive_fortnights':result['positive_fortnights'],'stress_return':result['double_cost_stress']['net_return']})
    write_csv(root/'comparison.csv',rows)
    # Not the performance of a continuous portfolio: each forward month resets capital.
    forward=[]
    for index in range(2,6):
        eligible=[]
        for result in results:
            past=result['monthly'][:index]
            score=finite_median([m['composite_score'] for m in past])
            compounded=math.prod(1+m['net_return'] for m in past)-1
            if score is not None and compounded>0 and sum(m['composite_score'] is not None for m in past)>=2:
                eligible.append((score,result))
        if eligible:
            _,winner=max(eligible,key=lambda entry:entry[0])
            current=winner['monthly'][index]
            forward.append({'window':current['window'],'selected':winner['name'],'selection_uses_prior_months':index,**current})
        else:
            forward.append({'window':results[0]['monthly'][index]['window'],'selected':'cash_fallback','net_return':0,'composite_score':None,'selection_uses_prior_months':index})
    (root/'walk_forward.json').write_text(json.dumps({'note':'Past-month-selected configs, next-month independent cash starts. No validation/test used. Cash fallback when no candidate has positive compounded past return and >=2 defined monthly scores.','folds':forward},indent=2,allow_nan=False))
    ordered=sorted(results,key=lambda r:r['monthly_median_score'] if r['monthly_median_score'] is not None else -math.inf,reverse=True)
    (root/'ranking.json').write_text(json.dumps([{'name':r['name'],'monthly_median_score':r['monthly_median_score'],'return':r['overall']['net_return'],'positive_months':r['positive_months'],'stress_return':r['double_cost_stress']['net_return']} for r in ordered],indent=2))
    assert not Path('data/historical/test.csv').exists()
    assert not Path('data/historical/test-access.json').exists()
    print('Batch complete. No validation or test data opened.',flush=True)


if __name__=='__main__':main()
