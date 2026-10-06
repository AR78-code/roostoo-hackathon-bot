"""Replay already-frozen classifier policies with continuous forward state."""
from dataclasses import replace,asdict
import json
from pathlib import Path
from trading_bot.config import load
from trading_bot.ml import LOOKBACK
from trading_bot.backtesting.cli import code_hashes
from trading_bot.backtesting.data import digest,load_period,load_spec
from trading_bot.backtesting.simulator import simulate,benchmark
from trading_bot.backtesting.report import write_report
from train_logistic import POLICIES
from train_ridge import trade_stats
from run_batch import segments


def main():
    root=Path('reports/research/batch-03/continuous');root.mkdir(parents=True,exist_ok=True)
    cfg=load('config/bot.toml');spec=load_spec('config/backtest.toml')
    models=[]
    for month in ('2025-03','2025-04','2025-05','2025-06'):
        path=Path(f'config/models/logistic-{month}.json');model=json.loads(path.read_text())
        assert model['available_at']<model['evaluation_start']
        models.append((model['evaluation_start']-1e-6,str(path)))
    registry={'protocol':'No fitting or policy changes. Original three classifier policies, continuous March-June development with monthly artifact updates. Carry cash, holdings and drawdown latch. Double execution costs and independent 14-day resets as diagnostics.',
              'policies':POLICIES,'code_sha256':code_hashes(),'script_sha256':digest(__file__),
              'data_sha256':digest('data/historical/development.csv'),
              'artifact_schedule':[{'effective_at':ts,'path':path,'sha256':digest(path)} for ts,path in models]}
    with (root/'registry.json').open('x') as handle:json.dump(registry,handle,indent=2)
    frames=load_period('data/historical/development.csv','development',spec,cfg.pairs)
    start=next(first for label,first,last in segments(frames,'monthly') if label=='2025-03')
    forward=frames[start:];warm=frames[start-LOOKBACK:start];summaries=[];runs=[]
    for name,entry,exit,vol in POLICIES:
        base=replace(cfg,strategy='logistic',slow_window=LOOKBACK,model_path=models[0][1],
                     model_entry_probability=entry,model_exit_probability=exit,volatility_target=vol)
        schedule=[(ts,replace(base,model_path=path)) for ts,path in models]
        result=simulate(forward,base,spec,warm,schedule);result.name=name;runs.append(result)
        stress=replace(base,fee_rate=cfg.fee_rate*2,slippage=cfg.slippage*2)
        stressed=simulate(forward,stress,spec,warm,[(ts,replace(stress,model_path=path)) for ts,path in models])
        windows=[]
        for label,first,last in segments(forward,'fortnight'):
            absolute=start+first
            replay=simulate(forward[first:last],base,spec,frames[absolute-LOOKBACK:absolute],schedule)
            windows.append({'window':label,**trade_stats(replay)})
        record={'candidate':name,'config':asdict(base),'continuous_forward':trade_stats(result),
                'double_cost_stress':trade_stats(stressed),'fortnight':windows}
        summaries.append(record)
        (root/f'{name}.json').write_text(json.dumps(record,indent=2,allow_nan=False))
        print(f"{name}: continuous return={record['continuous_forward']['net_return']:.2%}, stress={record['double_cost_stress']['net_return']:.2%}",flush=True)
    weight=min(cfg.max_pair_weight,cfg.max_total_weight/2)
    runs.extend([benchmark(forward,cfg,spec,'cash',{}),benchmark(forward,cfg,spec,'btc_buy_hold',{'BTC/USD':1}),
                 benchmark(forward,cfg,spec,'allocation_matched',{'BTC/USD':weight,'ETH/USD':weight})])
    (root/'candidate-summary.json').write_text(json.dumps(summaries,indent=2,allow_nan=False))
    report_spec={**spec,'forward_development':{'start':'2025-03-01','end':spec['development']['end']}}
    provenance={**registry,'portfolio_configs':{r['candidate']:r['config'] for r in summaries},
                'configuration_note':'Top-level configuration supplies common risk/execution and benchmark settings; actual portfolio configs and model schedule are separate.'}
    write_report(root,{'forward_development':runs},cfg,report_spec,provenance)
    assert not Path('data/historical/test.csv').exists()
    assert not Path('data/historical/test-access.json').exists()
    print('Continuous classifier replay complete; validation/test untouched.',flush=True)


if __name__=='__main__':main()
