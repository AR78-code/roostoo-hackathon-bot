"""Small causal logistic-model inference. Fitting is separate, research-only code."""
from functools import lru_cache
import json
import math
from pathlib import Path
import statistics

LOOKBACK = 1153
FEATURE_NAMES = ('return_1h','return_6h','return_1d','return_3d','sma_12h_2d','daily_volatility','distance_4d_mean')


def features(prices, interval_seconds=300):
    if interval_seconds != 300 or len(prices) < LOOKBACK:
        raise ValueError('Price model requires 1153 five-minute samples')
    recent=prices[-LOOKBACK:]
    returns=[math.log(b/a) for a,b in zip(recent[-289:-1],recent[-288:])]
    vector=[math.log(recent[-1]/recent[-1-lag]) for lag in (12,72,288,864)]
    vector.extend([
        (sum(recent[-144:])/144)/(sum(recent[-576:])/576)-1,
        statistics.pstdev(returns)*math.sqrt(288),
        recent[-1]/(sum(recent[-1152:])/1152)-1,
    ])
    if any(not math.isfinite(v) for v in vector):
        raise ValueError('Nonfinite model features')
    return vector


def load_model(path):
    # Cache the exact artifact contents, so replacement at the same path cannot
    # silently retain old coefficients or an old availability timestamp.
    return _parse_model(Path(path).read_text())


@lru_cache(maxsize=32)
def _parse_model(contents):
    model=json.loads(contents)
    if model['feature_names']!=list(FEATURE_NAMES) or model['interval_seconds']!=300:
        raise ValueError('Unsupported model feature schema')
    for name in ('mean','scale','coefficients'):
        values=model[name]
        if len(values)!=len(FEATURE_NAMES) or any(not math.isfinite(v) for v in values):
            raise ValueError('Invalid model parameters')
    if any(v<=0 for v in model['scale']) or not math.isfinite(model['intercept']) or not math.isfinite(model['available_at']):
        raise ValueError('Invalid model scale/intercept/availability')
    return model


load_model.cache_clear = _parse_model.cache_clear


def probability(history, config):
    model=load_model(config.model_path)
    known_at=history[-1][0]+config.interval_seconds-1e-6
    if model['available_at']>known_at:
        raise ValueError('Model uses information unavailable at this historical decision')
    vector=features([row[1] for row in history],config.interval_seconds)
    value=model['intercept']+sum(c*(x-m)/s for c,x,m,s in zip(model['coefficients'],vector,model['mean'],model['scale']))
    # Stable sigmoid even for extreme feature values.
    return 1/(1+math.exp(-value)) if value>=0 else math.exp(value)/(1+math.exp(value))
