# Roostoo Hackathon Trading Bot

Python 3.11+ autonomous long-only baseline bot for the Roostoo mock exchange. Runtime uses the Python standard library; no third-party packages are required. macOS/Linux are supported (process locking uses `fcntl`).

## Run locally

From this project directory:

```sh
# Reliability tests, without network access or credentials
PYTHONPATH=src python3 -m unittest discover -s tests -v

# Complete offline paper simulation; use a fresh directory for each experiment
PYTHONPATH=src python3 -m trading_bot.main demo --state-dir state/demo-1

# Read-only public API connectivity check
PYTHONPATH=src python3 -m trading_bot.main preflight

# Paper trading against current Roostoo prices; no API credentials needed
PYTHONPATH=src python3 -m trading_bot.main run

# One paper cycle / status
PYTHONPATH=src python3 -m trading_bot.main run --once
PYTHONPATH=src python3 -m trading_bot.main status
```

`demo` is synthetic and verifies execution behavior; its results are not evidence of strategy performance. `run` defaults to paper mode and never sends orders to Roostoo. Stop a local paper run with Ctrl+C.

## Strategy and limits

The baseline samples prices every five minutes. After 48 consecutive samples (roughly four hours), it compares the last 12 prices with the last 48. An uptrend above a 0.3% threshold targets a 20% allocation per configured asset; a downtrend targets cash. The neutral band holds the existing position. Missing intervals require a fresh contiguous window. The live bot has no historical warm-start; the separate backtester supports earlier closes for indicator warm-up.

Defaults: BTC/USD and ETH/USD; 40% maximum total allocation; 20% cash reserve; $2,000 maximum order; $25 minimum order; 2% equity rebalance band; one market order per cycle. Paper fills use bid/ask plus 0.1% slippage and 0.1% taker commission. Live fills and actual fees are recorded from exchange responses. Parameters in `config/bot.toml` are initial engineering defaults, not optimized trading parameters.

A 10% portfolio drawdown latches a buy halt, while strategy-driven sells remain allowed. This is not an immediate liquidation rule. Spread and minimum-size checks also apply to sells, so the bot cannot guarantee immediate exits. No shorting, leverage, market-making, high-frequency trading, or arbitrage is implemented.

## Reliability behavior

- Sorted HMAC-SHA256 parameters; millisecond timestamps; exchange clock synchronization.
- Sliding-window limit of 25 API calls per minute, below the FAQ's 30-call limit. Run only one API-consuming process per account; the limiter does not coordinate separate computers or tools.
- Bounded read retries and exponential backoff after failed cycles. Order placement is never automatically retried after a transport error.
- SQLite WAL with full synchronous writes. An intent is committed before an order is sent. A restart during submission blocks new orders.
- Orders with an exchange ID are reconciled using the read-only order query. An unknown order without an ID remains blocked for investigation; there is deliberately no automatic clearing or discretionary trade command.
- One process per state directory. Use only one live state directory per account; filesystem locking cannot prevent bots on other hosts.
- Paper and live databases are isolated. State includes signals, orders, balances/equity observations, startup configuration, and errors. Rotating text logs are in the same state directory.
- Reject missing/crossed/nonfinite quotes, stale snapshots, unavailable pairs, and holdings that cannot be valued. Free and locked balances are handled separately.

## Live mock-exchange setup

Live mode is implemented but has not been verified with your team's credentials or a filled exchange order. Do not use real-money exchange credentials. Resolve competition dates and complete paper validation first. Do not paste secrets into chat or commit them to Git.

Export `ROOSTOO_API_KEY` and `ROOSTOO_SECRET_KEY` in your local shell. `.env.example` documents their names; `.env` is not automatically loaded by Python. The systemd service can read an EnvironmentFile.

```sh
# Read-only authentication and pair check; no orders
PYTHONPATH=src python3 -m trading_bot.main preflight --mode live

# Autonomous mock-exchange execution, once ready
PYTHONPATH=src python3 -m trading_bot.main run --mode live

PYTHONPATH=src python3 -m trading_bot.main status --mode live
```

Do not delete or recreate a live state database to bypass an unresolved order. Inspect the journal and exchange order history, then determine what happened before making any recovery change. Any competition recovery or code update must follow organizer rules and be recorded in repository history. A drawdown halt is persistent across restarts and has no automated reset.

`preflight` only checks connectivity, pair availability, and authentication; it does not certify execution, competition eligibility, fees, or profitable behavior. Account identity is not exposed by the documented balance response; never reuse a live database with a different team's API keys.

## AWS

See [deployment instructions](docs/DEPLOYMENT.md). The supplied service starts in paper mode. Use the organizers' preconfigured launch template and Session Manager in Sydney (`ap-southeast-2`); do not provision additional instances or change resources outside event permissions.

## Layout

- `src/trading_bot/client.py`: authenticated REST transport, clock, retries, rate limiting.
- `src/trading_bot/strategy.py`: replaceable baseline signal logic.
- `src/trading_bot/risk.py`: wallet valuation, sizing, precision, exposure limits.
- `src/trading_bot/engine.py`: data validation, signals, execution, reconciliation.
- `src/trading_bot/state.py`: durable journal, history, process lock.
- `src/trading_bot/main.py`: CLI, lifecycle and status.
- `src/trading_bot/backtesting/`: historical replay, daily metrics, reports and guarded test evaluation.
- `research/plot_report.py`: optional equity and drawdown plots.
- `reports/baseline/`: initial development/validation results.
- `tests/`: offline reliability and backtesting tests.
- `docs/`: source links, open rule questions and deployment guidance.
- `deploy/`: systemd service.

## Historical performance evaluation

See [backtesting instructions](docs/BACKTESTING.md) and [baseline report](reports/baseline/report.md). Development and validation data have been evaluated; the final test period remains untouched. Results include modeled fees and slippage, with cash, BTC buy-and-hold, and allocation-matched BTC/ETH comparisons. This first baseline lost money in both evaluated periods; it is not a validated profitable strategy.

## Remaining validation

Run paper trading for a sustained period, inspect logs and restarts, and evaluate the strategy on historical/out-of-sample data before choosing production parameters. Historical backtesting and benchmark reports are available; see [backtesting instructions](docs/BACKTESTING.md). Confirm the current event schedule, eligible assets, fees, active-day criteria, and any shorting rules with the organizers. The linked Luma and FAQ timelines disagree; see `docs/RESOURCES.md`. No AWS resources have been created and no exchange orders have been placed by this implementation session.
