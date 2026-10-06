"""Summarize completed development experiments without opening market validation/test."""
import json
import statistics
from pathlib import Path


def main():
    root=Path('reports/research')
    rows=[]
    for batch in ('batch-01','batch-02','batch-04','batch-06'):
        if not (root/batch/'ranking.json').exists():
            continue
        for row in json.loads((root/batch/'ranking.json').read_text()):
            detail=json.loads((root/batch/f"{row['name']}.json").read_text())
            rows.append({'batch':batch,'candidate':row['name'],'scope':'Jan–Jun continuous',
                'net_return':row['return'],'median_monthly_score':row['monthly_median_score'],
                'positive_months':row['positive_months'],'fees':detail['overall']['fees'],
                'max_drawdown':detail['overall']['max_drawdown'],'stress_return':row['stress_return'],
                'median_fortnight_active_days':statistics.median(r['active_days'] for r in detail['fortnight']),
                'eligible_for_validation':row['return']>0 and row['stress_return']>0 and row['positive_months']>=4
                    and detail['positive_fortnights']>=6
                    and statistics.median(r['active_days'] for r in detail['fortnight'])>=8})
    for row in json.loads((root/'batch-03'/'summary.json').read_text()):
        rows.append({'batch':'batch-03','candidate':row['candidate'],'scope':'Mar–Jun independent monthly portfolios',
            'net_return':row['compounded_independent_month_return'],'median_monthly_score':row['monthly_median_score'],
            'positive_months':row['positive_months'],'fees':sum(r['fees'] for r in row['months']),
            'max_drawdown':max(r['max_drawdown'] for r in row['months']),
            'eligible_for_validation':False,'note':'Negative total forward-development return; not eligible. Does not share the full-period rule-candidate evaluation start/state.'})
    if (root/'batch-03/continuous/candidate-summary.json').exists():
        continuous={r['candidate']:r for r in json.loads((root/'batch-03/continuous/candidate-summary.json').read_text())}
        for row in rows:
            if row['batch']=='batch-03':
                detail=continuous[row['candidate']];stats=detail['continuous_forward']
                row['independent_month_compounded_return']=row['net_return']
                row.update(scope='Mar–Jun continuous forward',net_return=stats['net_return'],fees=stats['fees'],
                           max_drawdown=stats['max_drawdown'],stress_return=detail['double_cost_stress']['net_return'],
                           note='Monthly median score comes from reset portfolios; continuous return carries holdings and risk state. No new policies were fitted or tuned.')
    if (root/'batch-05/summary.json').exists():
        for row in json.loads((root/'batch-05/summary.json').read_text()):
            stats=row['continuous_forward']
            rows.append({'batch':'batch-05','candidate':row['candidate'],'scope':'Mar–Jun continuous forward',
                         'net_return':stats['net_return'],'median_monthly_score':row['monthly_median_score'],
                         'positive_months':row['positive_months'],'fees':stats['fees'],'max_drawdown':stats['max_drawdown'],
                         'stress_return':row['double_cost_stress']['net_return'],'eligible_for_validation':False,
                         'note':'Negative continuous forward return. Earlier-only ridge fits; monthly scores reset independently.'})
    if (root/'batch-07/summary.json').exists():
        for row in json.loads((root/'batch-07/summary.json').read_text()):
            stats=row['continuous_forward'];stress=row['double_cost_stress']['net_return']
            positive_windows=sum(r['net_return']>0 for r in row['fortnight'])
            activity=statistics.median(r['active_days'] for r in row['fortnight'])
            eligible=stats['net_return']>0 and stress>0 and row['positive_months']>=4 and positive_windows>=6 and activity>=8
            rows.append({'batch':'batch-07','candidate':row['candidate'],'scope':'Jan–Jun continuous forward; 2024+ earlier training',
                         'net_return':stats['net_return'],'median_monthly_score':row['monthly_median_score'],
                         'positive_months':row['positive_months'],'fees':stats['fees'],'max_drawdown':stats['max_drawdown'],
                         'stress_return':stress,'positive_fortnights':positive_windows,'median_fortnight_active_days':activity,
                         'eligible_for_validation':eligible,'note':'Training-history amendment recorded before outcomes; original holdouts untouched.'})
    (root/'overview.json').write_text(json.dumps(rows,indent=2,allow_nan=False))
    lines=['# Development research: completed cohorts','',
        'Actual final test remains undownloaded and unevaluated. No new candidate validation runs have been made. Original live configuration is unchanged.','',
        '| Candidate | Scope | Net return | Median monthly score | Fees |','|---|---|---:|---:|---:|']
    for row in rows:
        score='N/A' if row['median_monthly_score'] is None else f"{row['median_monthly_score']:.3f}"
        lines.append(f"| {row['candidate']} | {row['scope']} | {row['net_return']:.2%} | {score} | ${row['fees']:,.0f} |")
    lines += ['', '## Findings','',
        f"- {sum(r['eligible_for_validation'] for r in rows)} completed candidates meet the preregistered development promotion screens. Positive development results alone do not establish a profitable live strategy.",
        '- Slower SMA windows and wider signal thresholds reduce turnover/fees. They do not by themselves create positive development returns.',
        '- Smaller volatility-aware allocations reduce drawdowns and losses but also reduce market exposure; do not confuse this with stronger predictive skill.',
        '- The supervised classifier is fitted on earlier data only. Its March–June forward results have two positive and two negative months. All three probability policies lose money across the four independent monthly portfolios.',
        '- One classifier policy scores 27.708 in May despite only about 0.072% return, two strategy orders and one active day. Tiny drawdown and short-period annualization can inflate Calmar; this is not an acceptable competition candidate simply because its raw score is high.',
        '- Monthly resets/warm-up and the continuous full-period drawdown latch are different experiments. The reported monthly compounded classifier return is explicitly not a continuously managed portfolio track record.',
        '- Rule cohorts include chronological parameter-selection records in walk_forward.json. Retrospective ranking alone is not claimed as forward performance.',
        '- The classifier loses to an earlier-training constant probability on forward log loss and Brier score in three of four months. See research/AUDIT.md.',
        '- The expected-return ridge challenger also loses to an earlier-training mean predictor on forward squared error in three of four months. All three continuous March–June policies lose money; no trained model is qualified for promotion.',
        '- Removing the buy halt is not a demonstrated improvement: the baseline loss worsens to 21.72%, and the slower trend still loses money with 14.85% drawdown. Live risk limits remain unchanged.',
        '- Execution cashflow decomposition of the original validation run: about $25 before commission, versus about $6,204 commissions. This holds recorded trades fixed and includes spread/slippage; it is not a no-cost counterfactual.',
        '', '## Reproducibility','',
        'Every cohort retains registry.json, per-candidate configurations/results and archived source. Trained March–June coefficient/scaler artifacts are under config/models. The final test must remain untouched.']
    (root/'overview.md').write_text('\n'.join(lines)+'\n')
    print(f"Summarized {len(rows)} candidate policies; {sum(r['eligible_for_validation'] for r in rows)} development-qualified.")


if __name__=='__main__':main()
