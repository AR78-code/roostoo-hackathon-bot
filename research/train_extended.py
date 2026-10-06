"""Batch07: fixed logistic/ridge policies with supplemental earlier training."""
from dataclasses import asdict,replace
import json
import math
from pathlib import Path
import tomllib
import numpy as np
from trading_bot.config import load
from trading_bot.ml import FEATURE_NAMES,LOOKBACK,features
from trading_bot.backtesting.cli import code_hashes
from trading_bot.backtesting.data import digest,load_period,load_spec
from trading_bot.backtesting.simulator import simulate,benchmark,validate_replay
from trading_bot.backtesting.report import write_report
from train_logistic import fit as fit_logistic,feature_matrix,HORIZON,AVAILABILITY_BUFFER,POLICIES as LOGISTIC
from train_ridge import fit as fit_ridge,trade_stats,POLICIES as RIDGE
from run_batch import segments,write_candidate,finite_median

POLICIES=[('extended_'+name,'logistic',entry,exit,vol) for name,entry,exit,vol in LOGISTIC]+[
    ('extended_'+name,'ridge',entry,0,vol) for name,entry,vol in RIDGE]


def config_for(base,policy,path):
    name,family,entry,exit,vol=policy
    cfg=replace(base,strategy=family,slow_window=LOOKBACK,model_path=path,volatility_target=vol)
    return replace(cfg,model_entry_probability=entry,model_exit_probability=exit) if family=='logistic' else replace(cfg,model_entry_return=entry,model_exit_return=exit)


def main():
    root=Path('reports/research/batch-07');root.mkdir(parents=True,exist_ok=True)
    cfg=load('config/bot.toml');spec=load_spec('config/backtest.toml')
    supplement=tomllib.loads(Path('config/earlier-training.toml').read_text())
    registry={'policies':POLICIES,'training_history_amendment':'2024 supplement; forward Jan-Jun2025 remains original development',
              'horizon_bars':HORIZON,'availability_buffer_bars':AVAILABILITY_BUFFER,
              'code_sha256':code_hashes(),'script_sha256':digest(__file__),
              'fit_script_sha256':{p:digest(p) for p in ('research/train_logistic.py','research/train_ridge.py')},
              'data_sha256':{p:digest(p) for p in ('data/earlier-training/training.csv','data/historical/development.csv')},
              'protocol':'Same six existing policies/settings, expanding earlier training only. Monthly reset and continuous forward, doubled execution costs and14-day resets. No validation/test access.'}
    with (root/'registry.json').open('x') as handle:json.dump(registry,handle,indent=2)
    earlier=load_period('data/earlier-training/training.csv','training',supplement,cfg.pairs)
    development=load_period('data/historical/development.csv','development',spec,cfg.pairs)
    frames=earlier+development;start_forward=len(earlier)
    validate_replay(frames,cfg,spec)
    prepared={}
    for pair in cfg.pairs:
        closes=np.array([f[pair].close for f in frames]);indices,x=feature_matrix(closes)
        for index in (LOOKBACK-1,start_forward,len(frames)-1):
            np.testing.assert_allclose(x[index-(LOOKBACK-1)],features(closes[index-LOOKBACK+1:index+1].tolist()),rtol=1e-8,atol=1e-10)
        prepared[pair]=(indices,x,np.array([f[pair].open for f in frames]))
    monthly={p[0]:[] for p in POLICIES};models={'logistic':[],'ridge':[]};calibration=[]
    for month,start,end in segments(frames,'monthly'):
        if start<start_forward:continue
        cutoff=start-AVAILABILITY_BUFFER;xs=[];ys=[];fx=[];fy=[];last_label=0
        for pair,(indices,x,opens) in prepared.items():
            for mask,training in [(indices+HORIZON+1<cutoff,True),((indices>=start)&(indices+HORIZON+1<end),False)]:
                picked=indices[mask]
                entry=opens[picked+1]*(1+spec['spread_bps']/20000)*(1+cfg.slippage)*(1+cfg.fee_rate)
                exit=opens[picked+HORIZON+1]*(1-spec['spread_bps']/20000)*(1-cfg.slippage)*(1-cfg.fee_rate)
                target=np.log(exit/entry)
                if training:
                    xs.append(x[mask]);ys.append(target)
                    last_label=max(last_label,frames[int(picked[-1]+HORIZON+1)][pair].timestamp)
                else:fx.append(x[mask]);fy.append(target)
        x=np.vstack(xs);y=np.concatenate(ys);forward_x=np.vstack(fx);forward_y=np.concatenate(fy)
        paths={}
        for family in ('logistic','ridge'):
            model=fit_logistic(x,(y>0).astype(float)) if family=='logistic' else fit_ridge(x,np.clip(y,-.15,.15))
            model.update(model_type=family,feature_names=list(FEATURE_NAMES),interval_seconds=300,
                         available_at=frames[cutoff-1]['BTC/USD'].timestamp+300,last_label_timestamp=last_label,
                         evaluation_start=frames[start]['BTC/USD'].timestamp,data_sha256=registry['data_sha256'],label_horizon_bars=HORIZON)
            assert last_label<model['available_at']<model['evaluation_start']
            path=Path(f'config/models/{family}-extended-{month}.json')
            with path.open('x') as handle:json.dump(model,handle,indent=2,allow_nan=False)
            paths[family]=str(path);models[family].append((model['evaluation_start']-1e-6,str(path)))
            pred=((forward_x-model['mean'])/model['scale'])@np.array(model['coefficients'])+model['intercept']
            if family=='logistic':
                p=1/(1+np.exp(-np.clip(pred,-40,40)));labels=(forward_y>0).astype(float);prior=model['positive_label_fraction']
                loss=lambda probabilities:float(-(labels*np.log(np.clip(probabilities,1e-12,1-1e-12))+(1-labels)*np.log(np.clip(1-probabilities,1e-12,1-1e-12))).mean())
                record={'forward_logloss':loss(p),'constant_prior_logloss':loss(np.full(len(p),prior)),'mean_prediction':float(p.mean()),'positive_fraction':float(labels.mean())}
            else:
                record={'forward_mse':float(((pred-forward_y)**2).mean()),'constant_mean_mse':float(((model['intercept']-forward_y)**2).mean()),'mean_prediction':float(pred.mean()),'mean_outcome':float(forward_y.mean())}
            calibration.append({'month':month,'family':family,'rows':len(forward_y),'model_sha256':digest(path),**record})
            print(f'Fitted {family} {month}: {model["training_rows"]} earlier rows',flush=True)
        for policy in POLICIES:
            name,family,*_=policy;candidate=config_for(cfg,policy,paths[family])
            result=simulate(frames[start:end],candidate,spec,frames[start-LOOKBACK:start]);stats=trade_stats(result)
            record={'window':month,'config':asdict(candidate),'model_sha256':digest(paths[family]),**stats};monthly[name].append(record)
            (root/f'{name}-{month}.json').write_text(json.dumps(record,indent=2,allow_nan=False))
            write_candidate(f'config/candidates/{name}-{month}.toml',candidate)
            print(f"{name} {month}: {stats['net_return']:.2%}",flush=True)
    (root/'calibration.json').write_text(json.dumps({'note':'Correlated overlapping24-hour labels; counts are not independent observations. No validation/test used.','records':calibration},indent=2))
    runs=[];summaries=[];warm=frames[start_forward-LOOKBACK:start_forward]
    for policy in POLICIES:
        name,family,*_=policy;base=config_for(cfg,policy,models[family][0][1])
        schedule=[(ts,replace(base,model_path=path)) for ts,path in models[family]]
        result=simulate(development,base,spec,warm,schedule);result.name=name;runs.append(result)
        stress=replace(base,fee_rate=cfg.fee_rate*2,slippage=cfg.slippage*2)
        stressed=simulate(development,stress,spec,warm,[(ts,replace(stress,model_path=path)) for ts,path in models[family]])
        windows=[]
        for label,first,last in segments(development,'fortnight'):
            absolute=start_forward+first
            replay=simulate(development[first:last],base,spec,frames[absolute-LOOKBACK:absolute],schedule)
            windows.append({'window':label,**trade_stats(replay)})
        rows=monthly[name]
        summary={'candidate':name,'family':family,'months':rows,'continuous_forward':trade_stats(result),
                 'double_cost_stress':trade_stats(stressed),'fortnight':windows,
                 'monthly_median_score':finite_median([r['composite_score'] for r in rows]),
                 'positive_months':sum(r['net_return']>0 for r in rows),
                 'compounded_independent_month_return':math.prod(1+r['net_return'] for r in rows)-1,
                 'model_schedule':[{'effective_at':ts,'path':path,'sha256':digest(path)} for ts,path in models[family]],
                 'note':'Original2025development with supplemental2024training; monthly resets differ from continuous carry-forward. No holdout consumed.'}
        summaries.append(summary);(root/f'{name}-continuous.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
        print(f"{name}: continuous {summary['continuous_forward']['net_return']:.2%}, stress {summary['double_cost_stress']['net_return']:.2%}",flush=True)
    weight=min(cfg.max_pair_weight,cfg.max_total_weight/2)
    runs.extend([benchmark(development,cfg,spec,'cash',{}),benchmark(development,cfg,spec,'btc_buy_hold',{'BTC/USD':1}),
                 benchmark(development,cfg,spec,'allocation_matched',{'BTC/USD':weight,'ETH/USD':weight})])
    (root/'summary.json').write_text(json.dumps(summaries,indent=2,allow_nan=False))
    provenance={**registry,'portfolio_configs':{r['candidate']:[m['config'] for m in r['months']] for r in summaries},
                'model_schedules':{r['candidate']:r['model_schedule'] for r in summaries},
                'configuration_note':'Top-level config supplies shared risk/execution settings; actual policy configs and schedules are separate.'}
    write_report(root/'continuous',{'development':runs},cfg,spec,provenance)
    assert not Path('data/historical/test.csv').exists() and not Path('data/historical/test-access.json').exists()
    print('Batch07 complete; original validation/test untouched.',flush=True)


if __name__=='__main__':main()
