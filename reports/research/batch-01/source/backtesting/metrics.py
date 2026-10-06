import math
import statistics


def daily_returns(curve):
    # UTC midnight equity observations only. Partial days are excluded from ratios.
    midnight = [row for row in curve if row['timestamp'] % 86400 == 0]
    return [b['equity']/a['equity']-1 for a,b in zip(midnight,midnight[1:]) if b['timestamp']-a['timestamp']==86400]


def composite_score(sortino, sharpe, calmar):
    values = (sortino, sharpe, calmar)
    if any(value is None or not math.isfinite(value) for value in values):
        return None
    return 0.4 * sortino + 0.3 * sharpe + 0.3 * calmar


def metrics(result):
    values = [r['equity'] for r in result.curve]
    initial, final = values[0], values[-1]
    high = initial
    drawdown = 0.0
    for value in values:
        high = max(high,value)
        drawdown = max(drawdown,1-value/high)
    duration = result.curve[-1]['timestamp']-result.curve[0]['timestamp']
    if duration <= 0:
        raise ValueError('Metric duration must be positive')
    exponent = math.log(final/initial)*365*86400/duration
    cagr = math.expm1(exponent) if exponent < 700 else None
    daily = daily_returns(result.curve)
    sharpe = sortino = None
    if len(daily) >= 2:
        mean = statistics.mean(daily)
        deviation = statistics.stdev(daily)
        downside = math.sqrt(sum(min(0,r)**2 for r in daily)/len(daily))
        if deviation > 1e-15:
            sharpe = mean/deviation*math.sqrt(365)
        if downside > 1e-15:
            sortino = mean/downside*math.sqrt(365)
    calmar = cagr / drawdown if cagr is not None and drawdown > 1e-15 else None
    score = composite_score(sortino, sharpe, calmar)
    return dict(composite_score=score,net_return=final/initial-1,final_equity=final,max_drawdown=drawdown,
        sharpe=sharpe,sortino=sortino,calmar=calmar,
        cagr=cagr,turnover=sum(t['notional'] for t in result.trades)/statistics.mean(values),
        fees=sum(t['fee'] for t in result.trades),trade_count=len(result.trades),
        strategy_trade_count=sum(t['reason']!='terminal_liquidation' for t in result.trades),
        mean_exposure=statistics.mean(r['exposure'] for r in result.curve[1:]),
        full_days_for_ratios=len(daily),buy_halt_timestamp=result.halt_timestamp)
