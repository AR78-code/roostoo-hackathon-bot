"""Signals use completed closes; execution uses the subsequent open only."""
from dataclasses import dataclass, field, replace
from decimal import Decimal, ROUND_DOWN
from collections import deque
import math

from ..risk import Quote, equity, plan
from ..strategy import target_weight, rotation_targets


@dataclass
class Result:
    name: str
    curve: list = field(default_factory=list)
    trades: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    halt_timestamp: int | None = None
    fee_rate: float = 0.001


def quotes_at(frame, field_name, spread_bps):
    half = spread_bps / 20000
    return {p: Quote(getattr(b,field_name), getattr(b,field_name)*(1-half), getattr(b,field_name)*(1+half)) for p,b in frame.items()}


def fill(result, wallet, pair, side, qty, price, timestamp, signal_timestamp, reason):
    qty = float(qty)
    notional = qty * price
    fee = notional * result.fee_rate
    coin = pair.split('/')[0]
    if side == 'BUY':
        if notional + fee > wallet.get('USD',0) + 1e-7:
            raise ValueError('Simulated order exceeds available cash')
        wallet['USD'] -= notional + fee
        wallet[coin] = wallet.get(coin,0) + qty
    else:
        if qty > wallet.get(coin,0) + 1e-12:
            raise ValueError('Simulated order exceeds holdings')
        wallet['USD'] += notional - fee
        wallet[coin] = wallet.get(coin,0) - qty
    result.trades.append(dict(timestamp=timestamp, signal_timestamp=signal_timestamp,
        pair=pair, side=side, quantity=qty, price=price, notional=notional, fee=fee, reason=reason))


def liquidation(result, wallet, frame, cfg, spec):
    quotes = quotes_at(frame,'close',spec['spread_bps'])
    ts = next(iter(frame.values())).timestamp + cfg.interval_seconds
    # Common terminal valuation convention for all portfolios. Not bot-generated orders.
    for p in cfg.pairs:
        qty = wallet.get(p.split('/')[0],0)
        if qty:
            fill(result,wallet,p,'SELL',qty,quotes[p].bid*(1-cfg.slippage),ts,None,'terminal_liquidation')
    result.curve[-1]['equity'] = wallet['USD']
    result.curve[-1]['cash'] = wallet['USD']
    result.curve[-1]['exposure'] = 0.0


def validate_replay(frames, cfg, spec, warmup=None):
    if not frames or cfg.interval_seconds != spec['interval_seconds']:
        raise ValueError('Replay requires data and matching bar/polling intervals')
    prior = None
    for frame in list(warmup or []) + list(frames):
        if set(frame) != set(cfg.pairs):
            raise ValueError('Replay frame pairs differ from configuration')
        timestamps = {bar.timestamp for bar in frame.values()}
        if len(timestamps) != 1:
            raise ValueError('Replay frame has unaligned pairs')
        ts = timestamps.pop()
        if prior is not None and ts - prior != cfg.interval_seconds:
            raise ValueError('Replay and warm-up must be chronological and contiguous')
        for bar in frame.values():
            bar.validate()
        prior = ts


def simulate(frames, cfg, spec, warmup=None, model_schedule=None):
    validate_replay(frames,cfg,spec,warmup)
    # Research-only chronological artifact updates. Risk/execution configuration
    # must stay fixed so cash, holdings and the drawdown latch remain comparable.
    schedule=list(model_schedule or [])
    if schedule and cfg.strategy not in ('ridge','logistic','logistic_scaled','logistic_trend'):
        raise ValueError('Artifact schedules require a trained policy')
    if any(b[0]<=a[0] for a,b in zip(schedule,schedule[1:])):
        raise ValueError('Artifact update times must be strictly increasing')
    for timestamp,candidate in schedule:
        if not math.isfinite(timestamp):
            raise ValueError('Artifact update times must be finite')
        if replace(cfg,model_path=candidate.model_path)!=candidate:
            raise ValueError('Artifact schedule may change only model_path')

    def decision_config(known_at):
        current=cfg
        for effective_at,candidate in schedule:
            if effective_at>known_at:
                break
            current=candidate
        return current

    def decisions(histories,known_at):
        selected=decision_config(known_at)
        rows={pair:list(histories[pair]) for pair in cfg.pairs}
        if selected.strategy in ('rotation','rotation_hysteresis','rotation_normalized'):
            return rotation_targets(rows,selected)
        return [(pair,*target_weight(rows[pair],selected)) for pair in cfg.pairs]
    result = Result('strategy')
    result.fee_rate = cfg.fee_rate
    wallet = {'USD':cfg.paper_cash}
    history = {p:deque(maxlen=cfg.slow_window) for p in cfg.pairs}
    for frame in warmup or []:
        for p in cfg.pairs:
            bar = frame[p]
            history[p].append((bar.timestamp,bar.close))
    pending = None
    if warmup:
        signal_ts = next(iter(warmup[-1].values())).timestamp + cfg.interval_seconds - 1e-6
        pending = decisions(history,signal_ts)
    else:
        signal_ts = None
    high = cfg.paper_cash
    halted = False
    start = next(iter(frames[0].values())).timestamp
    result.curve.append(dict(timestamp=start,equity=cfg.paper_cash,cash=cfg.paper_cash,exposure=0.0))
    rules = {'AmountPrecision':spec['amount_precision'],'MiniOrder':spec['exchange_min_order']}
    for frame in frames:
        ts = next(iter(frame.values())).timestamp
        opening = quotes_at(frame,'open',spec['spread_bps'])
        total = equity(wallet,opening)
        high = max(high,total)
        if (high-total)/high >= cfg.max_drawdown and not halted:
            halted = True
            result.halt_timestamp = ts
        if pending:
            for pair,weight,reason in sorted(pending,key=lambda d:d[1] if d[1] is not None else 1):
                order = plan(pair,weight,wallet,dict(wallet),opening,rules,total,halted,cfg)
                if order:
                    side,qty,price = order
                    fill(result,wallet,pair,side,qty,price,ts,signal_ts,reason)
                    break
        closing = quotes_at(frame,'close',spec['spread_bps'])
        total = equity(wallet,closing)
        high = max(high,total)
        if (high-total)/high >= cfg.max_drawdown and not halted:
            halted = True
            result.halt_timestamp = ts + cfg.interval_seconds
        result.curve.append(dict(timestamp=ts+cfg.interval_seconds,equity=total,cash=wallet['USD'],exposure=1-wallet['USD']/total))
        for p in cfg.pairs:
            history[p].append((ts,frame[p].close))
        signal_ts = ts + cfg.interval_seconds - 1e-6
        pending = decisions(history,signal_ts)
        for p,weight,reason in pending:
            result.signals.append(dict(timestamp=signal_ts,pair=p,target=weight,reason=reason))
    liquidation(result,wallet,frames[-1],cfg,spec)
    return result


def benchmark(frames,cfg,spec,name,weights):
    validate_replay(frames,cfg,spec)
    if any(w < 0 for w in weights.values()) or sum(weights.values()) > 1:
        raise ValueError('Benchmark weights must be nonnegative and sum to at most one')
    result = Result(name)
    result.fee_rate = cfg.fee_rate
    wallet = {'USD':cfg.paper_cash}
    start = next(iter(frames[0].values())).timestamp
    result.curve.append(dict(timestamp=start,equity=cfg.paper_cash,cash=cfg.paper_cash,exposure=0.0))
    opening = quotes_at(frames[0],'open',spec['spread_bps'])
    for pair,weight in weights.items():
        price = opening[pair].ask*(1+cfg.slippage)
        # Target spending includes entry fee. Benchmark is buy/hold, not a bot risk-policy simulation.
        qty = Decimal(str(cfg.paper_cash*weight/(price*(1+cfg.fee_rate)))).quantize(Decimal(1).scaleb(-spec['amount_precision']),rounding=ROUND_DOWN)
        if qty > 0:
            fill(result,wallet,pair,'BUY',qty,price,start,None,'benchmark_entry')
    for frame in frames:
        ts = next(iter(frame.values())).timestamp + cfg.interval_seconds
        total = equity(wallet,quotes_at(frame,'close',spec['spread_bps']))
        result.curve.append(dict(timestamp=ts,equity=total,cash=wallet['USD'],exposure=1-wallet['USD']/total))
    liquidation(result,wallet,frames[-1],cfg,spec)
    return result


def run_all(frames,cfg,spec,warmup=None):
    if set(cfg.pairs) != {'BTC/USD','ETH/USD'}:
        raise ValueError('BTC/ETH benchmark suite requires exactly BTC/USD and ETH/USD')
    weight = min(cfg.max_pair_weight,cfg.max_total_weight/2)
    return [simulate(frames,cfg,spec,warmup),benchmark(frames,cfg,spec,'cash',{}),
        benchmark(frames,cfg,spec,'btc_buy_hold',{'BTC/USD':1}),
        benchmark(frames,cfg,spec,'allocation_matched',{'BTC/USD':weight,'ETH/USD':weight})]
