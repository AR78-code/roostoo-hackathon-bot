# Historical backtest report

Test access: **HELD OUT**

## Development: 2025-01-01 to 2025-07-01 (end exclusive, UTC)

| Portfolio | Composite | Net return | Max drawdown | Sharpe | Sortino | Calmar | Turnover | Fees ($) | Trades |
|---|---|---|---|---|---|---|---|---|---|
| extended_ml_entry055 | -0.221 | -1.40% | 10.35% | -0.163 | -0.226 | -0.271 | 7.879 | 779.249 | 391 |
| extended_ml_entry060 | 1.654 | 5.06% | 5.90% | 1.395 | 1.757 | 1.774 | 9.226 | 950.008 | 476 |
| extended_ml_entry055_vol01 | -1.420 | -1.70% | 3.04% | -1.341 | -1.706 | -1.117 | 2.447 | 242.542 | 123 |
| extended_ridge_entry002 | -0.584 | -2.61% | 9.82% | -0.567 | -0.640 | -0.528 | 27.387 | 2,694.482 | 1349 |
| extended_ridge_entry005 | 0.399 | 1.28% | 6.80% | 0.349 | 0.447 | 0.383 | 8.680 | 872.974 | 438 |
| extended_ridge_entry002_vol01 | -0.427 | -0.35% | 2.17% | -0.412 | -0.517 | -0.322 | 5.301 | 528.140 | 265 |
| cash | N/A | 0.00% | 0.00% | N/A | N/A | N/A | 0.000 | 0.000 | 0 |
| btc_buy_hold | 1.011 | 14.02% | 31.54% | 0.797 | 1.208 | 0.960 | 2.091 | 214.036 | 2 |
| allocation_matched | -0.188 | -2.37% | 19.12% | -0.131 | -0.186 | -0.246 | 0.817 | 77.633 | 4 |

Equity curves and trade journals: `development-*-equity.csv`, `development-*-trades.csv`.

## Assumptions and limitations

- Composite score is 0.4 Sortino + 0.3 Sharpe + 0.3 Calmar using the documented research definitions, without normalization. It is undefined if any component is undefined; this is not a verified reproduction of organizer calculations.
- Completed bar closes feed the configured strategy; signals execute at the next bar open. Sizing uses only that open and current holdings, never that bar's high/low/close.
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
