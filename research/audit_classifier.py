"""Forward calibration audit of frozen development models; no fitting or tuning."""
import json
import math
from pathlib import Path
import numpy as np
from trading_bot.config import load
from trading_bot.backtesting.data import load_period, load_spec, digest
from train_logistic import feature_matrix, HORIZON
from run_batch import segments


def scores(y, predictions):
    p=np.clip(predictions,1e-12,1-1e-12)
    return {'logloss':float(-(y*np.log(p)+(1-y)*np.log(1-p)).mean()),
            'brier':float(((p-y)**2).mean()),'mean_prediction':float(p.mean()),
            'positive_fraction':float(y.mean()),'rows':len(y)}


def main():
    cfg=load('config/bot.toml');spec=load_spec('config/backtest.toml')
    frames=load_period('data/historical/development.csv','development',spec,cfg.pairs)
    prepared={}
    for pair in cfg.pairs:
        indices,x=feature_matrix(np.array([f[pair].close for f in frames]))
        prepared[pair]=(indices,x,np.array([f[pair].open for f in frames]))
    records=[]
    for month,start,end in list(segments(frames,'monthly'))[2:]:
        path=Path(f'config/models/logistic-{month}.json');model=json.loads(path.read_text())
        if not model['last_label_timestamp'] < model['available_at'] <= model['evaluation_start']:
            raise ValueError('Invalid fit availability boundary')
        if model['evaluation_start'] != frames[start]['BTC/USD'].timestamp:
            raise ValueError('Evaluation period does not match model metadata')
        ys=[];ps=[]
        for pair,(indices,x,opens) in prepared.items():
            # Labels must end inside this forward month; no next-month outcome.
            mask=(indices>=start)&(indices+HORIZON+1<end)
            picked=indices[mask]
            entry=opens[picked+1]*(1+spec['spread_bps']/20000)*(1+cfg.slippage)*(1+cfg.fee_rate)
            exit=opens[picked+HORIZON+1]*(1-spec['spread_bps']/20000)*(1-cfg.slippage)*(1-cfg.fee_rate)
            y=(exit/entry-1>0).astype(float)
            z=((x[mask]-model['mean'])/model['scale'])@np.array(model['coefficients'])+model['intercept']
            p=1/(1+np.exp(-np.clip(z,-40,40)))
            ys.append(y);ps.append(p)
        y=np.concatenate(ys);p=np.concatenate(ps)
        buckets=[]
        for lower,upper in [(0,.4),(.4,.5),(.5,.6),(.6,1.000001)]:
            mask=(p>=lower)&(p<upper)
            buckets.append({'lower':lower,'upper':upper,**scores(y[mask],p[mask])} if mask.any() else {'lower':lower,'upper':upper,'rows':0})
        records.append({'month':month,'model_sha256':digest(path),'model':scores(y,p),
                        'earlier_training_prior':scores(y,np.full(len(y),model['positive_label_fraction'])),
                        'buckets':buckets})
    result={'note':'Overlapping 24-hour labels are correlated; row counts are not independent observations. These calibration results are development diagnostics, not proof of profitable trading. All model parameters and priors were fit before their forward month.',
            'development_sha256':digest('data/historical/development.csv'),'months':records}
    path=Path('reports/research/batch-03/calibration.json')
    with path.open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False)
    for r in records:
        print(f"{r['month']}: forward logloss={r['model']['logloss']:.4f}, prior={r['earlier_training_prior']['logloss']:.4f}; Brier={r['model']['brier']:.4f}/{r['earlier_training_prior']['brier']:.4f}")


if __name__=='__main__':main()
