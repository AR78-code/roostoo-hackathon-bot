# Deployment readiness — October 7, 2026

No candidate below has passed the combined profitability, cost-stress and activity screen. These are development results after repeated strategy selection, not independent proofs of future profitability. AWS activation has not been performed.

| Candidate | Period | Net return | Doubled-cost return | Median active days / 14 |
|---|---|---:|---:|---:|
| cash-exit-2025-entry0.6 | 2025 | 6.46% | 4.32% | 4.0 |
| cash-exit-2026-entry0.6 | 2026 | -1.23% | -1.32% | 0.0 |
| control-2025 | 2025 | -9.74% | -9.98% | 11.5 |
| expanded-2025 | 2025 | -9.50% | -9.70% | 14.0 |
| control-2026 | 2026 | -7.98% | -9.98% | 11.5 |
| expanded-2026 | 2026 | -9.18% | -10.06% | 12.0 |
| hysteresis-control-2025 | 2025 | -5.02% | -9.66% | 11.5 |
| hysteresis-expanded-2025 | 2025 | -9.09% | -9.51% | 13.5 |
| hysteresis-control-2026 | 2026 | -2.89% | -4.80% | 11.0 |
| hysteresis-expanded-2026 | 2026 | -4.71% | -8.57% | 12.0 |

| normalized-control-2025 | 2025 | -1.35% | -3.30% | 7.5 |
| normalized-expanded-2025 | 2025 | -2.76% | -8.27% | 11.5 |
| normalized-control-2026 | 2026 | -0.64% | -1.43% | 8.0 |
| normalized-expanded-2026 | 2026 | -2.70% | -4.74% | 9.5 |
| provisional-control-2025 | 2025 | -1.27% | -2.43% | 11.5 |
| provisional-control-2026 | 2026 | -0.72% | -1.22% | 11.0 |

Activity counts exclude terminal liquidation. A median over old 14-day windows does not guarantee eight days in the remaining live competition. The organizer requires enough strategy trades on each active day; public rules do not define an exact numeric daily threshold or counting timezone.

The trained candidate uses 1,153 observations (about four days); the latest rotation uses 2,304 (eight days). The new `trading_bot.warmup` command seeds completed public prices only into unused state, checks alignment/freshness and a 2% last-price agreement guard, and places no orders. AWS pulled commit32eda58, passed98tests, and seeded1,152 observations per pair successfully using the public endpoint and quote agreement checks. One-cycle strategy behavior and authenticated live readiness are being checked. It preserves separation from paper wallets, orders and risk state.

Current verification: 98 tests pass. Read-only activity diagnostics check filled-order days, mode, sample coverage and unresolved orders without changing the database. The original October–December 2025 test remains absent. No live configuration is claimed profitable or approved.

Confirmed AWS paper-history gap: both assets missed14:50UTC onOctober7. The old timer sleptfive minutes after each API cycle, accumulating duration and skipping a bucket. New scheduler anchors to server-adjusted five-minute boundaries. Existing gap state is retained; the separate seeded readiness state avoids inheriting that gap. Source fix is published; a running old process needs a controlled restart to load it. No competition orders have been placed by these checks. Once October2026prices have been used operationally for warm-up, that observed portion is no longer an untouched statistical test; no October2025test prices were accessed.
