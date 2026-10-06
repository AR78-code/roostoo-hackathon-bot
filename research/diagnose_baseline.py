"""Execution cashflow and FIFO holding-time diagnosis; no new market data accessed."""
from collections import defaultdict, deque
import csv
import json
from pathlib import Path
import statistics


def diagnose(path):
    with open(path) as handle:
        trades=list(csv.DictReader(handle))
    lots=defaultdict(deque)
    gross=fees=turnover=0.0
    durations=[]
    weighted_duration=quantity_weight=0.0
    reversals=0
    previous={}
    active=set()
    from datetime import datetime,timezone
    for trade in trades:
        qty,price,fee,notional=map(float,(trade['quantity'],trade['price'],trade['fee'],trade['notional']))
        pair,side,ts=trade['pair'],trade['side'],float(trade['timestamp'])
        gross+=notional if side=='SELL' else -notional
        fees+=fee;turnover+=notional
        if trade['reason']!='terminal_liquidation':
            active.add(datetime.fromtimestamp(ts,timezone.utc).date().isoformat())
            if pair in previous and previous[pair]!=side:reversals+=1
            previous[pair]=side
        if side=='BUY':
            lots[pair].append([qty,ts,price])
        else:
            remaining=qty
            while remaining>1e-10 and lots[pair]:
                lot=lots[pair][0]
                matched=min(remaining,lot[0])
                hours=(ts-lot[1])/3600
                durations.append(hours)
                weighted_duration+=hours*matched*price
                quantity_weight+=matched*price
                lot[0]-=matched;remaining-=matched
                if lot[0]<1e-10:lots[pair].popleft()
    return {'total_trades':len(trades),'active_days':len(active),'same_pair_side_reversals':reversals,
        'total_notional':turnover,'commission_fees':fees,'execution_cashflow_before_commissions':gross,
        'net_execution_cashflow':gross-fees,'median_fifo_lot_holding_hours':statistics.median(durations) if durations else None,
        'notional_weighted_fifo_holding_hours':weighted_duration/quantity_weight if quantity_weight else None,
        'lots_closed_within_4_hours_fraction':sum(d<4 for d in durations)/len(durations) if durations else None,
        'note':'Gross execution cashflow includes modeled spread and slippage, excludes commissions, and holds actual recorded trades fixed. This is an accounting decomposition, not a counterfactual no-cost backtest.'}


if __name__=='__main__':
    root=Path('reports/research');root.mkdir(parents=True,exist_ok=True)
    result={p:diagnose(f'reports/baseline/{p}-strategy-trades.csv') for p in ('development','validation')}
    (root/'baseline-diagnosis.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
