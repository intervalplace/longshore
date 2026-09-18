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
COOKING, FEEDING = "cooking", "feeding"

FIRE_REACH = 3           # how close you have to be for it to be your fire
COOK_SECONDS = 25.0
FED_SECONDS = 45.0       # how long a piece of driftwood keeps it up

# The gap people talk in. These were 14 to 48 seconds, carried over from
# catacomms where an action had to pay for its own airtime. Here a cast costs
# nothing at all, because position rides a heartbeat that was going out anyway,
# so the only argument for the wait is atmosphere, and half a minute of
# nothing is not atmosphere.
WAIT_MIN, WAIT_MAX = 7.0, 24.0
BITE_WINDOW = 2.6        # how long you have to strike
SHOW_CATCH = 4.0         # how long a landed fish stays on screen


# What a fish is worth towards your fishing. Weighted gently: a rare one
# should feel like a good evening rather than the only evening that counted,
# and somebody who fished all night and caught roach should not end up behind
# where they started.
WORTH = {"common": 1, "uncommon": 2, "scarce": 4, "rare": 8, "junk": 1}

# What cooking one is worth, and how long it takes.
#
# The first attempt was one point in five seconds, which was meant to be too
# small to matter and was in fact the best thing in the game: you can only
# cook a fish you have already caught, so it rides on top of a cast rather
# than instead of one, and at five seconds it returned 0.109 a second against
# fishing's 0.086. The optimal play was to fish the one spot nearest the fire
# and cook everything, which collapses a whole coast to a single tile.
#
# So it is slow. Twenty-five seconds for two comes to 0.083 a second, a
# fraction under fishing: never the efficient thing, never far off it either.
# The decision costs almost nothing in either direction, which is the point,
# because then it is made for reasons that are not numbers.
#
# And the twenty-five seconds is not a price, it is the thing itself. It is
# time stood at a fire with your hands busy, which is what a fire is for.
COOK_WORTH = 2

# Level n costs BASE * n ** CURVE. It never caps and never runs away: level
# five is an evening, ten is a month of weekly ones, twenty is about a year,
# and there is no last one. An exponential curve put level forty at fourteen
# thousand hours, which is not a level, it is a joke.
LEVEL_BASE = 15
LEVEL_CURVE = 1.6


def cost_of(level: int) -> int:
    """What the next level asks for."""
    return int(LEVEL_BASE * (max(1, level) ** LEVEL_CURVE))


def level_from(points: int) -> tuple:
    """(level, how far into it, what this one costs).

    Derived from the log rather than stored, so there is nothing to keep in
    step and nothing to corrupt.
    """
    level, spent = 1, 0
    while spent + cost_of(level) <= points:
        spent += cost_of(level)
        level += 1
    return level, points - spent, cost_of(level)


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
    """What you have ever caught, and what you have put on the fire.

    It only ever grows.

    No decay, no seasons expiring, nothing to lose by not turning up for a
    month. The number that goes up is how many kinds you have seen, and it is
    nobody's business but yours.
    """
    entries: dict = field(default_factory=dict)
    cooked: int = 0

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
    def points(self) -> int:
        """Everything you have ever pulled out, weighted by how hard it was.

        Recomputed from the log every time. There is no second number to keep
        in step, and nothing to lose if one of them is wrong.
        """
        from . import fish as F
        total = 0
        for name, entry in self.entries.items():
            kind = F.BY_NAME.get(name)
            total += WORTH.get(kind.rarity if kind else "common", 1) * entry.count
        return total + self.cooked * COOK_WORTH

    @property
    def level(self) -> int:
        return level_from(self.points)[0]

    @property
    def caught(self) -> int:
        return sum(e.count for e in self.entries.values())

    def best_of(self, species: str) -> int:
        seen = self.entries.get(species)
        return seen.best if seen else 0

    def to_dict(self) -> dict:
        return {"caught": {n: [e.count, e.best, e.first, e.last]
                           for n, e in sorted(self.entries.items())},
                "cooked": self.cooked}

    @classmethod
    def from_dict(cls, raw: dict) -> "Log":
        out = cls()
        # The first shape was the bare dictionary of catches. Anybody who
        # fished before this reads back rather than starting again.
        caught = (raw or {}).get("caught", raw or {})
        for name, row in caught.items():
            if not isinstance(row, (list, tuple)) or len(row) != 4:
                continue
            count, best, first, last = row
            out.entries[name] = Entry(name, int(count), int(best),
                                      float(first), float(last))
        out.cooked = int((raw or {}).get("cooked", 0) or 0)
        return out


@dataclass
class Angler:
    """Where you are and what you are doing about it.

    The log is the only part worth keeping. Where you happen to be standing is
    not, and a level measured in months that resets when you close the window
    is not a level at all: that was true here for longer than it should have
    been.
    """
    x: int
    y: int
    log: Log = field(default_factory=Log)
    state: str = IDLE
    until: float = 0.0          # when the current state runs out
    pending: tuple = (None, 0)  # what is on the hook, before you know it
    landed: tuple = (None, 0)   # what you last brought in
    casts: int = 0
    missed: int = 0
    wood: int = 0            # driftwood caught and not yet burned
    at_fire: tuple = (None, 0)   # what is on the fire, and how big

    # -- what you can do ---------------------------------------------------

    def move(self, world, dx: int, dy: int, now: float | None = None) -> bool:
        """Walking cancels a cast. You cannot drag a line up the beach."""
        nx, ny = self.x + dx, self.y + dy
        if not world.walkable(nx, ny, now):
            return False
        self.x, self.y = nx, ny
        if self.state in (WAITING, BITING):
            self.state, self.pending = IDLE, (None, 0)
        return True

    def wade_back(self, world, now: float) -> bool:
        """If the water came in around you, walk up onto the land.

        Being stood in the sea is not a punishment and losing a cast to the
        tide would be, so this only happens when the flat you are on has gone
        under, and it puts you on the nearest dry tile rather than anywhere
        dramatic.
        """
        if world.walkable(self.x, self.y, now):
            return False
        for radius in range(1, 6):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    x, y = self.x + dx, self.y + dy
                    if world.inside(x, y) and world.walkable(x, y, now) \
                       and world.on_foot(x, y):
                        self.x, self.y = x, y
                        if self.state in (WAITING, BITING):
                            self.state, self.pending = IDLE, (None, 0)
                        return True
        return False

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
        if species.name in ("driftwood",):
            # The one disappointment in the game turns out to be the fuel.
            self.wood += 1
        self.log.record(species.name, cm, now)
        self.state, self.until = DONE, now + SHOW_CATCH
        self.landed, self.pending = (species, cm), (None, 0)
        return (species, cm)

    def stop(self) -> None:
        self.state, self.pending = IDLE, (None, 0)

    # -- the fire ----------------------------------------------------------

    def by_the_fire(self, world) -> bool:
        from .world import firepit
        pit = firepit(world)
        return bool(pit and max(abs(self.x - pit[0]), abs(self.y - pit[1])) <= FIRE_REACH)

    def cook(self, world, now: float) -> bool:
        """Put your last catch on. Nothing is gained by it and nothing is
        lost: it is a reason to walk over to where the others are."""
        if not self.by_the_fire(world) or self.state in (WAITING, BITING):
            return False
        if self.landed[0] is None or self.landed[0].junk:
            return False
        self.state, self.until = COOKING, now + COOK_SECONDS
        self.at_fire = (self.landed[0].name, self.landed[1])
        self.log.cooked += 1
        self.landed = (None, 0)      # it is on the fire now, not in your hand
        return True

    def feed(self, world, now: float) -> bool:
        """A piece of driftwood on the fire. It burns higher for a while."""
        if not self.by_the_fire(world) or self.wood <= 0:
            return False
        if self.state in (WAITING, BITING):
            return False
        self.wood -= 1
        self.state, self.until = FEEDING, now + 2.0
        return True

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
        elif self.state == COOKING and now >= self.until:
            self.state = IDLE
            news.append(("cooked", self.at_fire[0]))
            self.at_fire = (None, 0)
        elif self.state == FEEDING and now >= self.until:
            self.state = IDLE
        return news

    # -- what other people are told ---------------------------------------

    def presence(self) -> str:
        """Small enough to ride on a heartbeat, which is why it is a string
        and not a structure. Position, what you are doing, and the last thing
        you caught, if it was recent enough to be worth mentioning."""
        doing = {IDLE: "-", WAITING: "c", BITING: "!", DONE: "+",
                 COOKING: "k", FEEDING: "f"}[self.state]
        got = ""
        if self.state == DONE and self.landed[0] is not None:
            got = f":{self.landed[0].name}:{self.landed[1]}"
        elif self.state == COOKING and self.at_fire[0]:
            # Cooking rides in the same slot a catch does, so telling the
            # shore what is on the fire costs nothing that was not already
            # being sent.
            got = f":{self.at_fire[0]}:{self.at_fire[1]}"
        return f"@{self.x}.{self.y}{doing}{got}"


def read_presence(text: str):
    """The other half: what to draw for somebody else. Returns a dict, or None
    if the string was not one of ours, because anybody can type anything into
    a personal message."""
    if not text.startswith("@"):
        return None
    body = text[1:]
    head, _, tail = body.partition(":")
    if not head or head[-1] not in "-c!+kf":
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


def load_log(path) -> Log:
    """Read a fishing log back, or start a new one."""
    import json
    from pathlib import Path
    where = Path(path)
    if not where.exists():
        return Log()
    try:
        return Log.from_dict(json.loads(where.read_text(encoding="utf-8")))
    except Exception:
        return Log()


def save_log(log: Log, path) -> None:
    """Written whole and moved into place, so a machine turned off mid-write
    comes back to the log it had rather than half of one."""
    import json
    import os
    from pathlib import Path
    where = Path(path)
    try:
        where.parent.mkdir(parents=True, exist_ok=True)
        temporary = where.with_suffix(".tmp")
        temporary.write_text(json.dumps(log.to_dict(), separators=(",", ":")),
                             encoding="utf-8")
        os.replace(temporary, where)
    except OSError:
        pass
