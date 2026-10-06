import csv
from dataclasses import asdict
import html
import json
import platform
from pathlib import Path

from .data import iso
from .metrics import metrics


ASSUMPTIONS = [
    "Composite score is 0.4 Sortino + 0.3 Sharpe + 0.3 Calmar using the documented research definitions, without normalization. It is undefined if any component is undefined; this is not a verified reproduction of organizer calculations.",
    "Completed bar closes feed the configured strategy; signals execute at the next bar open. Sizing uses only that open and current holdings, never that bar's high/low/close.",
    "Existing risk.plan handles sizing, free balance, reserve, spread, rounding, order caps and buy halts. At most one strategy order per bar; sells have priority as in the live engine.",
    "Each split starts with fresh cash and risk state. Validation/test may use only preceding historical closes for indicator warm-up, without trading before the split.",
    "Binance USDT prices are a proxy for Roostoo USD prices, assuming 1 USDT = 1 USD. Candle closes approximate the live bot's sampled ticker prices.",
    "Bid/ask are synthetic from a constant configured spread. Market orders fill at open plus spread and adverse configured slippage; fees apply to executed notional. No partial fills, depth, volume limits, network latency or API outages are modeled.",
    "All portfolios are liquidated at the last close minus spread/slippage with fees. These terminal accounting fills bypass per-order caps/precision and are separated from strategy-generated trades.",
    "Cash earns zero. BTC buy/hold invests 100% including its entry fee. Allocation-matched buy/hold uses the configured maximum BTC/ETH target weights initially, leaves the remainder in cash, and does not rebalance. Passive benchmarks bypass strategy limits and buy halts.",
    "Sharpe uses sample standard deviation of full UTC-day returns; Sortino uses root mean squared negative daily returns including zero downside on positive days. Both annualize with sqrt(365), zero risk-free rate and zero target return.",
    "Calmar is calendar-time CAGR divided by maximum recorded drawdown. Ratios with fewer than two full days, zero variance/downside, or zero drawdown are N/A rather than fabricated infinities. Annualization over short periods can be misleading.",
    "Maximum drawdown uses recorded bar-close equity and initial equity, including terminal costs. Intrabar losses may be larger. Buy-halt decisions check observed opens and closes, not intrabar highs/lows.",
    "Turnover is total absolute executed notional divided by mean recorded equity, including entry/exit costs and terminal sales; it is not half-turnover or annualized.",
    "Fixed chronological splits reduce leakage but do not establish statistical significance or profitability. Repeated validation selection can still overfit. Held-out data should be evaluated once after the strategy is frozen.",
]


def write_csv(path, rows):
    if not rows:
        path.write_text('')
        return
    with path.open('w', newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def write_report(output, runs, cfg, spec, provenance):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    summary={'runtime':{'python':platform.python_version(),'platform':platform.platform()},'config':asdict(cfg),'backtest_spec':spec,'provenance':provenance,'assumptions':ASSUMPTIONS,'periods':{}}
    flat=[]
    for period, results in runs.items():
        summary['periods'][period]={}
        for result in results:
            stats=metrics(result)
            summary['periods'][period][result.name]=stats
            flat.append({'period':period,'portfolio':result.name,**stats})
            write_csv(output/f'{period}-{result.name}-equity.csv',result.curve)
            write_csv(output/f'{period}-{result.name}-trades.csv',result.trades)
            if result.signals:
                write_csv(output/f'{period}-{result.name}-signals.csv',result.signals)
    (output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))
    write_csv(output/'metrics.csv',flat)
    columns=['composite_score','net_return','max_drawdown','sharpe','sortino','calmar','turnover','fees','trade_count']
    labels=['Composite','Net return','Max drawdown','Sharpe','Sortino','Calmar','Turnover','Fees ($)','Trades']
    def formatted(key,value):
        if value is None:return 'N/A'
        if key in ('net_return','max_drawdown'):return f'{value:.2%}'
        if key=='trade_count':return str(value)
        return f'{value:,.3f}'
    tables=[]
    md=['# Historical backtest report','',f"Test access: **{provenance.get('test_status','HELD OUT')}**",'']
    for period in runs:
        bounds=spec[period]
        heading=f'{period.title()}: {bounds["start"]} to {bounds["end"]} (end exclusive, UTC)'
        md += ['## '+heading,'','| Portfolio | '+' | '.join(labels)+' |','|---|'+'---|'*len(labels)]
        body=[]
        for row in flat:
            if row['period']!=period:continue
            cells=[formatted(k,row[k]) for k in columns]
            md.append('| '+row['portfolio']+' | '+' | '.join(cells)+' |')
            body.append('<tr><th>'+html.escape(row['portfolio'])+'</th>'+''.join('<td>'+v+'</td>' for v in cells)+'</tr>')
        md+=['',f'Equity curves and trade journals: `{period}-*-equity.csv`, `{period}-*-trades.csv`.','']
        tables.append('<h2>'+heading+'</h2><table><thead><tr><th>Portfolio</th>'+''.join('<th>'+x+'</th>' for x in labels)+'</tr></thead><tbody>'+''.join(body)+'</tbody></table>')
    md+=['## Assumptions and limitations','']+['- '+a for a in ASSUMPTIONS]+['','## Reproducibility','', 'Configuration, source-code hashes and dataset hashes are recorded in `summary.json`.']
    (output/'report.md').write_text('\n'.join(md)+'\n')
    markup="""<!doctype html><html><head><meta charset="utf-8"><title>Historical backtest report</title><style>
body{font:16px system-ui;margin:40px auto;max-width:1200px;padding:0 24px;color:#17212b;background:#f8fafc}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #ddd;text-align:right}th:first-child{text-align:left}h1,h2{color:#12314b}li{margin-bottom:12px}.badge{padding:14px;background:#e5eef5;border-radius:8px}img{max-width:100%}</style></head><body><h1>Historical backtest report</h1>"""
    markup+='<p class="badge">Test access: '+html.escape(provenance.get('test_status','HELD OUT'))+'. Returns include simulated costs; historical results do not predict future performance.</p>'
    markup+=''.join(tables)+'<div id="charts"></div><h2>Assumptions and limitations</h2><ul>'+''.join('<li>'+html.escape(a)+'</li>' for a in ASSUMPTIONS)+'</ul><p>Full metrics: <a href="metrics.csv">CSV</a>. Reproducibility record: <a href="summary.json">JSON</a>.</p></body></html>'
    (output/'report.html').write_text(markup)
    return summary
