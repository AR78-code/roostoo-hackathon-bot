"""Audit saved experiment provenance and real-test isolation without reading prices."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root=Path('reports/research');checks=[]
    for number in range(1,8):
        batch=root/f'batch-{number:02d}'
        registry=json.loads((batch/'registry.json').read_text())
        verified=[]
        for relative,expected in registry['code_sha256'].items():
            path=batch/'source/src/trading_bot'/relative
            if not path.exists():path=batch/'source'/relative
            if not path.exists() or sha(path)!=expected:
                raise ValueError(f'Archived source mismatch: {path}')
            verified.append(relative)
        sources=registry['data_sha256']
        sources=sources if isinstance(sources,dict) else {'data/historical/development.csv':sources}
        for path,expected in sources.items():
            if sha(Path(path))!=expected:raise ValueError(f'Dataset changed: {path}')
        checks.append({'batch':batch.name,'archived_source_modules_verified':len(verified),
                       'dataset_checksums_verified':list(sources)})
    models=[]
    for path in sorted(Path('config/models').glob('*.json')):
        model=json.loads(path.read_text())
        if not model['last_label_timestamp']<model['available_at']<=model['evaluation_start']:
            raise ValueError(f'Invalid model chronology: {path}')
        models.append({'path':str(path),'sha256':sha(path),'available_at':model['available_at'],'evaluation_start':model['evaluation_start']})
    for batch_number in (3,5,7):
        batch=root/f'batch-{batch_number:02d}'
        if not (batch/'summary.json').exists():raise ValueError(f'Incomplete batch: {batch}')
        for record in json.loads((batch/'summary.json').read_text()):
            for month in record['months']:
                if sha(Path(month['config']['model_path']))!=month['model_sha256']:
                    raise ValueError('Model differs from evaluated artifact')
    if Path('data/historical/test.csv').exists() or Path('data/historical/test-access.json').exists():
        raise ValueError('Real test was consumed')
    if Path('config/bot.toml').read_bytes()!=(root/'batch-03/source/bot.toml').read_bytes():
        raise ValueError('Original live configuration changed')
    result={'cohorts':checks,'models':models,'real_test_csv_present':False,'real_test_access_marker_present':False,
            'original_bot_config_unchanged':True,'note':'Verifies saved source/data/model checksums and chronology. Tests establish runtime behavior separately. No price rows or validation/test files opened.'}
    (root/'artifact-audit.json').write_text(json.dumps(result,indent=2))
    print(f'Verified seven cohort snapshots and {len(models)} model artifacts; original config unchanged and real test absent.')


if __name__=='__main__':main()
