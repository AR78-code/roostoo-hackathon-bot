# Research handoff

Completed 45 recorded policy experiments across seven cohorts. Research stopped at the latest requested half-allowance ceiling (last account reading 50% used). Local computations already running were allowed to finish; no further experiment was launched. No live orders, AWS deployment or live-configuration change was made.

Strongest supplemental-history development candidate: **extended_ml_entry060**. January–June 2025 continuous net return **5.06%**, doubled-cost return **2.61%**, maximum drawdown **5.90%**, composite **1.654**, fees **$950.01**. It uses earlier-only 2024 + expanding 2025 training, seven causal price features and unchanged logistic thresholds. Mean exposure is 4.81%; compare exposure as well as return.

It has 5 positive monthly reset portfolios and 8 positive 14-day windows. Median14-day activity is 4.0 days against the preregistered 8-day screen. Development-qualified candidates: 0. No new finalist validation has been run, and no profitability or competition compliance is claimed. The research candidate is not activated. Resolve its activity limitation on development before any further selection; then freeze a candidate and perform a small one-time validation comparison. Do not tune on validation outcomes.

Original baseline January–June net return was-8.30%. Original rules and weaker classifiers/ridge models remain recorded rather than discarded. Earlier training-history expansion was explicitly documented before its outcomes. The final October–December 2025 test remains undownloaded and unevaluated; real test CSV/access marker are absent. Original July–September validation had already been viewed for the baseline, so it is not pristine. At most three total finalists may enter validation in future authorized work.

Reliability: 79 tests pass. Model replacements cannot use stale cached coefficients; future-trained and wrong-type artifacts are rejected; frozen selections check source/data/model integrity before test access. Live and historical execution reuse strategy/risk logic. Signals use completed information before next-open fills; modeled spread, adverse slippage and fees apply. Continuous model updates preserve cash, holdings and buy-halt state.

The seven-feature calculation is approximately 3.27x faster in a synthetic microbenchmark. A forward development replay produced identical order counts and metrics after the numerical optimization. All seven source snapshots and saved model/dataset hashes pass the artifact audit.

Limitations: proxy Binance USDT prices rather than Roostoo USD; synthetic spread/liquidity; no partial fills, depth, API latency or intrabar drawdown measurement; overlapping supervised labels are correlated; short-period ratio annualization can inflate scores. The 10% drawdown rule blocks new buys and does not force liquidation. Fees, risk caps, rebalancing deadbands and terminal liquidation assumptions affect results. Composite definitions are provisional until organizer calculations are confirmed.

Read reports/research/overview.md, batch-07/continuous/report.html and artifact-audit.json for results/provenance. Reproduce tests with PYTHONPATH=src python3 -m unittest discover -s tests -q. Archived snapshots identify the exact implementation used by each cohort; do not rerun an existing batch under changed hashes or overwrite its results.
