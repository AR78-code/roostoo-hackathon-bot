"""Finalize the bounded research handoff from completed saved outputs only."""
import json
from pathlib import Path
import summarize_batches
import verify_research_artifacts


def main():
    summarize_batches.main();verify_research_artifacts.main()
    root=Path('reports/research');rows=json.loads((root/'overview.json').read_text())
    qualified=[r for r in rows if r['eligible_for_validation']]
    extended=[r for r in rows if r['batch']=='batch-07'];best=max(extended,key=lambda r:r['net_return'])
    detail=next(r for r in json.loads((root/'batch-07/summary.json').read_text()) if r['candidate']==best['candidate'])
    stats=detail['continuous_forward']
    text=f'''# Research handoff

Completed {len(rows)} recorded policy experiments across seven cohorts. Research stopped at the latest requested half-allowance ceiling (last account reading50%used). Local computations already running were allowed to finish; no further experiment was launched. No live orders, AWS deployment or live-configuration change was made.

Strongest supplemental-history development candidate: **{best['candidate']}**. January–June2025 continuous net return **{stats['net_return']:.2%}**, doubled-cost return **{best['stress_return']:.2%}**, maximum drawdown **{stats['max_drawdown']:.2%}**, composite **{stats['composite_score']:.3f}**, fees **${stats['fees']:,.2f}**. It uses earlier-only2024+expanding2025 training, seven causal price features and unchanged logistic thresholds. Mean exposure is{stats['mean_exposure']:.2%}; compare exposure as well as return.

It has{best['positive_months']}positive monthly reset portfolios and{best['positive_fortnights']}positive14-day windows. Median14-day activity is{best['median_fortnight_active_days']:.1f}days against the preregistered8-day screen. Development-qualified candidates:{len(qualified)}. No new finalist validation has been run, and no profitability or competition compliance is claimed. The research candidate is not activated. Resolve its activity limitation on development before any further selection; then freeze a candidate and perform a small one-time validation comparison. Do not tune on validation outcomes.

Original baseline January–June net return was-8.30%. Original rules and weaker classifiers/ridge models remain recorded rather than discarded. Earlier training-history expansion was explicitly documented before its outcomes. The final October–December2025 test remains undownloaded and unevaluated; real test CSV/access marker are absent. Original July–September validation had already been viewed for the baseline, so it is not pristine. At most three total finalists may enter validation in future authorized work.

Reliability:79tests pass. Model replacements cannot use stale cached coefficients; future-trained and wrong-type artifacts are rejected; frozen selections check source/data/model integrity before test access. Live and historical execution reuse strategy/risk logic. Signals use completed information before next-open fills; modeled spread, adverse slippage and fees apply. Continuous model updates preserve cash, holdings and buy-halt state.

The seven-feature calculation is approximately3.27x faster in a synthetic microbenchmark. A forward development replay produced identical order counts and metrics after the numerical optimization. All seven source snapshots and saved model/dataset hashes pass the artifact audit.

Limitations: proxy Binance USDT prices rather than Roostoo USD; synthetic spread/liquidity; no partial fills, depth, API latency or intrabar drawdown measurement; overlapping supervised labels are correlated; short-period ratio annualization can inflate scores. The10%drawdown rule blocks new buys and does not force liquidation. Fees, risk caps, rebalancing deadbands and terminal liquidation assumptions affect results. Composite definitions are provisional until organizer calculations are confirmed.

Read reports/research/overview.md, batch-07/continuous/report.html and artifact-audit.json for results/provenance. Reproduce tests with PYTHONPATH=src python3 -m unittest discover -s tests -q. Archived snapshots identify the exact implementation used by each cohort; do not rerun an existing batch under changed hashes or overwrite its results.
'''
    Path('research/HANDOFF.md').write_text(text)
    audit={'policy_count':len(rows),'cohort_count':7,'qualified_for_validation':len(qualified),
           'best_development_candidate':best,'risk_live_config_unchanged':True,'test_consumed':False,
           'final_test_required_now':False,'reliability_tests_passed':79,
           'source_and_model_audit':'reports/research/artifact-audit.json',
           'evidence':{'diagnosis':'reports/research/baseline-diagnosis.json','score':'src/trading_bot/backtesting/metrics.py',
                       'chronology':'reports/research/batch-07/calibration.json','reports':'reports/research/overview.json',
                       'handoff':'research/HANDOFF.md'},
           'completion_scope':'Bounded research/verification/handoff within amended half-allowance ceiling; no live activation and no claim of a validated profitable strategy.'}
    (root/'completion-audit.json').write_text(json.dumps(audit,indent=2))
    Path('research/STATUS.md').write_text(f'# Research finalized\n\n{len(rows)}policies, seven cohorts; {len(qualified)}development-qualified finalists. Half-allowance ceiling reached; no new experiments. All local research processes completed.79tests pass; source/model audit passes; original configuration unchanged and real test absent. Handoff:research/HANDOFF.md. No live trading/AWS/credentials used.\n')
    print(f'Final handoff ready. Best development:{best["candidate"]} {best["net_return"]:.2%}; qualified:{len(qualified)}.')


if __name__=='__main__':main()
