# AWS deployment

Use the event AWS access portal and the official guide linked in `RESOURCES.md`. Use Sydney (`ap-southeast-2`), `Hackathon-Starter-Template`, the default template resources, and Session Manager. Do not manually create SSH keys or extra instances.

1. Confirm `python3 --version` is at least 3.11 on the instance.
2. Copy or clone the reviewed code to `/opt/roostoo-bot`. Commit the code and all strategy updates in your submission repository first. A repository remote has not been configured by this build.
3. Set the service's `User` to the actual non-root login user (the template currently uses `ubuntu` as an example). Ensure that user owns `/opt/roostoo-bot/state`.
4. Create the `state` directory. Store environment variables in `/opt/roostoo-bot/.env` with permissions `600`, owned by the service user. The file format is `ROOSTOO_API_KEY=...` and `ROOSTOO_SECRET_KEY=...`, one per line. Never commit the file.
5. Run the offline tests and the read-only public preflight on the server. Run a paper cycle and inspect its database/logs.
6. Install `deploy/trading-bot.service` as `/etc/systemd/system/trading-bot.service`. Review paths and user, then run `sudo systemctl daemon-reload` and `sudo systemctl enable --now trading-bot` for paper mode.
7. Inspect `sudo systemctl status trading-bot`, `sudo journalctl -u trading-bot`, and `state/paper/bot.log`. Test recovery in paper mode before activating competition execution.
8. After credentials, rules, schedule and paper behavior are validated, change both `--mode` and `--state-dir` in ExecStart to `live` and `state/live`. Run an authenticated preflight. Activation and any restart during the competition must comply with organizer restrictions on manual intervention and updates; do not assume restarts are freely permitted.

The service restarts after failures and comes up after reboot. It does not clear ambiguous orders or drawdown halts. It starts in paper mode by default. Filesystem state must persist across deployments; never replace or wipe a live database. Synchronize the operating system clock and retain database backups along with the WAL file or use SQLite's backup API.

No deployment, account login, instance creation, or live trading has been performed by creating these files.
