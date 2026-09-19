"""The world, derived rather than stored.

Nothing about the map is ever transmitted. Everybody computes it from the same
seed and gets the same coastline, the same rocks, the same reeds. That is the
trick the whole project runs on: generation is free, transmission is not.

There is no engine here and no state machine. A world is a fact, not a
simulation: given a seed you get terrain, and given a place and a moment you
get what is biting. Nothing in this file changes, ever.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from . import tide

WATER, SHALLOW, SAND, GRASS, ROCK, REED, TREE = range(7)
GLYPH = {WATER: "~", SHALLOW: "-", SAND: ".", GRASS: ",",
         ROCK: "o", REED: "|", TREE: "T"}


class Rng:
    """SplitMix64. Deterministic, tiny, and identical on every machine.

    The standard library's random would do, but its stream is a promise nobody
    made, and two people on two Pythons getting two coastlines would be a poor
    way to find that out.
    """

    __slots__ = ("state",)
    MASK = (1 << 64) - 1

    def __init__(self, seed: int) -> None:
        self.state = seed & self.MASK

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & self.MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & self.MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & self.MASK
        return z ^ (z >> 31)

    def below(self, n: int) -> int:
        return self.next() % n if n > 0 else 0

    def unit(self) -> float:
        return self.next() / (1 << 64)


def seed_of(*parts) -> int:
    """A 64-bit seed from anything. Stable across machines and versions."""
    text = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(text, digest_size=8).digest(), "big")


# --------------------------------------------------------------------------
# Terrain
# --------------------------------------------------------------------------

def _noise(seed: int, x: int, y: int) -> float:
    """Value noise at a point. Smooth enough for a coastline, cheap enough to
    call for every tile without anybody noticing."""
    return Rng(seed_of(seed, x, y)).unit()


def _smooth(seed: int, x: float, y: float, scale: float) -> float:
    """Bilinear interpolation between noise samples on a grid of `scale`."""
    gx, gy = x / scale, y / scale
    x0, y0 = int(gx // 1), int(gy // 1)
    fx, fy = gx - x0, gy - y0
    # smoothstep, so the coast curves rather than creasing
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = _noise(seed, x0, y0)
    b = _noise(seed, x0 + 1, y0)
    c = _noise(seed, x0, y0 + 1)
    d = _noise(seed, x0 + 1, y0 + 1)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


@dataclass(frozen=True)
class World:
    seed: str
    width: int
    height: int
    tiles: tuple          # row strings of tile ints

    def at(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return WATER

    def on_foot(self, x: int, y: int, now: float | None = None) -> bool:
        """Ground you could stand on, ignoring what is on it.

        At low water the shallows are ground too. The tide only ever adds
        places to stand: what you could reach at high water you can still
        reach at low, so nothing is ever shut and nobody has to turn up at an
        hour somebody else chose.
        """
        tile = self.at(x, y)
        if tile in (SAND, GRASS):
            return True
        return tile == SHALLOW and now is not None and tide.out(now)

    def walkable(self, x: int, y: int, now: float | None = None) -> bool:
        if not self.on_foot(x, y, now):
            return False
        # You cannot stand in a fire. Without this people walked into the
        # middle of it and the flame was drawn behind them.
        return (x, y) != firepit(self)

    def inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def fishable_from(self, x: int, y: int, now: float | None = None) -> bool:
        """You fish from the land, into water you are standing beside.

        The water has to be on the map. Reading off the edge returns water, so
        without the bounds check every tile along the border claimed to be a
        fishing spot with nothing in front of it.
        """
        if not self.walkable(x, y, now):
            return False
        # At low water the flats are mud, not water, for everybody. This used
        # to exempt only the tile you were standing on, so anyone on the beach
        # beside an exposed flat was casting into dry sand.
        out = now is not None and tide.out(now)
        wet = (WATER, REED) if out else (WATER, SHALLOW, REED)
        return any(self.inside(x + dx, y + dy)
                   and self.at(x + dx, y + dy) in wet
                   for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)))


def _fbm(seed: int, x: float, y: float, scale: float, octaves: int = 4) -> float:
    """Layered noise. One octave gives blobs; four gives a coastline with
    headlands and inlets at every size, which is what a coast looks like."""
    total, amplitude, weight = 0.0, 1.0, 0.0
    for n in range(octaves):
        total += _smooth(seed + n * 101, x, y, scale / (2 ** n)) * amplitude
        weight += amplitude
        amplitude *= 0.5
    return total / weight


# A coast for four people. Sixty-four by thirty-six was the first guess and it
# was too much room: at a size where the tiles are big enough to see somebody
# on, four figures disappeared into two and a half thousand tiles of scenery.
# Forty by twenty-four keeps every water and every fish, gives about twenty
# places to sit, and fits a screen at eighteen pixels a tile.
COAST_WIDTH, COAST_HEIGHT = 40, 24


def build(seed: str, width: int = COAST_WIDTH, height: int = COAST_HEIGHT) -> World:
    """A coast with the sea to the west, made from a height field.

    Varying a single edge per row gives a wobbly vertical line. A field gives
    bays, headlands, spits and the occasional island, because those are what
    happens when a surface meets a level rather than what a rule produces.
    """
    number = seed_of(seed)

    # Height first, then thresholds chosen so every seed gets a real coast.
    # Fixed cut-offs gave one world 4% water and the next 28%, because the
    # noise does not care what proportion you were hoping for.
    field = [[_fbm(number, x, y, 26.0) - 0.5 + (x / width - 0.30) * 1.45
              for x in range(width)] for y in range(height)]
    ordered = sorted(v for row in field for v in row)
    def cut(fraction):
        return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]
    deep, shallow, beach = cut(0.34), cut(0.42), cut(0.50)

    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            land = field[y][x]
            if land < deep:
                tile = WATER
            elif land < shallow:
                tile = SHALLOW
            elif land < beach:
                tile = SAND
            else:
                tile = GRASS
            # Averaging octaves pulls noise towards the middle, so a
            # threshold of 0.74 on two octaves produced no rock at all in ten
            # seeds. These are set against what the field actually does.
            grain = _fbm(number + 977, x, y, 7.0, 2)
            if tile == SHALLOW and grain > 0.58:
                tile = REED          # reeds are where the odd things live
            elif tile == WATER and land > deep - 0.05 and grain > 0.585:
                tile = ROCK          # standing out of the water
            elif tile == SAND and grain > 0.74:
                # Rock does not walk on, so rock on the beach is a wall along
                # the waterline. At 0.60 it took more than half the shore and
                # left barely thirty places to stand on a whole coast.
                tile = ROCK
            elif tile == GRASS and grain > 0.60:
                tile = TREE
            row.append(tile)
        rows.append(tuple(row))

    world = World(seed=seed, width=width, height=height, tiles=tuple(rows))
    world = _ensure_ledges(world, number)
    return _ensure_reeds(world, number)


def _ensure_ledges(world: "World", number: int, want: int = 3) -> "World":
    """Every coast gets at least a few rocks standing in the water.

    Seven coasts in twenty came out with none, and a coast without a ledge
    cannot reach the open-sea fish at all: it offered twenty-four species of
    forty-two. A rock is also the one landmark worth walking to, so a shore
    with none is a shore where every spot is the same spot.
    """
    # Count places somebody could stand and fish a ledge from, not rocks in
    # general: rocks out on an island you cannot walk to are scenery.
    reachable = sum(1 for y in range(world.height) for x in range(world.width)
                    if world.fishable_from(x, y)
                    and any(world.at(x + dx, y + dy) == ROCK
                            for dx in (-1, 0, 1) for dy in (-1, 0, 1)))
    if reachable >= want:
        return world

    # Somewhere a person could stand, with water in front to drop a rock into.
    candidates = []
    for y in range(1, world.height - 1):
        for x in range(1, world.width - 1):
            if not world.fishable_from(x, y):
                continue
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                if world.at(x + dx, y + dy) in (WATER, SHALLOW):
                    candidates.append((x + dx, y + dy))
                    break
    if not candidates:
        return world

    rng = Rng(seed_of(number, "ledges"))
    rows = [list(row) for row in world.tiles]
    placed, tries = 0, 0
    while placed < want - reachable and tries < 200 and candidates:
        tries += 1
        spot = candidates[rng.below(len(candidates))]
        if rows[spot[1]][spot[0]] == ROCK:
            continue
        rows[spot[1]][spot[0]] = ROCK
        placed += 1
    return World(seed=world.seed, width=world.width, height=world.height,
                 tiles=tuple(tuple(r) for r in rows))


_PITS: dict = {}


def firepit(world: World):
    """Where the fire is. Derived, like everything else.

    Nobody places it and nobody has to be told: the same seed gives the same
    spot on every machine, so whether it is lit can be worked out from where
    people are standing, and no part of the fire ever crosses the radio.

    It wants to be near the water and out of the way of the best fishing, so
    it goes on land with a view of the sea and a bit of shelter behind it.
    """
    if world.seed in _PITS:
        return _PITS[world.seed]
    # Decided from tiles alone. Scoring it on `fishable_from` read better and
    # recursed for ever: walkable asks where the fire is, and the fire asked
    # what was walkable.
    wet = (WATER, SHALLOW, REED)

    def would_fish(x, y):
        return world.on_foot(x, y) and any(
            world.inside(x + dx, y + dy) and world.at(x + dx, y + dy) in wet
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)))

    best, choice = None, None
    for y in range(1, world.height - 1):
        for x in range(1, world.width - 1):
            if not world.on_foot(x, y):
                continue
            # What matters is how much fishing is within a short walk. Scoring
            # it on shelter put the fire in a sandy corner with no water near
            # it on two coasts in four, and a fire nobody passes is not a
            # gathering place, it is scenery.
            near = sum(1 for dx in range(-4, 5) for dy in range(-4, 5)
                       if would_fish(x + dx, y + dy))
            room = sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                       if world.on_foot(x + dx, y + dy))
            if room < 7 or near < 3:
                continue          # nowhere to stand, or nobody ever comes by
            sea = sum(1 for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)
                      if world.inside(x + dx, y + dy)
                      and world.at(x + dx, y + dy) in wet)
            score = (near, room, sea, -x, -y)
            if best is None or score > best:
                best, choice = score, (x, y)
    # Scanning the map for it on every step would be silly; a world is frozen
    # and its fire never moves.
    _PITS[world.seed] = choice
    return choice


def render(world: World) -> str:
    return "\n".join("".join(GLYPH[t] for t in row) for row in world.tiles)


def _ensure_reeds(world: "World", number: int, want: int = 3) -> "World":
    """Every coast gets a reed bed somebody can fish from.

    Ledges were guaranteed and reeds were not, which cost nothing on a large
    coast and everything on a small one: shrink the map and the reeds stop
    appearing, and with them the ten species that live in them. A coast that
    can only offer thirty-two of forty-two fish is a coast missing a quarter
    of the game.
    """
    reachable = sum(1 for y in range(world.height) for x in range(world.width)
                    if world.fishable_from(x, y)
                    and any(world.at(x + dx, y + dy) == REED
                            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))))
    if reachable >= want:
        return world

    # Shallow water next to somewhere a person could stand. Reeds grow in the
    # thin water at the edge, which is where they grow anyway.
    candidates = []
    for y in range(1, world.height - 1):
        for x in range(1, world.width - 1):
            if not world.fishable_from(x, y):
                continue
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                if world.at(x + dx, y + dy) == SHALLOW:
                    candidates.append((x + dx, y + dy))
    if not candidates:
        # No shallows at all: turn the odd bit of deep water at the edge.
        for y in range(1, world.height - 1):
            for x in range(1, world.width - 1):
                if world.fishable_from(x, y):
                    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                        if world.at(x + dx, y + dy) == WATER:
                            candidates.append((x + dx, y + dy))
    if not candidates:
        return world

    rng = Rng(seed_of(number, "reeds"))
    rows = [list(row) for row in world.tiles]
    placed, tries = 0, 0
    while placed < want - reachable and tries < 300 and candidates:
        tries += 1
        spot = candidates[rng.below(len(candidates))]
        if rows[spot[1]][spot[0]] == REED:
            continue
        rows[spot[1]][spot[0]] = REED
        placed += 1
    return World(seed=world.seed, width=world.width, height=world.height,
                 tiles=tuple(tuple(r) for r in rows))
