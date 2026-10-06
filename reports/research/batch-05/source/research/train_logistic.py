"""Fixed-settings expanding-window model fitting; only development prices used."""
from dataclasses import replace
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import statistics
import numpy as np

from trading_bot.config import load
from trading_bot.ml import FEATURE_NAMES,LOOKBACK,features
from trading_bot.backtesting.cli import code_hashes
from trading_bot.backtesting.data import digest,load_period,load_spec
from trading_bot.backtesting.metrics import metrics
from trading_bot.backtesting.simulator import simulate
from run_batch import segments,write_candidate,finite_median

HORIZON=288
AVAILABILITY_BUFFER=288
POLICIES=[('ml_entry055',.55,.40,0),('ml_entry060',.60,.45,0),('ml_entry055_vol01',.55,.40,.01)]


def feature_matrix(closes):
    indices=np.arange(LOOKBACK-1,len(closes))
    logs=np.log(closes)
    columns=[logs[indices]-logs[indices-lag] for lag in (12,72,288,864)]
    cumulative=np.r_[0,np.cumsum(closes)]
    def mean(window):return (cumulative[indices+1]-cumulative[indices+1-window])/window
    changes=np.r_[0,np.diff(logs)]
    total=np.r_[0,np.cumsum(changes)]
    square=np.r_[0,np.cumsum(changes**2)]
    means=(total[indices+1]-total[indices+1-288])/288
    variance=(square[indices+1]-square[indices+1-288])/288-means**2
    columns.extend([mean(144)/mean(576)-1,np.sqrt(np.maximum(variance,0))*math.sqrt(288),closes[indices]/mean(1152)-1])
    return indices,np.column_stack(columns)


def fit(x,y):
    mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale>1e-12,scale,1)
    normalized=(x-mean)/scale
    coefficients=np.zeros(x.shape[1])
    prior=float(y.mean())
    intercept=math.log(max(1e-6,prior)/max(1e-6,1-prior))
    for _ in range(300):
        logits=np.clip(normalized@coefficients+intercept,-40,40)
        probability=1/(1+np.exp(-logits))
        error=probability-y
        coefficients-=.1*(normalized.T@error/len(y)+.01*coefficients)
        intercept-=.1*error.mean()
    predictions=1/(1+np.exp(-np.clip(normalized@coefficients+intercept,-40,40)))
    logloss=float(-(y*np.log(np.maximum(predictions,1e-12))+(1-y)*np.log(np.maximum(1-predictions,1e-12))).mean())
    return {'mean':mean.tolist(),'scale':scale.tolist(),'coefficients':coefficients.tolist(),'intercept':float(intercept),
        'training_rows':len(y),'positive_label_fraction':prior,'training_logloss':logloss,
        'constant_prior_logloss':-prior*math.log(max(prior,1e-12))-(1-prior)*math.log(max(1-prior,1e-12)),
        'fit_settings':{'iterations':300,'learning_rate':.1,'l2_penalty':.01}}


def main():
    root=Path('reports/research/batch-03');root.mkdir(parents=True,exist_ok=True)
    cfg=load('config/bot.toml');spec=load_spec('config/backtest.toml')
    registry={'policies':POLICIES,'label_horizon_bars':HORIZON,'availability_buffer_bars':AVAILABILITY_BUFFER,
        'code_sha256':code_hashes(),'script_sha256':digest(__file__),'data_sha256':digest('data/historical/development.csv'),
        'feature_names':FEATURE_NAMES,'protocol':'Fit earlier development data only, purge horizon, one-day availability buffer, evaluate next month. No validation/test access.'}
    path=root/'registry.json'
    if path.exists():raise ValueError('Batch 03 already exists; do not overwrite prior ML experiments')
    path.write_text(json.dumps(registry,indent=2))
    frames=load_period('data/historical/development.csv','development',spec,cfg.pairs)
    times=np.array([f['BTC/USD'].timestamp for f in frames])
    prepared={}
    for pair in cfg.pairs:
        closes=np.array([f[pair].close for f in frames]);opens=np.array([f[pair].open for f in frames])
        indices,x=feature_matrix(closes)
        # Verify vectorized training features equal the pure-Python live features.
        for index in (LOOKBACK-1,LOOKBACK+100,len(closes)-1):
            np.testing.assert_allclose(x[index-(LOOKBACK-1)],features(closes[index-(LOOKBACK-1):index+1].tolist()),rtol=1e-8,atol=1e-10)
        prepared[pair]=(indices,x,opens)
    summaries={name:[] for name,*_ in POLICIES}
    # Four real forward development months, after initial Jan-Feb fitting.
    for month,start,end in list(segments(frames,'monthly'))[2:]:
        cutoff=start-AVAILABILITY_BUFFER
        xs=[];ys=[]
        for pair,(indices,x,opens) in prepared.items():
            eligible=indices+HORIZON+1<cutoff
            picked=indices[eligible]
            entry=opens[picked+1]*(1+spec['spread_bps']/20000)*(1+cfg.slippage)*(1+cfg.fee_rate)
            exit=opens[picked+HORIZON+1]*(1-spec['spread_bps']/20000)*(1-cfg.slippage)*(1-cfg.fee_rate)
            xs.append(x[eligible]);ys.append((exit/entry-1>0).astype(float))
        model=fit(np.vstack(xs),np.concatenate(ys))
        model.update({'feature_names':list(FEATURE_NAMES),'interval_seconds':300,'available_at':int(times[cutoff-1]+300),
            'training_start':int(times[LOOKBACK-1]),'last_label_timestamp':int(times[cutoff-1]),'evaluation_start':int(times[start]),
            'label_horizon_bars':HORIZON,'data_sha256':registry['data_sha256']})
        model_path=Path('config/models')/f'logistic-{month}.json';model_path.parent.mkdir(parents=True,exist_ok=True)
        with model_path.open('x') as handle:json.dump(model,handle,indent=2,allow_nan=False)
        print(f"Fitted {month}: {model['training_rows']} rows, class-positive={model['positive_label_fraction']:.3f}",flush=True)
        for name,entry,exit,volatility in POLICIES:
            candidate=replace(cfg,strategy='logistic',slow_window=LOOKBACK,model_path=str(model_path),model_entry_probability=entry,model_exit_probability=exit,volatility_target=volatility)
            result=simulate(frames[start:end],candidate,spec,frames[start-LOOKBACK:start])
            stats=metrics(result)
            active={datetime.fromtimestamp(t['timestamp'],timezone.utc).date().isoformat() for t in result.trades if t['reason']!='terminal_liquidation'}
            record={'window':month,'model_sha256':digest(model_path),'config':candidate.__dict__,**stats,'active_days':len(active)}
            summaries[name].append(record)
            (root/f'{name}-{month}.json').write_text(json.dumps(record,indent=2,allow_nan=False))
            write_candidate(f'config/candidates/{name}-{month}.toml',candidate)
            print(f"{name} {month}: return={stats['net_return']:.2%}, score={stats['composite_score']}",flush=True)
    overall=[]
    for name,rows in summaries.items():
        overall.append({'candidate':name,'months':rows,'monthly_median_score':finite_median([r['composite_score'] for r in rows]),
            'positive_months':sum(r['net_return']>0 for r in rows),'compounded_independent_month_return':math.prod(1+r['net_return'] for r in rows)-1,
            'note':'Four expanding-fit forward months with independent portfolio resets; compounded number is not an actual continuously managed equity curve.'})
    (root/'summary.json').write_text(json.dumps(overall,indent=2,allow_nan=False))
    assert not Path('data/historical/test.csv').exists()
    print('ML forward-development batch complete. Validation/test untouched.',flush=True)


if __name__=='__main__':main()
