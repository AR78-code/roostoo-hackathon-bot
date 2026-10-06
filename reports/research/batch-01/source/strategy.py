def target_weight(history, config):
    """Long-only SMA trend with a neutral band. None means hold current position."""
    if len(history) < config.slow_window:
        return None, "warming_up"
    recent = history[-config.slow_window:]
    # Missing polling intervals invalidate the window after a long outage.
    if any(b[0] - a[0] > config.interval_seconds * 1.5 for a, b in zip(recent, recent[1:])):
        return None, "history_gap"
    prices = [row[1] for row in recent]
    slow = sum(prices) / len(prices)
    fast = sum(prices[-config.fast_window:]) / config.fast_window
    strength = fast / slow - 1
    if strength > config.signal_threshold and prices[-1] > slow:
        return config.max_pair_weight, "uptrend"
    if strength < -config.signal_threshold:
        return 0.0, "downtrend"
    return None, "neutral"
