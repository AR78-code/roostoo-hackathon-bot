"""Development counterfactual: diagnose the buy latch, never change live risk."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from trading_bot.config import load
from trading_bot.backtesting.data import load_period,load_spec,digest
from trading_bot.backtesting.cli import code_hashes
from trading_bot.backtesting.simulator import simulate
from trading_bot.backtesting.metrics import metrics


def main():
    root=Path('reports/research/halt-diagnosis');root.mkdir(parents=True,exist_ok=True)
    names=['baseline','trend_3h_12h','trend_12h_2d_vol01']
    registry={'candidates':names,'diagnostic_drawdown_limit':.99,
              'hypothesis':'Determine whether irreversible buy halts explain negative continuous-development performance. A 99% halt is diagnostic, not an acceptable deployment policy.',
              'code_sha256':code_hashes(),'data_sha256':digest('data/historical/development.csv'),'script_sha256':digest(__file__)}
    with (root/'registry.json').open('x') as handle:json.dump(registry,handle,indent=2)
    spec=load_spec('config/backtest.toml');frames=load_period('data/historical/development.csv','development',spec,load('config/bot.toml').pairs)
    records=[]
    for name in names:
        cfg=load(f'config/candidates/{name}.toml')
        baseline=json.loads(Path(f"reports/research/{'batch-02' if 'vol01' in name else 'batch-01'}/{name}.json").read_text())['overall']
        result=simulate(frames,replace(cfg,max_drawdown=.99),spec)
        stats=metrics(result)
        records.append({'name':name,'original':baseline,'relaxed_halt_diagnostic':stats,
                        'diagnostic_halt_timestamp':result.halt_timestamp})
        print(f"{name}: original {baseline['net_return']:.2%}, relaxed halt {stats['net_return']:.2%}, diagnostic drawdown {stats['max_drawdown']:.2%}",flush=True)
    with (root/'results.json').open('x') as handle:json.dump(records,handle,indent=2,allow_nan=False)


if __name__=='__main__':main()
