# Hackathon resources

Access checked October 1, 2026. Links are references, not full archived copies. The Notion pages and Pitch viewer require browser access when the text web reader fails.

| Source | Link |
|---|---|
| Problem statement and event rules | https://luma.com/coghwiyt |
| Public API documentation | https://github.com/roostoo/Roostoo-API-Documents |
| FAQ | https://roostoo.notion.site/Roostoo-Quant-Trading-Hackathon-Official-FAQ-313ba22fed798042bab7c93c609d004e |
| Data sources | https://roostoo.notion.site/Data-Sources-Pack-318ba22fed7980118a69c7a614995930 |
| AWS guide | https://roostoo.notion.site/Hackathon-Guide-How-to-Sign-In-AWS-and-Launch-Your-Bot-309ba22fed798071b4dde6d1e8666816 |
| Info session, 30 slides | https://pitch.com/v/apac-quant-hackathon-info-session-zunvgj |

## Confirm before activation

Luma lists preparation October 1–3, live trading October 4–17, at least eight active trading days, and repository submission before October 14. The FAQ instead lists the main round starting September 30 and a first trade October 1 at 8pm (timezone not specified in that answer). Do not silently pick one schedule.

The public API README examples show historical illustrative fees and balances; they are not competition account parameters. Luma lists $100,000 starting portfolio, 0.1% market-order fees and 0.05% limit-order fees. The baseline uses those market fee and paper balance values, but reads live balances from the account.

FAQ: 30 calls per minute including queries and execution; Roostoo exposes ticker snapshots, not OHLCV. External market data is permitted. The baseline uses only sampled Roostoo ticker data and needs a warm-up window.

Rules require autonomous orders and traceable committed strategy changes. No discretionary API trades, high-frequency trading, market-making, or arbitrage. AWS deployment is required. This baseline implements long-only spot orders; the newer public repository includes short endpoints, which are intentionally excluded here pending further research and validation.

The slide deck has been checked for access, not reviewed in full. These notes do not replace a full rule review or organizer clarification.
