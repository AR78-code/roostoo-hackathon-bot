# Development research: completed cohorts

Actual final test remains undownloaded and unevaluated. No new candidate validation runs have been made. Original live configuration is unchanged.

| Candidate | Scope | Net return | Median monthly score | Fees |
|---|---|---:|---:|---:|
| trend_3h_12h | Jan–Jun continuous | -4.83% | -0.218 | $1,805 |
| threshold_010 | Jan–Jun continuous | -8.58% | -0.609 | $1,716 |
| trend_6h_1d | Jan–Jun continuous | -6.82% | -2.733 | $1,018 |
| trend_12h_2d_band04 | Jan–Jun continuous | -6.57% | -2.740 | $618 |
| trend_12h_2d | Jan–Jun continuous | -7.77% | -2.955 | $757 |
| threshold_006 | Jan–Jun continuous | -8.06% | -3.313 | $3,215 |
| trend_2d_8d | Jan–Jun continuous | -7.56% | -3.708 | $277 |
| trend_1d_4d_band04 | Jan–Jun continuous | -8.06% | -4.010 | $472 |
| trend_2d_8d_010 | Jan–Jun continuous | -7.70% | -4.078 | $216 |
| trend_1d_4d_010 | Jan–Jun continuous | -10.74% | -4.080 | $507 |
| trend_1d_4d | Jan–Jun continuous | -8.45% | -4.134 | $572 |
| baseline | Jan–Jun continuous | -8.30% | -4.336 | $4,759 |
| trend_1d_4d_003 | Jan–Jun continuous | -8.48% | -4.621 | $532 |
| trend_12h_2d_vol01 | Jan–Jun continuous | -2.47% | -1.488 | $1,044 |
| breakout_2d | Jan–Jun continuous | -8.35% | -2.822 | $564 |
| trend_1d_4d_vol01 | Jan–Jun continuous | -3.07% | -3.184 | $848 |
| trend_1d_4d_vol02 | Jan–Jun continuous | -8.47% | -3.359 | $618 |
| breakout_1d | Jan–Jun continuous | -8.96% | -4.468 | $1,080 |
| breakout_1d_001 | Jan–Jun continuous | -8.74% | -4.524 | $1,068 |
| breakout_12h | Jan–Jun continuous | -8.78% | -4.590 | $2,165 |
| breakout_1d_vol01 | Jan–Jun continuous | -5.13% | -4.866 | $1,868 |
| pullback_1d_8d_020 | Jan–Jun continuous | -2.07% | -2.271 | $1,247 |
| pullback_12h_4d_020 | Jan–Jun continuous | -5.06% | -4.734 | $816 |
| pullback_12h_4d_010_vol01 | Jan–Jun continuous | -3.46% | -6.074 | $1,117 |
| pullback_12h_4d_010 | Jan–Jun continuous | -9.45% | -6.856 | $1,532 |
| pullback_6h_2d_010 | Jan–Jun continuous | -8.69% | -6.882 | $2,385 |
| pullback_6h_2d_005 | Jan–Jun continuous | -9.37% | -8.123 | $2,749 |
| rotation_4d_8d | Jan–Jun continuous | -7.53% | -6.118 | $2,171 |
| rotation_2d_8d | Jan–Jun continuous | -8.76% | -6.764 | $2,565 |
| rotation_2d_8d_vol01 | Jan–Jun continuous | -9.22% | -7.121 | $4,670 |
| rotation_1d_4d | Jan–Jun continuous | -9.75% | -7.362 | $2,420 |
| rotation_1d_8d | Jan–Jun continuous | -9.05% | -7.511 | $2,185 |
| rotation_1d_4d_vol01 | Jan–Jun continuous | -9.98% | -8.028 | $4,347 |
| ml_entry055 | Mar–Jun continuous forward | -1.66% | 0.028 | $1,131 |
| ml_entry060 | Mar–Jun continuous forward | -2.72% | 1.012 | $658 |
| ml_entry055_vol01 | Mar–Jun continuous forward | -0.09% | -0.123 | $232 |
| ridge_entry002 | Mar–Jun continuous forward | -5.60% | -4.323 | $1,779 |
| ridge_entry005 | Mar–Jun continuous forward | -2.57% | -2.458 | $1,030 |
| ridge_entry002_vol01 | Mar–Jun continuous forward | -1.29% | -3.382 | $387 |
| extended_ml_entry055 | Jan–Jun continuous forward; 2024+ earlier training | -1.40% | 0.514 | $779 |
| extended_ml_entry060 | Jan–Jun continuous forward; 2024+ earlier training | 5.06% | 6.367 | $950 |
| extended_ml_entry055_vol01 | Jan–Jun continuous forward; 2024+ earlier training | -1.70% | -3.179 | $243 |
| extended_ridge_entry002 | Jan–Jun continuous forward; 2024+ earlier training | -2.61% | -0.379 | $2,694 |
| extended_ridge_entry005 | Jan–Jun continuous forward; 2024+ earlier training | 1.28% | 1.053 | $873 |
| extended_ridge_entry002_vol01 | Jan–Jun continuous forward; 2024+ earlier training | -0.35% | -2.454 | $528 |

## Findings

- 0 completed candidates meet the preregistered development promotion screens. Positive development results alone do not establish a profitable live strategy.
- Slower SMA windows and wider signal thresholds reduce turnover/fees. They do not by themselves create positive development returns.
- Smaller volatility-aware allocations reduce drawdowns and losses but also reduce market exposure; do not confuse this with stronger predictive skill.
- The supervised classifier is fitted on earlier data only. Its March–June forward results have two positive and two negative months. All three probability policies lose money across the four independent monthly portfolios.
- One classifier policy scores 27.708 in May despite only about 0.072% return, two strategy orders and one active day. Tiny drawdown and short-period annualization can inflate Calmar; this is not an acceptable competition candidate simply because its raw score is high.
- Monthly resets/warm-up and the continuous full-period drawdown latch are different experiments. The reported monthly compounded classifier return is explicitly not a continuously managed portfolio track record.
- Rule cohorts include chronological parameter-selection records in walk_forward.json. Retrospective ranking alone is not claimed as forward performance.
- The classifier loses to an earlier-training constant probability on forward log loss and Brier score in three of four months. See research/AUDIT.md.
- The expected-return ridge challenger also loses to an earlier-training mean predictor on forward squared error in three of four months. All three continuous March–June policies lose money; no trained model is qualified for promotion.
- Removing the buy halt is not a demonstrated improvement: the baseline loss worsens to 21.72%, and the slower trend still loses money with 14.85% drawdown. Live risk limits remain unchanged.
- Execution cashflow decomposition of the original validation run: about $25 before commission, versus about $6,204 commissions. This holds recorded trades fixed and includes spread/slippage; it is not a no-cost counterfactual.

## Reproducibility

Every cohort retains registry.json, per-candidate configurations/results and archived source. Trained March–June coefficient/scaler artifacts are under config/models. The final test must remain untouched.
