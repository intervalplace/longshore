"""The tide.

Worked out from the clock, so every machine has the same water at the same
moment and nothing is ever sent about it. The firepit is derived from the
seed and the fire from who is standing near it; this is the third thing on
the coast that costs no radio time because nobody has to be told.

It changes what is interesting and never what is possible. A tide that shut
the fishing until eight would be a schedule, and a schedule is an obligation:
longshore has no stakes and nothing that decays, and something you have to
turn up for is both. So the water moves, the shallows come and go, and
whatever you could catch before you can still catch now, somewhere.

Twelve hours and twenty-five minutes is the real figure, near enough, and it
is worth the accuracy: a tide that drifted a little each day is one people
notice, and a tide on the hour is a clock with a coat on.
"""
from __future__ import annotations

import math

# A lunar day: two highs and two lows in 24h 50m.
PERIOD = 12 * 3600 + 25 * 60


def height(now: float) -> float:
    """Where the water is, from -1 at the lowest to 1 at the highest."""
    return math.sin(2 * math.pi * (now % PERIOD) / PERIOD)


def rising(now: float) -> bool:
    return math.cos(2 * math.pi * (now % PERIOD) / PERIOD) > 0


def state(now: float) -> str:
    """One of: low, coming in, high, going out.

    Four words rather than a number, because nobody on a shore says the tide
    is at zero point four.
    """
    h = height(now)
    if h < -0.55:
        return "low"
    if h > 0.55:
        return "high"
    return "coming in" if rising(now) else "going out"


def out(now: float) -> bool:
    """Low enough that the shallows are walkable and the ledges are out."""
    return height(now) < -0.35


def turns_until(now: float, want_low: bool = True) -> int:
    """Roughly how many minutes until the next low or high, for saying so."""
    step = 60.0
    for minutes in range(1, int(PERIOD / step) + 1):
        later = now + minutes * step
        if want_low and height(later) < -0.9:
            return minutes
        if not want_low and height(later) > 0.9:
            return minutes
    return 0
