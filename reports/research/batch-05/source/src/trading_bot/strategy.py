"""Causal price-only policies; default SMA retains the original baseline behavior."""
import math
import statistics


def allocation(prices, config):
    if config.volatility_target <= 0:
        return config.max_pair_weight
    returns = [math.log(b / a) for a, b in zip(prices[-289:-1], prices[-288:])]
    periods_per_day = 86400 / config.interval_seconds
    daily_vol = statistics.pstdev(returns) * math.sqrt(periods_per_day)
    if daily_vol <= 1e-12:
        return config.max_pair_weight
    return config.max_pair_weight * min(1.0, config.volatility_target / daily_vol)


def target_weight(history, config):
    """Return a long-only target or None to retain the existing position."""
    if len(history) < config.slow_window:
        return None, "warming_up"
    recent = history[-config.slow_window:]
    if any(b[0] - a[0] > config.interval_seconds * 1.5 for a, b in zip(recent, recent[1:])):
        return None, "history_gap"
    prices = [row[1] for row in recent]
    if config.strategy == "ridge":
        from .ml import expected_return
        predicted = expected_return(recent, config)
        if predicted >= config.model_entry_return:
            return allocation(prices, config), "ridge_entry"
        if predicted <= config.model_exit_return:
            return 0.0, "ridge_exit"
        return None, "ridge_hold"
    if config.strategy == "logistic":
        from .ml import probability
        score = probability(recent, config)
        if score >= config.model_entry_probability:
            return allocation(prices, config), "model_entry"
        if score <= config.model_exit_probability:
            return 0.0, "model_exit"
        return None, "model_hold"
    if config.strategy == "breakout":
        prior_high = max(prices[-config.fast_window - 1:-1])
        exit_window = max(2, config.fast_window // 2)
        prior_low = min(prices[-exit_window - 1:-1])
        if prices[-1] > prior_high * (1 + config.signal_threshold):
            return allocation(prices, config), "breakout_entry"
        if prices[-1] < prior_low:
            return 0.0, "breakout_exit"
        return None, "breakout_hold"
    slow = sum(prices) / len(prices)
    fast = sum(prices[-config.fast_window:]) / config.fast_window
    if config.strategy == "pullback":
        # Buy a dip relative to the short mean only inside a positive long trend.
        # Exit at mean recovery or loss of the long trend; all observations are
        # completed closes. signal_threshold is the fractional dip requirement.
        if fast <= slow or prices[-1] <= slow:
            return 0.0, "pullback_trend_exit"
        if prices[-1] >= fast:
            return 0.0, "pullback_recovery_exit"
        if prices[-1] < fast * (1 - config.signal_threshold):
            return allocation(prices, config), "pullback_entry"
        return None, "pullback_hold"
    strength = fast / slow - 1
    if strength > config.signal_threshold and prices[-1] > slow:
        return allocation(prices, config), "uptrend"
    if strength < -config.signal_threshold:
        return 0.0, "downtrend"
    return None, "neutral"
