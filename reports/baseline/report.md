# Historical backtest report

Test access: **HELD OUT — not loaded or evaluated**

## Development: 2025-01-01 to 2025-07-01 (end exclusive, UTC)

| Portfolio | Net return | Max drawdown | Sharpe | Sortino | Calmar | Turnover | Fees ($) | Trades |
|---|---|---|---|---|---|---|---|---|
| strategy | -8.30% | 10.35% | -2.708 | -3.357 | -1.548 | 50.940 | 4,758.896 | 2382 |
| cash | 0.00% | 0.00% | N/A | N/A | N/A | 0.000 | 0.000 | 0 |
| btc_buy_hold | 14.02% | 31.54% | 0.797 | 1.208 | 0.960 | 2.091 | 214.036 | 2 |
| allocation_matched | -2.37% | 19.12% | -0.131 | -0.186 | -0.246 | 0.817 | 77.633 | 4 |

Equity curves and trade journals: `development-*-equity.csv`, `development-*-trades.csv`.

## Validation: 2025-07-01 to 2025-10-01 (end exclusive, UTC)

| Portfolio | Net return | Max drawdown | Sharpe | Sortino | Calmar | Turnover | Fees ($) | Trades |
|---|---|---|---|---|---|---|---|---|
| strategy | -6.18% | 10.25% | -2.456 | -3.612 | -2.180 | 62.348 | 6,203.756 | 3103 |
| cash | 0.00% | 0.00% | N/A | N/A | N/A | 0.000 | 0.000 | 0 |
| btc_buy_hold | 6.00% | 13.63% | 0.933 | 1.361 | 1.906 | 1.934 | 206.002 | 2 |
| allocation_matched | 14.41% | 8.54% | 2.394 | 3.876 | 8.272 | 0.837 | 94.429 | 4 |

Equity curves and trade journals: `validation-*-equity.csv`, `validation-*-trades.csv`.

## Assumptions and limitations

- Completed bar closes feed the existing SMA strategy; signals execute at the next bar open. Sizing uses only that open and current holdings, never that bar's high/low/close.
- Existing risk.plan handles sizing, free balance, reserve, spread, rounding, order caps and buy halts. At most one strategy order per bar; sells have priority as in the live engine.
- Each split starts with fresh cash and risk state. Validation/test may use only preceding historical closes for indicator warm-up, without trading before the split.
- Binance USDT prices are a proxy for Roostoo USD prices, assuming 1 USDT = 1 USD. Candle closes approximate the live bot's sampled ticker prices.
- Bid/ask are synthetic from a constant configured spread. Market orders fill at open plus spread and adverse configured slippage; fees apply to executed notional. No partial fills, depth, volume limits, network latency or API outages are modeled.
- All portfolios are liquidated at the last close minus spread/slippage with fees. These terminal accounting fills bypass per-order caps/precision and are separated from strategy-generated trades.
- Cash earns zero. BTC buy/hold invests 100% including its entry fee. Allocation-matched buy/hold uses the configured maximum BTC/ETH target weights initially, leaves the remainder in cash, and does not rebalance. Passive benchmarks bypass strategy limits and buy halts.
- Sharpe uses sample standard deviation of full UTC-day returns; Sortino uses root mean squared negative daily returns including zero downside on positive days. Both annualize with sqrt(365), zero risk-free rate and zero target return.
- Calmar is calendar-time CAGR divided by maximum recorded drawdown. Ratios with fewer than two full days, zero variance/downside, or zero drawdown are N/A rather than fabricated infinities. Annualization over short periods can be misleading.
- Maximum drawdown uses recorded bar-close equity and initial equity, including terminal costs. Intrabar losses may be larger. Buy-halt decisions check observed opens and closes, not intrabar highs/lows.
- Turnover is total absolute executed notional divided by mean recorded equity, including entry/exit costs and terminal sales; it is not half-turnover or annualized.
- Fixed chronological splits reduce leakage but do not establish statistical significance or profitability. Repeated validation selection can still overfit. Held-out data should be evaluated once after the strategy is frozen.

## Reproducibility

Configuration, source-code hashes and dataset hashes are recorded in `summary.json`.
