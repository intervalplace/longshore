"""What is biting, and where, and when.

Same principle as the world: nothing here is transmitted. Two people on
opposite sides of a bay compute the same fish from the same day, hour and
patch of water, because all three are things both machines already know.

A catch is not simulated. It is a lookup with a die roll: the water you are
beside decides the pool, the day and hour weight it, and rarity does the rest.
There is no economy, no hunger, no stock to deplete. Fishing a spot for an hour
does not make it worse, because a spot that runs dry is a spot you have to
defend, and this is not that kind of game.
"""

from __future__ import annotations

from dataclasses import dataclass

from .world import REED, ROCK, SHALLOW, WATER, Rng, seed_of

# Where a species will take a hook. A spot's water decides which pool you draw
# from, so a reed bed and a rock ledge are different places to sit rather than
# different scenery.
OPEN, SHALLOWS, REEDS, LEDGE = "open", "shallows", "reeds", "ledge"

DAWN, DAY, DUSK, NIGHT = "dawn", "day", "dusk", "night"


@dataclass(frozen=True)
class Species:
    name: str
    water: tuple          # which pools it belongs to
    weight: int           # how often it comes up, against its pool
    hours: tuple = ()     # empty means any time
    months: tuple = ()    # empty means all year
    size: tuple = (20, 60)   # centimetres, small and large
    junk: bool = False       # a boot is not a scarce fish

    @property
    def rarity(self) -> str:
        if self.junk:
            return "junk"
        if self.weight >= 40:
            return "common"
        if self.weight >= 14:
            return "uncommon"
        if self.weight >= 4:
            return "scarce"
        return "rare"


# Forty-odd species. The common ones are there so there is always something
# happening; the rare ones are there so there is always something to say.
FISH = (
    # -- open water ------------------------------------------------------
    Species("herring",      (OPEN,),            60, size=(18, 32)),
    Species("mackerel",     (OPEN,),            50, (DAWN, DAY), size=(25, 45)),
    Species("whiting",      (OPEN,),            38, size=(20, 40)),
    Species("pollack",      (OPEN, LEDGE),      30, size=(30, 70)),
    Species("cod",          (OPEN,),            22, months=(10, 11, 12, 1, 2), size=(40, 95)),
    Species("garfish",      (OPEN,),            16, (DAY,), months=(5, 6, 7, 8), size=(45, 80)),
    Species("sea trout",    (OPEN, SHALLOWS),   12, (DAWN, DUSK), size=(35, 70)),
    Species("turbot",       (OPEN,),             7, size=(30, 60)),
    Species("halibut",      (OPEN,),             3, size=(70, 190)),
    Species("moonfish",     (OPEN,),             1, (NIGHT,), size=(60, 140)),

    # -- the shallows ----------------------------------------------------
    Species("sand goby",    (SHALLOWS,),        70, size=(6, 11)),
    Species("dab",          (SHALLOWS,),        48, size=(15, 30)),
    Species("flounder",     (SHALLOWS,),        40, size=(20, 45)),
    Species("shore crab",   (SHALLOWS, LEDGE),  36, size=(4, 9)),
    Species("plaice",       (SHALLOWS,),        26, size=(25, 50)),
    Species("sand eel",     (SHALLOWS,),        24, (DAWN,), size=(10, 20)),
    Species("bass",         (SHALLOWS, LEDGE),  14, (DUSK, NIGHT), size=(35, 80)),
    Species("sole",         (SHALLOWS,),         9, (NIGHT,), size=(22, 45)),
    Species("brill",        (SHALLOWS,),         5, size=(28, 55)),
    Species("glass eel",    (SHALLOWS,),         2, (NIGHT,), months=(3, 4, 5), size=(6, 10)),

    # -- reed beds -------------------------------------------------------
    Species("roach",        (REEDS,),           66, size=(12, 30)),
    Species("rudd",         (REEDS,),           44, (DAY,), size=(14, 32)),
    Species("perch",        (REEDS,),           34, size=(15, 40)),
    Species("tench",        (REEDS,),           20, (DAWN, DUSK), size=(25, 55)),
    Species("bream",        (REEDS,),           18, size=(25, 60)),
    Species("pike",         (REEDS,),           11, size=(45, 110)),
    Species("eel",          (REEDS,),            8, (NIGHT,), size=(35, 90)),
    Species("crucian",      (REEDS,),            6, size=(15, 35)),
    Species("golden rudd",  (REEDS,),            2, (DAWN,), size=(18, 36)),
    Species("wels",         (REEDS,),            1, (NIGHT,), months=(6, 7, 8), size=(90, 240)),

    # -- rock ledges -----------------------------------------------------
    Species("blenny",       (LEDGE,),           62, size=(6, 14)),
    Species("wrasse",       (LEDGE,),           46, (DAY,), size=(20, 45)),
    Species("rockling",     (LEDGE,),           32, size=(15, 30)),
    Species("scorpionfish", (LEDGE,),           17, size=(12, 28)),
    Species("conger",       (LEDGE,),           10, (NIGHT,), size=(60, 180)),
    Species("john dory",    (LEDGE,),            5, size=(25, 55)),
    Species("red mullet",   (LEDGE,),            4, (DUSK,), months=(6, 7, 8, 9), size=(20, 40)),
    Species("lumpsucker",   (LEDGE,),            2, months=(2, 3, 4), size=(20, 50)),
    Species("silverjack",   (LEDGE,),            1, (DAWN,), size=(30, 65)),

    # -- anywhere, and mostly not fish -----------------------------------
    Species("old boot",     (OPEN, SHALLOWS, REEDS, LEDGE), 12, size=(28, 34), junk=True),
    Species("driftwood",    (OPEN, SHALLOWS, REEDS, LEDGE),  9, size=(20, 80), junk=True),
    Species("bottle",       (OPEN, SHALLOWS, REEDS, LEDGE),  5, size=(18, 30), junk=True),
)

BY_NAME = {s.name: s for s in FISH}
COIN = "\u00a4"


def hour_band(hour: int) -> str:
    if 5 <= hour < 8:
        return DAWN
    if 8 <= hour < 18:
        return DAY
    if 18 <= hour < 21:
        return DUSK
    return NIGHT


def pool_at(world, x: int, y: int) -> str | None:
    """Which water a spot fishes into.

    A place beside a rock fishes the ledge whatever else is around it, because
    the rock is the interesting thing. Otherwise reeds, then open water, then
    the shallows.
    """
    around = [world.at(x + dx, y + dy)
              for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                             (-1, -1), (1, -1), (-1, 1), (1, 1))
              if world.inside(x + dx, y + dy)]
    if ROCK in around and any(t in (WATER, SHALLOW, REED) for t in around):
        return LEDGE
    if REED in around:
        return REEDS

    # What matters is how quickly it gets deep, not how much of each is about.
    # Counting area made every spot the shallows, because a beach is fronted by
    # shallows by definition and half the neighbourhood is land. A steep shore
    # or a point fishes the open sea; a gently shelving one does not.
    wet = False
    for reach in (1, 2, 3):
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                if max(abs(dx), abs(dy)) != reach:
                    continue
                if not world.inside(x + dx, y + dy):
                    continue
                tile = world.at(x + dx, y + dy)
                if tile == WATER:
                    return OPEN
                if tile == SHALLOW:
                    wet = True
        if wet and reach >= 2:
            break
    return SHALLOWS if wet else None


def biting(pool: str, month: int, hour: int) -> list:
    """Everything that could take a hook here, now, with its weight.

    A rock ledge reaches the open sea as well as its own fish, because a point
    juts into deeper water. Without that, a gently shelving coast could not
    reach the open table at all and offered barely half the species in the
    game.
    """
    band = hour_band(hour)
    reaches = {pool, OPEN} if pool == LEDGE else {pool}
    out = []
    for fish in FISH:
        if not reaches & set(fish.water):
            continue
        if fish.hours and band not in fish.hours:
            continue
        if fish.months and month not in fish.months:
            continue
        out.append(fish)
    return out


def catch(pool: str, month: int, hour: int, roll: int):
    """One cast. `roll` is a number the caller has already decided.

    Kept separate from any clock so the same cast can be replayed and checked,
    and so nothing in here needs to know what time it is.
    """
    pond = biting(pool, month, hour)
    if not pond:
        return None
    total = sum(f.weight for f in pond)
    pick = roll % total
    for fish in pond:
        pick -= fish.weight
        if pick < 0:
            return fish
    return pond[-1]


def size_of(fish: Species, roll: int) -> int:
    """Most are middling; the odd one is a story. Two rolls averaged bunch
    them towards the middle, and the third pulls the tail out."""
    low, high = fish.size
    span = high - low
    a, b = roll % 1000, (roll // 1000) % 1000
    middling = (a + b) / 2000
    if (roll // 1000000) % 100 == 0:
        middling = 1.0                     # one cast in a hundred is a monster
    return int(low + span * middling)


def cast(world, x: int, y: int, month: int, hour: int, salt) -> tuple:
    """What comes up, and how big. Returns (species, centimetres) or (None, 0).

    The roll is seeded from the place and the salt, not from a clock, so every
    machine that hears about a cast can check it produced what was claimed.
    """
    pool = pool_at(world, x, y)
    if pool is None:
        return None, 0
    rng = Rng(seed_of(world.seed, x, y, month, hour, salt))
    fish = catch(pool, month, hour, rng.next())
    if fish is None:
        return None, 0
    return fish, size_of(fish, rng.next())
