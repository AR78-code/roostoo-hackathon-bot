"""Repair/render recorded batch05 output without rerunning a model or opening prices."""
import csv
import json
from pathlib import Path
from trading_bot.config import Config
from trading_bot.backtesting.simulator import Result
from trading_bot.backtesting.report import write_report


def read_rows(path,numeric):
    with path.open() as handle:
        rows=list(csv.DictReader(handle))
    for row in rows:
        for key in numeric:
            if key in row:
                row[key]=float(row[key]) if row[key] else None
    return rows


def main():
    root=Path('reports/research/batch-05');folder=root/'continuous'
    prior=json.loads((folder/'summary.json').read_text())
    candidates=json.loads((root/'summary.json').read_text())
    period='forward_development';runs=[]
    for name,stats in prior['periods'][period].items():
        result=Result(name,halt_timestamp=stats['buy_halt_timestamp'])
        result.curve=read_rows(folder/f'{period}-{name}-equity.csv',['timestamp','equity','cash','exposure'])
        path=folder/f'{period}-{name}-trades.csv'
        result.trades=read_rows(path,['timestamp','signal_timestamp','quantity','price','notional','fee']) if path.stat().st_size else []
        signals=folder/f'{period}-{name}-signals.csv'
        if signals.exists() and signals.stat().st_size:
            result.signals=read_rows(signals,['timestamp','target'])
        runs.append(result)
    cfg=prior['config'];cfg['pairs']=tuple(cfg['pairs'])
    spec=prior['backtest_spec'];spec[period]={'start':'2025-03-01','end':spec['development']['end']}
    provenance={**prior['provenance'],'portfolio_configs':{r['candidate']:[m['config'] for m in r['months']] for r in candidates},
                'model_schedules':{r['candidate']:r['model_schedule'] for r in candidates},
                'configuration_note':'Top-level config supplies common risk/execution settings; actual portfolio strategy configs and schedules are recorded separately.',
                'report_repair':'Initial renderer lacked custom forward-period bounds; regenerated from saved curve/trade/signal CSV only. No strategy/model or market-data evaluation rerun.'}
    write_report(folder,{period:runs},Config(**cfg),spec,provenance)
    print('Rendered recorded continuous results without market-data access')


if __name__=='__main__':main()
