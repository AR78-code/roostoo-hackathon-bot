# AWS deployment

## Current installation — October 6, 2026

The user has deployed one Amazon Linux 2023 instance in Sydney and connects as
`ssm-user` through Session Manager. Python 3.11 is installed. The GitHub repository
is `https://github.com/AR78-code/roostoo-hackathon-bot`, cloned to
`/home/ssm-user/roostoo-hackathon-bot`. The enabled service is currently running
the original configuration in **paper** mode with `state/paper`. Authenticated
read-only preflight passed. This does not verify live order submission.

The generic `/opt` and `ubuntu` examples below do not match this installation.
Use the actual installed service paths when reviewing a deployment. Keep `.env`
private and preserve existing state. Never copy paper wallet, order records,
drawdown state or mode metadata into a live database.

The logistic candidates need 1,153 five-minute observations (about four days).
An empty live state cannot trade immediately with these configurations. Any
historical warm-up procedure must validate chronology, alignment, freshness and
price-source differences before it is used. A price-only warm-up utility is now implemented and tested; public-endpoint access and price agreement must still be checked on the actual server.
The original paper configuration retains only its 48-sample signal window.
Leaving that service running does not accumulate the 1,153 samples required by
the trained candidates. Deployment must explicitly address this retention and
warm-up limitation; paper wallet and order state must still stay isolated.

Inspect the installed service and logs with:

```bash
sudo systemctl cat trading-bot
sudo journalctl -u trading-bot -n 20 --no-pager
```

No improved strategy has been approved or activated in live mode.

Use the event AWS access portal and the official guide linked in `RESOURCES.md`. Use Sydney (`ap-southeast-2`), `Hackathon-Starter-Template`, the default template resources, and Session Manager. Do not manually create SSH keys or extra instances.

1. Confirm `python3 --version` is at least 3.11 on the instance.
2. Copy or clone the reviewed code to `/opt/roostoo-bot`. Commit the code and all strategy updates in your submission repository first. The current remote is the public Team116 repository listed above.
3. Set the service's `User` to the actual non-root login user (the template currently uses `ubuntu` as an example). Ensure that user owns `/opt/roostoo-bot/state`.
4. Create the `state` directory. Store environment variables in `/opt/roostoo-bot/.env` with permissions `600`, owned by the service user. The file format is `ROOSTOO_API_KEY=...` and `ROOSTOO_SECRET_KEY=...`, one per line. Never commit the file.
5. Run the offline tests and the read-only public preflight on the server. Run a paper cycle and inspect its database/logs.
6. Install `deploy/trading-bot.service` as `/etc/systemd/system/trading-bot.service`. Review paths and user, then run `sudo systemctl daemon-reload` and `sudo systemctl enable --now trading-bot` for paper mode.
7. Inspect `sudo systemctl status trading-bot`, `sudo journalctl -u trading-bot`, and `state/paper/bot.log`. Test recovery in paper mode before activating competition execution.
8. After credentials, rules, schedule and paper behavior are validated, change both `--mode` and `--state-dir` in ExecStart to `live` and `state/live`. Run an authenticated preflight. Activation and any restart during the competition must comply with organizer restrictions on manual intervention and updates; do not assume restarts are freely permitted.

The service restarts after failures and comes up after reboot. It does not clear ambiguous orders or drawdown halts. It starts in paper mode by default. Filesystem state must persist across deployments; never replace or wipe a live database. Synchronize the operating system clock and retain database backups along with the WAL file or use SQLite's backup API.

No deployment, account login, instance creation, or live trading has been performed by creating these files.


## Price-only warm-up for a reviewed five-minute configuration

Run `PYTHONPATH=src python3.11 -m trading_bot.warmup --config <reviewed-config> --mode live --state-dir state/live` only before starting the bot in an unused live state directory. The utility locks the database, fetches the exact trailing window of completed Binance Spot five-minute USDT closes, requires complete aligned timestamps, checks freshness and refuses last-close deviation greater than2%from the public Roostoo USD ticker. No paper wallet, orders, or drawdown state are imported. Existing samples, orders or portfolio high-water state cause refusal rather than replacement. Preflight-only state is allowed if the sampling configuration matches. No exchange order endpoint is called.

This removes the empty-history delay, not the need for a strategy signal. It cannot guarantee trades on eight days. Historical USDT closes and live Roostoo USD polling prices differ;2%agreement is a coarse rejection guard, not proof of equivalent feeds. History uses completed bar opening timestamps, matching the historical simulator; every close is available before seeding and before the first live execution. The history endpoint is documented in [Binance public market-data documentation](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md). Public history may be unavailable in a cloud region. If fetching or checks fail, do not bypass them.100tests pass using deterministic data; actual server fetch has not yet been verified.

The official event page states live trading October4–17 and allows strategy iteration/redeployment during this period. It requires eight active days with enough strategy trades each day; the exact per-day count and counting timezone are not specified there. Local daily fill counts are diagnostics, not an organizer eligibility certificate. Paper orders never count toward the competition account. Once current October2026prices are used for live deployment, that portion of the new2026test period is observed operationally and must not later be described as an untouched holdout. Original October–December2025test data remain reserved.

Read local activity without modifying the database: `python3.11 deploy/inspect_state.py state/live/bot.sqlite3` (use `state/paper/bot.sqlite3` for simulated diagnostics). It reports mode, sample coverage, unresolved orders and UTC days with filled orders. Counts use local order-intent timestamps; delayed reconciliation and organizer counting rules can differ.

Startup timing correction: warm-up now includes a known current public Roostoo ticker observation after the completed Binance closes, retaining the configured total sample count. It is not an unfinished future closing price. Use `--paper-check` with `--mode paper` to run one immediate simulated cycle under the same lock; this flag is rejected in live mode. This avoids a gap from waiting between seeding and checking. Any longer interruption still needs fresh history; do not wipe used live state.

For the verified Team116 installation, `bash deploy/activate_team116.sh` prepares the reviewed provisional policy for live competition execution. It requires the existing paper service and private600-permission credentials, repeats read-only preflight, and seeds unused live history before changing the service. Failed warm-up prevents stopping/installing the service; an already-live service is refused. It saves the prior service unit, keeps all state files, and starts the non-root Team116 live unit.102tests pass locally, including both activation gates. The policy remains negative in historical development; neither profit nor eight qualifying live days is guaranteed. Actual service activation must be verified from AWS status/logs.
