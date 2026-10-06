"""Batch 05: preregistered expected-return model, chronological development only."""
from dataclasses import replace, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import math
import numpy as np
from trading_bot.config import load
from trading_bot.ml import FEATURE_NAMES, LOOKBACK, expected_return
from trading_bot.backtesting.cli import code_hashes
from trading_bot.backtesting.data import digest, load_period, load_spec
from trading_bot.backtesting.metrics import metrics
from trading_bot.backtesting.simulator import simulate, benchmark
from trading_bot.backtesting.report import write_report
from train_logistic import feature_matrix, HORIZON, AVAILABILITY_BUFFER
from run_batch import segments, write_candidate, finite_median

PENALTY=.1
POLICIES=[('ridge_entry002',.002,0),('ridge_entry005',.005,0),('ridge_entry002_vol01',.002,.01)]


def fit(x,y):
    mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale>1e-12,scale,1)
    z=(x-mean)/scale;intercept=float(y.mean())
    slopes=np.linalg.solve(z.T@z/len(y)+PENALTY*np.eye(x.shape[1]),z.T@(y-intercept)/len(y))
    return {'model_type':'ridge','mean':mean.tolist(),'scale':scale.tolist(),'coefficients':slopes.tolist(),
            'intercept':intercept,'training_rows':len(y),'training_mse':float(((z@slopes+intercept-y)**2).mean()),
            'constant_mean_training_mse':float(((intercept-y)**2).mean()),'fit_settings':{'ridge_penalty':PENALTY,'target_clip':[-.15,.15]}}


def trade_stats(result):
    stats=metrics(result)
    stats['active_days']=len({datetime.fromtimestamp(t['timestamp'],timezone.utc).date().isoformat()
                             for t in result.trades if t['reason']!='terminal_liquidation'})
    return stats


def main():
    root=Path('reports/research/batch-05');root.mkdir(parents=True,exist_ok=True)
    cfg=load('config/bot.toml');spec=load_spec('config/backtest.toml')
    registry={'policies':POLICIES,'ridge_penalty':PENALTY,'training_target_clip':[-.15,.15],
              'label_horizon_bars':HORIZON,'availability_buffer_bars':AVAILABILITY_BUFFER,
              'code_sha256':code_hashes(),'script_sha256':digest(__file__),
              'feature_script_sha256':digest('research/train_logistic.py'),
              'data_sha256':digest('data/historical/development.csv'),
              'protocol':'Earlier training only. Forward March-June monthly resets and continuous chronological model updates. Development only, no validation/test.'}
    with (root/'registry.json').open('x') as handle:json.dump(registry,handle,indent=2)
    frames=load_period('data/historical/development.csv','development',spec,cfg.pairs)
    prepared={}
    for pair in cfg.pairs:
        indices,x=feature_matrix(np.array([f[pair].close for f in frames]))
        prepared[pair]=(indices,x,np.array([f[pair].open for f in frames]))
    months=list(segments(frames,'monthly'))[2:]
    models=[];monthly={name:[] for name,*_ in POLICIES};calibration=[]
    for month,start,end in months:
        cutoff=start-AVAILABILITY_BUFFER;xs=[];ys=[];forward_x=[];forward_y=[]
        last_label=0
        for pair,(indices,x,opens) in prepared.items():
            for mask,is_training in [(indices+HORIZON+1<cutoff,True),((indices>=start)&(indices+HORIZON+1<end),False)]:
                picked=indices[mask]
                entry=opens[picked+1]*(1+spec['spread_bps']/20000)*(1+cfg.slippage)*(1+cfg.fee_rate)
                exit=opens[picked+HORIZON+1]*(1-spec['spread_bps']/20000)*(1-cfg.slippage)*(1-cfg.fee_rate)
                target=np.log(exit/entry)
                if is_training:
                    xs.append(x[mask]);ys.append(np.clip(target,-.15,.15))
                    last_label=max(last_label,frames[int(picked[-1]+HORIZON+1)][pair].timestamp)
                else:
                    forward_x.append(x[mask]);forward_y.append(target)
        model=fit(np.vstack(xs),np.concatenate(ys))
        model.update(feature_names=list(FEATURE_NAMES),interval_seconds=300,
                     available_at=frames[cutoff-1]['BTC/USD'].timestamp+300,
                     last_label_timestamp=last_label,evaluation_start=frames[start]['BTC/USD'].timestamp,
                     data_sha256=registry['data_sha256'],label_horizon_bars=HORIZON)
        assert model['last_label_timestamp']<model['available_at']<model['evaluation_start']
        path=Path(f'config/models/ridge-{month}.json')
        with path.open('x') as handle:json.dump(model,handle,indent=2,allow_nan=False)
        models.append((model['evaluation_start']-1e-6,str(path)))
        fx=np.vstack(forward_x);fy=np.concatenate(forward_y)
        pred=((fx-model['mean'])/model['scale'])@np.array(model['coefficients'])+model['intercept']
        calibration.append({'month':month,'rows':len(fy),'model_sha256':digest(path),
                            'forward_mse':float(((pred-fy)**2).mean()),
                            'prior_mean_mse':float(((model['intercept']-fy)**2).mean()),
                            'mean_prediction':float(pred.mean()),'mean_outcome':float(fy.mean())})
        for name,entry,vol in POLICIES:
            candidate=replace(cfg,strategy='ridge',slow_window=LOOKBACK,model_path=str(path),model_entry_return=entry,volatility_target=vol)
            # Pure-Python inference must match vectorized prediction at a real forward observation.
            vector_history=[(f['BTC/USD'].timestamp,f['BTC/USD'].close) for f in frames[start-LOOKBACK+1:start+1]]
            idx,x,_=prepared['BTC/USD'];row=x[start-(LOOKBACK-1)]
            value=float(((row-model['mean'])/model['scale'])@np.array(model['coefficients'])+model['intercept'])
            assert math.isclose(expected_return(vector_history,candidate),value,rel_tol=1e-8,abs_tol=1e-10)
            stats=trade_stats(simulate(frames[start:end],candidate,spec,frames[start-LOOKBACK:start]))
            record={'window':month,'config':asdict(candidate),'model_sha256':digest(path),**stats}
            monthly[name].append(record)
            (root/f'{name}-{month}.json').write_text(json.dumps(record,indent=2,allow_nan=False))
            write_candidate(f'config/candidates/{name}-{month}.toml',candidate)
            print(f"{name} {month}: return={stats['net_return']:.2%}, score={stats['composite_score']}",flush=True)
    (root/'calibration.json').write_text(json.dumps({'note':'Forward outcomes are unclipped. Overlapping labels are correlated, not independent observations.','months':calibration},indent=2))
    start=months[0][1];forward=frames[start:];warm=frames[start-LOOKBACK:start]
    summaries=[];runs=[]
    for name,entry,vol in POLICIES:
        base=replace(cfg,strategy='ridge',slow_window=LOOKBACK,model_path=models[0][1],model_entry_return=entry,volatility_target=vol)
        schedule=[(ts,replace(base,model_path=path)) for ts,path in models]
        result=simulate(forward,base,spec,warm,schedule);result.name=name;runs.append(result)
        stress=replace(base,fee_rate=cfg.fee_rate*2,slippage=cfg.slippage*2)
        stressed=simulate(forward,stress,spec,warm,[(ts,replace(stress,model_path=path)) for ts,path in models])
        windows=[]
        for label,first,last in segments(forward,'fortnight'):
            absolute=start+first
            replay=simulate(forward[first:last],base,spec,frames[absolute-LOOKBACK:absolute],schedule)
            windows.append({'window':label,**trade_stats(replay)})
        rows=monthly[name]
        summary={'candidate':name,'months':rows,'continuous_forward':trade_stats(result),
                 'double_cost_stress':trade_stats(stressed),'fortnight':windows,
                 'monthly_median_score':finite_median([r['composite_score'] for r in rows]),
                 'positive_months':sum(r['net_return']>0 for r in rows),
                 'compounded_independent_month_return':math.prod(1+r['net_return'] for r in rows)-1,
                 'model_schedule':[{'effective_at':ts,'path':path,'sha256':digest(path)} for ts,path in models],
                 'note':'Continuous forward carries wallet and drawdown latch; independent monthly portfolios reset. Trained model updates first affect execution at next month open.'}
        summaries.append(summary)
        print(f"{name} continuous: {summary['continuous_forward']['net_return']:.2%}, double cost: {summary['double_cost_stress']['net_return']:.2%}",flush=True)
    weight=min(cfg.max_pair_weight,cfg.max_total_weight/2)
    runs.extend([benchmark(forward,cfg,spec,'cash',{}),benchmark(forward,cfg,spec,'btc_buy_hold',{'BTC/USD':1}),
                 benchmark(forward,cfg,spec,'allocation_matched',{'BTC/USD':weight,'ETH/USD':weight})])
    (root/'summary.json').write_text(json.dumps(summaries,indent=2,allow_nan=False))
    write_report(root/'continuous',{'forward_development':runs},cfg,spec,registry)
    assert not Path('data/historical/test.csv').exists()
    assert not Path('data/historical/test-access.json').exists()
    print('Batch05 complete. No validation/test access.',flush=True)


if __name__=='__main__':main()
