# Historical backtesting and performance reports

## Quick start

Python 3.11+; replay/reporting uses only the standard library. Run from the project directory:

```sh
# Download only development and validation. Archives are SHA256-verified.
PYTHONPATH=src python3 -m trading_bot.backtesting.cli fetch --period development
PYTHONPATH=src python3 -m trading_bot.backtesting.cli fetch --period validation

# Evaluate a configuration without opening the held-out period.
PYTHONPATH=src python3 -m trading_bot.backtesting.cli research

# Optional matplotlib curves (matplotlib is installed in this project's .venv).
.venv/bin/python research/plot_report.py reports/baseline

# Reliability and backtest tests
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Development/validation archives have already been downloaded and the initial report generated in `reports/baseline`. Reuse those CSVs; fetch refuses to overwrite an existing dataset. Historical data is ignored by Git. A fetch command downloads only its named period; research opens only `development.csv` and `validation.csv`.

Outputs:

- `report.html` and `report.md`: readable comparison and limitations.
- `summary.json`: all metrics, effective configuration, data hashes and code hashes.
- `metrics.csv`: all portfolios/periods, including exposure, CAGR and drawdown-halt timing.
- `*-equity.csv`: five-minute equity, cash and exposure.
- `*-trades.csv`: signal time, execution time, quantities, prices, fees and trade reasons.
- `*-signals.csv`: the strategy's target weights and decision reasons.
- `*-performance.png`: optional equity/drawdown plots.

## Fixed chronological periods

`config/backtest.toml` defines UTC dates with start inclusive and end exclusive:

| Period | Dates | Purpose |
|---|---|---|
| Development | 2025-01-01 to 2025-07-01 | Explore strategies and choose candidate parameters |
| Validation | 2025-07-01 to 2025-10-01 | Compare a limited set of candidates before selecting one |
| Held-out test | 2025-10-01 to 2026-01-01 | One final evaluation after selection |

Dates were fixed before the baseline results were viewed. No test market data has been downloaded, loaded or evaluated for the baseline. Synthetic unit tests exercise final evaluation in temporary directories; they do not access the real held-out dataset.

Each split starts from the same $100,000 cash balance with fresh drawdown state. Validation is warmed using the last `slow_window` development closes; test is warmed using prior validation closes. This historical warm-up is permitted information available before execution. Development starts cold. These independent split returns are not a continuous deployment track record.

## Freeze and final evaluation

After selecting a strategy based on development/validation, run:

```sh
# The report must match the current code, configuration and earlier data.
PYTHONPATH=src python3 -m trading_bot.backtesting.cli freeze \
  --research-report reports/baseline --selection reports/selection.json

# Explicitly consumes the held-out test. Uses the frozen config, not --config.
# Downloads test archives if absent, then evaluates only the test period.
PYTHONPATH=src python3 -m trading_bot.backtesting.cli final \
  --selection reports/selection.json --allow-test --output reports/final

.venv/bin/python research/plot_report.py reports/final
```

Do not run final evaluation while still choosing parameters. Selection files are created exclusively and never overwritten. They contain checksums of configuration, code and earlier data, plus the research report hash. `final` rejects changed code/data and records access in `data/historical/test-access.json` before loading/downloading test data. After a successful evaluation, additional final runs are rejected. A failed run can be retried only with the same frozen selection. This is a workflow safeguard, not a security boundary: copying/deleting files or reading archives manually can bypass it and invalidate the claim that the period was untouched. Once viewed, test results must not become another tuning signal; use a genuinely new future period for subsequent evaluation.

## Execution and reuse

`backtesting/simulator.py` calls the actual `strategy.target_weight` and `risk.plan`; it does not reimplement their rules. At the close of bar t it computes the signal from closes no later than t. At bar t+1 open it sizes against that observable price and current wallet, executes at most one strategy order, then records t+1 closing equity. It never uses t+1 high/low/close to decide or price the opening fill. The final signal has no future bar and is never executed.

Signals are timestamped one microsecond before the next open to represent the completed prior bar. This idealized next-open fill assumes zero processing latency at a bar boundary. A real bot may execute later. Unit tests perturb both the execution bar's close and future bars to verify earlier decisions do not change.

The same sizing routine handles cash reserve, maximum exposure, order caps, spread limits, quantity rounding and minimum notional. Free balance equals total balance in replay because market orders are filled immediately and no funds are locked. A buy halt latches when observed open/close drawdown crosses the configured threshold. It never resets inside a split; strategy exits remain allowed. Historical quotes use an assumed constant 2-basis-point full spread; quantity precision defaults to six decimals and exchange minimum to $1, rather than pretending we have historical Roostoo exchange rules.

Terminal liquidation is a common accounting convention for the strategy and all benchmarks. It includes adverse spread, slippage and fees, but bypasses per-order limits, volume capacity and rounding to sell the complete remaining balance. Its trade reason is `terminal_liquidation`; it is not an autonomous strategy decision. Reported `trade_count` includes those sales; `strategy_trade_count` excludes terminal sales (and includes initial entries for passive benchmarks).

## Benchmarks

- **Cash:** no trading, no interest, unchanged nominal balance.
- **BTC buy-and-hold:** spends the full initial cash, including its entry fee, on BTC at the first open; liquidates at the final close. This is a higher-exposure reference, not an equal-risk comparator.
- **Allocation-matched BTC/ETH buy-and-hold:** each asset's initial spending weight is `min(max_pair_weight, max_total_weight / 2)`. Defaults are 20% BTC + 20% ETH + 60% cash. Positions drift with prices and are not rebalanced. Matching refers to initial maximum strategy allocations, not actual realized or ongoing exposure. Mean exposure is reported so this distinction is visible.

Benchmarks share data periods, capital, fee/slippage/spread assumptions and terminal liquidation. They intentionally bypass the strategy's order cap, daily decisions and drawdown halts; otherwise they would not be passive buy-and-hold references.

## Metrics

Net return is final cash after terminal costs divided by initial cash minus one. Fees are the sum of commissions in quote currency, including terminal sales; spread and slippage are embedded in execution prices and are not mislabeled as fees.

Maximum drawdown is the largest peak-to-trough decline in recorded bar-close equity, including initial equity and terminal costs. Sharpe and Sortino use full UTC daily equity returns. Sharpe uses sample standard deviation; Sortino uses the root mean square of negative daily returns with positive-day downside set to zero. Risk-free rate and minimum acceptable return are both zero; annualization uses 365 cryptocurrency trading days.

Calmar is actual-calendar-time CAGR divided by maximum recorded drawdown. Turnover is sum of absolute executed quote notionals divided by mean recorded equity; includes buys, sells and terminal sales, and is not annualized or halved. Ratios return `null` in JSON / N/A in reports when variance/downside/drawdown is zero or fewer than two full days are available. Undefined values are never replaced with infinite scores.

The exact competition metric implementation has not been published/verified here. These clearly specified research definitions may differ from organizer leaderboard calculations.

## Data and limitations

Official data reference: https://github.com/binance/binance-public-data . BTCUSDT and ETHUSDT Spot monthly five-minute klines are fetched from https://data.binance.vision/ with companion archive checksums. Since January 2025, Spot archive timestamps use microseconds; the importer also supports older millisecond archives. Canonical CSV columns are:

```text
timestamp,pair,open,high,low,close,volume
```

Timestamps are integer Unix seconds for bar opening in UTC. Pairs must match configured BTC/USD and ETH/USD. `load_period` validates the whole expected timestamp grid, aligned pairs, duplicates, OHLC relationships and finite positive prices. Gaps are errors, not silently forward-filled. Out-of-period rows are rejected. Source sidecars record archive URLs/checksums and the canonical CSV checksum. Custom data can use the same separate period CSVs; document its provenance before comparing runs.

Binance USDT is only a proxy for Roostoo USD. No depeg correction, historical bid/ask, order book, market impact, fill capacity, partial fills, network outages, API contention, tax or financing is modeled. Candle-close samples are a proxy for live ticker samples. Intrabar equity drawdowns and actual execution delays may be worse than reported. Terminal assumptions and annualization can strongly affect short-period comparisons. Benchmarks are educational references, not recommended investments.

## Improving the baseline

Create a separate candidate TOML and write each report to a different directory:

```sh
PYTHONPATH=src python3 -m trading_bot.backtesting.cli research \
  --config config/candidate.toml --output reports/candidate
```

Choose candidates from development findings, compare a small number on validation under identical costs, and preserve all experiments rather than reporting only the winner. Do not inspect test data until selection is frozen. Report the strategy's actual exposure and costs, not only return. No automatic tuning or strategy changes are made by the reporting system.
