import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from ..config import Config, load
from ..state import ProcessLock
from .data import PERIODS, digest, fetch_period, load_period, load_spec
from .report import write_report
from .simulator import run_all


def code_hashes():
    base=Path(__file__).resolve().parents[1]
    paths=sorted(base.rglob('*.py'))
    return {str(p.relative_to(base)):digest(p) for p in paths}


def identity(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def research(data_dir,output,cfg,spec):
    previous=None
    runs={}
    hashes={}
    for period in ('development','validation'):
        path=Path(data_dir)/f'{period}.csv'
        frames=load_period(path,period,spec,cfg.pairs)
        hashes[period]=digest(path)
        warmup=previous[-cfg.slow_window:] if previous else None
        runs[period]=run_all(frames,cfg,spec,warmup)
        previous=frames
    return write_report(output,runs,cfg,spec,{'test_status':'HELD OUT — not loaded or evaluated','data_sha256':hashes,'code_sha256':code_hashes(),
        'model_sha256':digest(cfg.model_path) if cfg.strategy in ('logistic','ridge') else None})


def freeze(data_dir,report,selection,cfg,spec):
    summary=json.loads((Path(report)/'summary.json').read_text())
    if summary['config']!=json.loads(json.dumps(asdict(cfg))) or summary['backtest_spec']!=spec:
        raise ValueError('Research report differs from current config/spec; rerun research before freezing')
    if summary['provenance']['code_sha256']!=code_hashes():
        raise ValueError('Code changed since research; rerun before freezing')
    hashes={p:digest(Path(data_dir)/f'{p}.csv') for p in ('development','validation')}
    if hashes!=summary['provenance']['data_sha256']:
        raise ValueError('Development/validation data changed since research')
    model_sha256=digest(cfg.model_path) if cfg.strategy in ('logistic','ridge') else None
    if summary['provenance'].get('model_sha256')!=model_sha256:
        raise ValueError('Trained model changed since research; rerun before freezing')
    payload={'config':asdict(cfg),'spec':spec,'data_sha256':hashes,'code_sha256':code_hashes(),
        'model_sha256':model_sha256,
        'research_report_sha256':digest(Path(report)/'summary.json'),'frozen_at':datetime.now(timezone.utc).isoformat()}
    envelope={'selection_sha256':identity(payload),'selection':payload}
    Path(selection).parent.mkdir(parents=True,exist_ok=True)
    with Path(selection).open('x') as handle:
        json.dump(envelope,handle,indent=2)
    return envelope


def final(data_dir,output,selection,allow_test):
    if not allow_test:
        raise ValueError("Final evaluation requires --allow-test; test remains untouched")
    lock = ProcessLock(Path(data_dir) / "final-evaluation.lock")
    try:
        return _final(data_dir,output,selection,allow_test)
    finally:
        lock.close()


def _final(data_dir,output,selection,allow_test):
    if not allow_test:
        raise ValueError('Final evaluation requires --allow-test; test remains untouched')
    envelope=json.loads(Path(selection).read_text())
    payload=envelope['selection']
    if identity(payload)!=envelope['selection_sha256']:
        raise ValueError('Frozen selection checksum mismatch')
    if payload['code_sha256']!=code_hashes():
        raise ValueError('Code differs from frozen selection; no test data was loaded')
    cfg_values=dict(payload['config']);cfg_values['pairs']=tuple(cfg_values['pairs'])
    cfg=Config(**cfg_values);spec=payload['spec']
    if cfg.strategy in ('logistic','ridge') and digest(cfg.model_path)!=payload.get('model_sha256'):
        raise ValueError('Trained model differs from frozen selection')
    from .data import validate_spec
    validate_spec(spec)
    for p in ('development','validation'):
        if digest(Path(data_dir)/f'{p}.csv')!=payload['data_sha256'][p]:
            raise ValueError('Earlier data differs from frozen selection')
    marker=Path(data_dir)/'test-access.json'
    token=envelope['selection_sha256']
    if marker.exists():
        prior=json.loads(marker.read_text())
        if prior['selection_sha256']!=token:
            raise ValueError('Test already accessed for another selection; it is no longer an untouched holdout')
        if prior.get('completed'):
            raise ValueError('Final evaluation already completed; read the existing report: '+prior['output'])
    else:
        marker.write_text(json.dumps({'selection_sha256':token,'accessed_at':datetime.now(timezone.utc).isoformat(),'completed':False},indent=2))
    test_path=Path(data_dir)/'test.csv'
    if not test_path.exists():
        fetch_period(data_dir,'test',spec,cfg.pairs)
    frames=load_period(test_path,'test',spec,cfg.pairs)
    validation=load_period(Path(data_dir)/'validation.csv','validation',spec,cfg.pairs)
    runs={'test':run_all(frames,cfg,spec,validation[-cfg.slow_window:])}
    summary=write_report(output,runs,cfg,spec,{'test_status':'FINAL EVALUATION — holdout now consumed',
        'selection_sha256':token,'data_sha256':{'test':digest(test_path),**payload['data_sha256']},'code_sha256':code_hashes()})
    marker.write_text(json.dumps({'selection_sha256':token,'completed':True,'output':str(Path(output).resolve()),'test_sha256':digest(test_path)},indent=2))
    return summary


def main():
    parser=argparse.ArgumentParser(description='Historical backtesting with guarded chronological holdout')
    parser.add_argument('command',choices=('fetch','research','freeze','final'))
    parser.add_argument('--config',default='config/bot.toml')
    parser.add_argument('--spec',default='config/backtest.toml')
    parser.add_argument('--data-dir',default='data/historical')
    parser.add_argument('--output',default=None)
    parser.add_argument('--period',choices=('development','validation'),default='development')
    parser.add_argument('--research-report',default='reports/baseline')
    parser.add_argument('--selection',default='reports/selection.json')
    parser.add_argument('--allow-test',action='store_true')
    args=parser.parse_args()
    if args.command=='final':
        final(args.data_dir,args.output or 'reports/final',args.selection,args.allow_test)
    else:
        cfg=load(args.config);spec=load_spec(args.spec)
        if cfg.interval_seconds!=spec['interval_seconds']:
            raise ValueError('Bot polling interval and historical interval must match')
        if set(cfg.pairs)!={'BTC/USD','ETH/USD'}:
            raise ValueError('Historical suite currently requires BTC/USD and ETH/USD')
        if args.command=='fetch':
            fetch_period(args.data_dir,args.period,spec,cfg.pairs)
        elif args.command=='research':
            research(args.data_dir,args.output or 'reports/baseline',cfg,spec)
        else:
            freeze(args.data_dir,args.research_report,args.selection,cfg,spec)
    print(f'{args.command} completed',flush=True)
    return 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,RuntimeError,OSError,KeyError,TypeError) as exc:
        print(f'Backtest stopped: {exc}',file=sys.stderr)
        sys.exit(1)
