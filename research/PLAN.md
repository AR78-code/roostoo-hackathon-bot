# Research plan — started October 1, 2026

Authorized: improve strategy candidates within the remaining current five-hour Codex allowance. Initial usage snapshot: 19% used; primary reset epoch 1790849351. This is an account-wide model usage window, not a guaranteed five-hour wall-clock job. No live trading or AWS deployment. Original baseline remains reproducible. Real test CSV and test-access marker must remain absent.

## Fixed protocol before first candidate batch

- Use only January–June 2025 development BTC/ETH data for candidate exploration.
- Add the stated composite score: 0.4 Sortino + 0.3 Sharpe + 0.3 Calmar. Undefined/nonfinite ratios produce an undefined score; do not reward them.
- Separate full-period score from robustness. Examine full calendar months and 14-day windows, return, fees, drawdown and active days. Short-window annualization can distort Calmar; report components and do not rank solely by an exceptional window.
- First batch: original SMA baseline plus a small manual list of slower windows/thresholds and less frequent rebalancing. Fees/slippage/exposure limits stay fixed. Every candidate and result is retained.
- Chronological walk-forward parameter selection: select candidates from January–February and evaluate March, then select using past data only for April, May and June. Clearly distinguish retrospective candidate comparisons from these forward-selected results.
- At most three finalists will be evaluated on July–September validation, once each after development selection. Validation was already seen for the original baseline, so it is not a pristine holdout.
- Preserve October–December 2025 real test data without downloading/accessing it. Do not run final evaluation.
- Assess larger cost assumptions and nearby parameters on development. No metric-only acceptance if return, activity or execution quality is unacceptable.
- Only add a simple trained model if development diagnosis supplies a justified target and enough research allowance remains; training/standardization/labels must use preceding data only.
- Record hypotheses, unsuccessful experiments, full configuration and code/data fingerprints. Leave the original live config unchanged; candidates remain research configurations until reviewed.

## Stop conditions

The latest user amendment is to use half of the FULL five-hour allowance. This supersedes the prior half-remaining interpretation and72%ceiling. At amendment usage was46%; the new ceiling is50%total-used. Finish the already running batch07 and verification/handoff; do not launch further experiments. Account usage is shared and rounded. If this window resets, do not expand into a new window.

Stop when the ceiling/account limit prevents useful continuation or the user interrupts. Preserve completed and unsuccessful runs, verify reliability and the untouched test, and prepare a concrete handoff. A cohort checkpoint alone does not complete the goal.

## Second cohort and supervised challenger preregistration

Batch 02 introduces four breakout policies and four volatility-sized policies, keeping maximum allocation/fees/risk caps fixed. It runs under the same development protocol. Source snapshots are retained because strategy code evolves between batches.

A small supervised challenger will use one pooled BTC/ETH logistic classifier (seven price-derived features, no volume/news/external inputs), predicting whether a 24-hour next-open-to-next-open long trade is positive after modeled round-trip costs. Fit on preceding months only, purge the final label horizon and reserve one full day for model availability before the next month. Standardization is learned on training samples only. Fixed fitting settings, no neural networks/RL and no large hyperparameter search. Assess March–June development months with expanding earlier training; compare at most three preregistered probability policies. This is research only and does not change live defaults. Evaluate calibration/class balance and activity as well as portfolio score. Validation remains restricted to at most three total finalists across all strategy families.

## Fourth cohort

Six fixed pullback policies were registered before evaluating their results. Buy only below a short moving mean while both that mean and the current price exceed the long mean. Exit when the short mean is regained or the longer trend fails. Dip thresholds are 0.5%, 1% or 2%, with a single volatility-sized sensitivity check. Risk caps and execution costs remain constant. The same continuous, monthly, 14-day, double-cost and chronological past-month-selection protocol applies. The classifier calibration and 99%-halt counterfactual are diagnostics, not candidate tuning or risk approval.

## Next supervised challenger, fixed before its results

The binary classifier fails forward calibration in three of four months and does not estimate win/loss magnitude. Compare a linear ridge expected-return model using the same seven causal price features, pooled earlier BTC/ETH observations, 24-hour next-open execution label, label purge and one-day availability buffer. The target is the logarithm of exit/entry after modeled round-trip costs, clipped to [-0.15, 0.15] on training samples only. Standardization and intercept use preceding training data only. Solve ridge with fixed mean-square penalty 0.1 on standardized slopes; do not penalize the intercept. Do not sweep features, horizons or penalties. Compare three fixed policies: enter at expected net log return 0.002, at 0.005, or at 0.002 with 1% daily-volatility sizing; all exit when prediction is <=0. All retain existing exposure, execution and drawdown limits. Evaluate March–June forward months before considering validation. Compare forward squared-error predictions against the earlier-training target mean, and report a continuous forward portfolio where model updates become available chronologically if feasible. Do not claim monthly resets are that portfolio.

Before any positive future result, tighten rule-candidate development promotion screening to positive full and double-cost returns, at least four positive calendar months and six positive full 14-day windows, and median 14-day activity of at least eight days. This adds a competition-activity check; it does not instruct the bot to generate unnecessary trades. All existing candidates already fail on negative returns. These screens are provisional research requirements, not confirmed organizer scoring definitions.

## Relative-strength cohort, preregistered

Independent BTC/ETH signals and pooled models do not compare the assets with each other. Test six fixed relative-strength rotation variants: momentum/mean windows one-day/four-day, one-day/eight-day, two-day/eight-day and four-day/eight-day, with a 0.6% positive-momentum and relative-separation requirement; add 1%-daily-volatility sizing only to one-day/four-day and two-day/eight-day variants. The strongest eligible asset must exceed its longer mean and have positive momentum above the threshold. When two eligible assets are separated by less than the threshold, hold their existing allocations; invalid-trend assets receive zero targets. Otherwise allocate at most the existing per-pair cap to the strongest and zero to others. All input series must be chronological and aligned; no ranking on subsequent opens/closes. Preserve risk and execution limits, with existing sell-first and one-order-per-bar behavior. This is development exploration; do not retrospectively select BTC permanently because its full-period result is better. Use the standard rule-cohort protocol and promotion gates.

## Earlier training-history amendment

After the initial six cohorts, the initial two-month classifier/ridge fitting period and bearish early-2025 training exposure remain substantial limitations. Add a separate checksum-verified public BTCUSDT/ETHUSDT five-minute history for January–December 2024, ending before the original development start. This deliberately amends the initial "January–June data only" restriction for training history; preserve all original experiments rather than rewriting them. It does not move or consume the original July–September validation or October–December test periods.

Before seeing earlier-history-trained results, fix the next comparison to the same three logistic policies and the same three ridge policies, with unchanged seven features, fitting settings, costs, horizon, label purge and availability buffer. Train on expanding earlier history from 2024 and evaluate all six original January–June 2025 development months forward, with continuous holdings/risk and monthly artifact updates. Assess prediction quality against training-prior/mean constants, costs, drawdown and activity. This is a different training-history protocol, not an independent untouched holdout or a retroactively improved score for the original models. No new large search grid or neural model is authorized by this amendment. Continue the at-most-three-total-finalists validation limit and real-test exclusion.
