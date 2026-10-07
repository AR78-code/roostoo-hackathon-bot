"""Read-only deployment diagnostics; local order days are not certified eligibility."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('database', help='Existing bot.sqlite3 file; never creates a database')
args = parser.parse_args()
path = Path(args.database).resolve(strict=True)
db = sqlite3.connect('file:' + quote(str(path), safe='/') + '?mode=ro', uri=True)
try:
    def get(key):
        row = db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None
    daily = {}
    for ts, in db.execute("SELECT ts FROM orders WHERE status='FILLED'"):
        date = datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
        daily[date] = daily.get(date, 0) + 1
    mode = get('mode')
    result = {'mode': mode, 'last_success': get('last_success'),
        'drawdown_halt': get('drawdown_halt'),
        'unresolved_orders': db.execute("SELECT COUNT(*) FROM orders WHERE status IN ('SUBMITTING','UNKNOWN','PENDING')").fetchone()[0],
        'samples': {pair: {'count': count, 'latest_timestamp': latest} for pair,count,latest in
            db.execute('SELECT pair,COUNT(*),MAX(ts) FROM samples GROUP BY pair')},
        'filled_orders_by_utc_day': dict(sorted(daily.items())),
        'days_with_filled_orders': len(daily),
        'competition_days_certified': False,
        'note': 'Local order-intent timestamps grouped in UTC. Organizer timezone and sufficient-trades threshold need confirmation. Only live fills concern competition activity.'}
    if mode != 'live': result['note'] += ' This is simulated activity and contributes no competition trading days.'
    print(json.dumps(result, indent=2))
finally:
    db.close()
