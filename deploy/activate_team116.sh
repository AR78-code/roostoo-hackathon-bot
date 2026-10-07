#!/usr/bin/env bash
# Provisional competition deployment, explicitly using the reviewed small-risk policy.
# This script never clears state or sends a manual order. The service trades autonomously.
set -euo pipefail

project_root=/home/ssm-user/roostoo-hackathon-bot
cd "$project_root"
if [[ "$(id -un)" != ssm-user ]]; then
    echo 'Run this from the existing ssm-user Session Manager terminal.' >&2
    exit 1
fi
if [[ ! -f .env || "$(stat -c %a .env)" != 600 ]]; then
    echo 'The private .env file must exist with permissions 600.' >&2
    exit 1
fi
existing_command=$(systemctl show trading-bot -p ExecStart --value)
if [[ "$existing_command" != *'--mode paper'* ]]; then
    echo 'Expected the existing paper service. Inspect the service before changing it.' >&2
    exit 1
fi

# Load the user's local credential file without printing its contents.
set -a
. ./.env
set +a
export PYTHONPATH="$project_root/src"
python3.11 -m trading_bot.main preflight --config config/provisional-live.toml --mode live --state-dir state/live-preflight-oct07
# Refuses existing samples, order journal, or prior portfolio activity.
# Completes before touching the running paper service; no competition orders here.
python3.11 -m trading_bot.warmup --config config/provisional-live.toml --mode live --state-dir state/live

unit_backup="/etc/systemd/system/trading-bot.service.before-live-$(date -u +%Y%m%dT%H%M%SZ)"
sudo cp -a /etc/systemd/system/trading-bot.service "$unit_backup"
sudo systemctl stop trading-bot
sudo install -m 644 deploy/trading-bot-team116.service /etc/systemd/system/trading-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now trading-bot
echo "Prior service unit saved at $unit_backup"
sudo systemctl status trading-bot --no-pager -l
sudo journalctl -u trading-bot -n 8 --no-pager -l
