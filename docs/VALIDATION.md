# Validation record — October 1, 2026

- Offline unittest suite: 27 tests passed. Includes the published HMAC vector, transport retry boundaries, uncertain order persistence, order reconciliation, restart recovery, quote validation, sizing and cash limits, drawdown persistence, one-order-per-cycle behavior, and locking.
- Default offline CLI demo: 180 cycles completed; 45 simulated fills. Synthetic data is for exercising execution, not assessing returns.
- Roostoo public preflight: passed server time, exchange information and configured tickers.
- One public-data paper cycle: passed, both pairs in warm-up; no exchange orders or authentication requests.

Authenticated endpoints and live mock order fills remain unverified without team credentials. Sustained operation, EC2 deployment, historical strategy validation and organizer confirmation of conflicting dates remain outstanding. No live orders were submitted.

## Historical evaluation added

- Complete suite: 56 tests passed (27 original bot tests and 29 backtesting/reporting tests).
- Real five-minute BTCUSDT/ETHUSDT development and validation archives downloaded from Binance with all archive checksums verified. Timestamp grids are complete and aligned.
- Baseline research replay and CSV/JSON/Markdown/HTML reports completed. Development net return: -8.30%; validation net return: -6.18%, after modeled spread/slippage/fees and terminal liquidation.
- Equity and drawdown figures rendered with matplotlib and visually inspected.
- Source/code/data hashes are recorded in `reports/baseline/summary.json`.
- Actual held-out period October–December 2025 was not downloaded, loaded or evaluated. Synthetic fixtures exercise freezing/final evaluation in temporary directories only.
- Live bot logic and risk parameters were not modified by the backtesting implementation.
