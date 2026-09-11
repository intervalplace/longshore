"""One person, standing somewhere, fishing.

Entirely local. Nothing in here is agreed with anybody, because nothing in here
affects anybody: my catch does not change your water. That is what lets the
whole game skip the machinery catacomms needed, and it is why longshore has no
engine, no lockstep and no state hashes.

Time is passed in rather than read, the same as everywhere else in these
projects, so a session can be replayed and tested without waiting for it.
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field

from . import fish as F
from .world import Rng, seed_of

IDLE, WAITING, BITING, DONE = "idle", "waiting", "biting", "done"

# The gap people talk in. These were 14 to 48 seconds, carried over from
# catacomms where an action had to pay for its own airtime. Here a cast costs
# nothing at all, because position rides a heartbeat that was going out anyway,
# so the only argument for the wait is atmosphere, and half a minute of
# nothing is not atmosphere.
WAIT_MIN, WAIT_MAX = 7.0, 24.0
BITE_WINDOW = 2.6        # how long you have to strike
SHOW_CATCH = 4.0         # how long a landed fish stays on screen


@dataclass
class Entry:
    """One species, as you have known it."""
    name: str
    count: int = 0
    best: int = 0
    first: float = 0.0
    last: float = 0.0


@dataclass
class Log:
    """What you have ever caught. It only ever grows.

    No decay, no seasons expiring, nothing to lose by not turning up for a
    month. The number that goes up is how many kinds you have seen, and it is
    nobody's business but yours.
    """
    entries: dict = field(default_factory=dict)

    def record(self, species: str, cm: int, now: float) -> bool:
        """Returns True if this is a kind you had never caught before."""
        seen = self.entries.get(species)
        if seen is None:
            self.entries[species] = Entry(species, 1, cm, now, now)
            return True
        seen.count += 1
        seen.last = now
        seen.best = max(seen.best, cm)
        return False

    @property
    def kinds(self) -> int:
        return len(self.entries)

    @property
    def caught(self) -> int:
        return sum(e.count for e in self.entries.values())

    def best_of(self, species: str) -> int:
        seen = self.entries.get(species)
        return seen.best if seen else 0

    def to_dict(self) -> dict:
        return {n: [e.count, e.best, e.first, e.last]
                for n, e in sorted(self.entries.items())}

    @classmethod
    def from_dict(cls, raw: dict) -> "Log":
        out = cls()
        for name, (count, best, first, last) in (raw or {}).items():
            out.entries[name] = Entry(name, int(count), int(best),
                                      float(first), float(last))
        return out


@dataclass
class Angler:
    """Where you are and what you are doing about it."""
    x: int
    y: int
    log: Log = field(default_factory=Log)
    state: str = IDLE
    until: float = 0.0          # when the current state runs out
    pending: tuple = (None, 0)  # what is on the hook, before you know it
    landed: tuple = (None, 0)   # what you last brought in
    casts: int = 0
    missed: int = 0

    # -- what you can do ---------------------------------------------------

    def move(self, world, dx: int, dy: int) -> bool:
        """Walking cancels a cast. You cannot drag a line up the beach."""
        nx, ny = self.x + dx, self.y + dy
        if not world.walkable(nx, ny):
            return False
        self.x, self.y = nx, ny
        if self.state in (WAITING, BITING):
            self.state, self.pending = IDLE, (None, 0)
        return True

    def cast(self, world, now: float, month: int, hour: int) -> bool:
        """Put a line in. Decides there and then what is on the end of it.

        The fish is chosen at the cast rather than at the strike so that a
        cast is one event with one outcome, and nothing about how fast you
        press a key changes what was in the water.
        """
        if self.state in (WAITING, BITING):
            return False
        if not world.fishable_from(self.x, self.y):
            return False
        self.casts += 1
        salt = f"{self.casts}:{int(now)}"
        species, cm = F.cast(world, self.x, self.y, month, hour, salt)
        if species is None:
            return False
        rng = Rng(seed_of(world.seed, self.x, self.y, salt, "wait"))
        wait = WAIT_MIN + (WAIT_MAX - WAIT_MIN) * rng.unit()
        self.state, self.until = WAITING, now + wait
        self.pending, self.landed = (species, cm), (None, 0)
        return True

    def strike(self, now: float) -> tuple:
        """Pull. Only does anything inside the window."""
        if self.state != BITING:
            if self.state == WAITING:
                # Striking early loses the fish, which is the only way to be
                # wrong at this game.
                self.state, self.pending = IDLE, (None, 0)
                self.missed += 1
            return (None, 0)
        species, cm = self.pending
        self.log.record(species.name, cm, now)
        self.state, self.until = DONE, now + SHOW_CATCH
        self.landed, self.pending = (species, cm), (None, 0)
        return (species, cm)

    def stop(self) -> None:
        self.state, self.pending = IDLE, (None, 0)

    # -- the clock ---------------------------------------------------------

    def tick(self, now: float) -> list:
        """Advance to `now`. Returns anything worth telling the player."""
        news = []
        if self.state == WAITING and now >= self.until:
            self.state, self.until = BITING, now + BITE_WINDOW
            news.append(("bite", None))
        elif self.state == BITING and now >= self.until:
            self.state, self.pending = IDLE, (None, 0)
            self.missed += 1
            news.append(("lost", None))
        elif self.state == DONE and now >= self.until:
            self.state = IDLE
        return news

    # -- what other people are told ---------------------------------------

    def presence(self) -> str:
        """Small enough to ride on a heartbeat, which is why it is a string
        and not a structure. Position, what you are doing, and the last thing
        you caught, if it was recent enough to be worth mentioning."""
        doing = {IDLE: "-", WAITING: "c", BITING: "!", DONE: "+"}[self.state]
        got = ""
        if self.state == DONE and self.landed[0] is not None:
            got = f":{self.landed[0].name}:{self.landed[1]}"
        return f"@{self.x}.{self.y}{doing}{got}"


def read_presence(text: str):
    """The other half: what to draw for somebody else. Returns a dict, or None
    if the string was not one of ours, because anybody can type anything into
    a personal message."""
    if not text.startswith("@"):
        return None
    body = text[1:]
    head, _, tail = body.partition(":")
    if not head or head[-1] not in "-c!+":
        return None
    doing, coords = head[-1], head[:-1]
    if "." not in coords:
        return None
    sx, _, sy = coords.partition(".")
    if not (sx.lstrip("-").isdigit() and sy.lstrip("-").isdigit()):
        return None
    out = {"x": int(sx), "y": int(sy), "doing": doing, "fish": "", "cm": 0}
    if tail:
        name, _, cm = tail.partition(":")
        out["fish"] = name
        out["cm"] = int(cm) if cm.isdigit() else 0
    return out
