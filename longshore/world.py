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

    def walkable(self, x: int, y: int) -> bool:
        return self.at(x, y) in (SAND, GRASS)

    def inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def fishable_from(self, x: int, y: int) -> bool:
        """You fish from the land, into water you are standing beside.

        The water has to be on the map. Reading off the edge returns water, so
        without the bounds check every tile along the border claimed to be a
        fishing spot with nothing in front of it.
        """
        if not self.walkable(x, y):
            return False
        return any(self.inside(x + dx, y + dy)
                   and self.at(x + dx, y + dy) in (WATER, SHALLOW, REED)
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


def build(seed: str, width: int = 64, height: int = 36) -> World:
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
    return _ensure_ledges(world, number)


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


def render(world: World) -> str:
    return "\n".join("".join(GLYPH[t] for t in row) for row in world.tiles)
