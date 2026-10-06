"""Optional standard matplotlib figures from a completed report; reads no market data."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('report_dir')
    args=parser.parse_args()
    root=Path(args.report_dir)
    summary=json.loads((root/'summary.json').read_text())
    images=[]
    for period,portfolios in summary['periods'].items():
        fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,layout='constrained')
        for name in portfolios:
            with (root/f'{period}-{name}-equity.csv').open() as handle:
                rows=list(csv.DictReader(handle))
            ts=[datetime.fromtimestamp(float(r['timestamp']),timezone.utc) for r in rows]
            values=[float(r['equity']) for r in rows]
            high=values[0];dd=[]
            for value in values:
                high=max(high,value);dd.append((value/high-1)*100)
            axes[0].plot(ts,[v/values[0]*100 for v in values],label=name,lw=1.2)
            axes[1].plot(ts,dd,label=name,lw=1.2)
        axes[0].set(title=f'{period.title()} — net of simulated fees, spread and slippage',ylabel='Equity (initial = 100)')
        axes[1].set(ylabel='Drawdown (%)',xlabel='UTC')
        axes[0].legend(ncol=2)
        for axis in axes:axis.grid(alpha=.2)
        path=root/f'{period}-performance.png'
        fig.savefig(path,dpi=150)
        plt.close(fig)
        images.append(f'<h2>{period.title()} curves</h2><img src="{path.name}" alt="Equity and drawdown curves for {period}">')
    page=root/'report.html'
    page.write_text(page.read_text().replace('<div id="charts"></div>','<div id="charts">'+''.join(images)+'</div>'))
    print('Wrote performance plots')


if __name__=='__main__':main()
