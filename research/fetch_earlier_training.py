"""Fetch only supplemental history ending before the original development start."""
from pathlib import Path
import tomllib
from trading_bot.config import load
from trading_bot.backtesting.data import fetch_period,load_spec,utc_date


def main():
    supplement=tomllib.loads(Path('config/earlier-training.toml').read_text())
    original=load_spec('config/backtest.toml')
    bounds=supplement['training']
    if not utc_date(bounds['start'])<utc_date(bounds['end'])<=utc_date(original['development']['start']):
        raise ValueError('Supplemental history must end before original development')
    if supplement['interval_seconds']!=original['interval_seconds']:
        raise ValueError('Supplemental bar interval must match original development')
    path=fetch_period('data/earlier-training','training',supplement,load('config/bot.toml').pairs)
    print(f'Supplemental training history saved to {path}; original holdouts unchanged')


if __name__=='__main__':main()
