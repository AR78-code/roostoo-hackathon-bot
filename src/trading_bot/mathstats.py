"""Small finite-float helpers for repeatedly evaluated price features."""
import math


def population_std(values):
    values=tuple(values)
    if not values or any(not math.isfinite(v) for v in values):
        raise ValueError('Population deviation requires finite observations')
    mean=math.fsum(values)/len(values)
    return math.sqrt(math.fsum((v-mean)**2 for v in values)/len(values))
