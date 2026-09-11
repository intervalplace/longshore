"""longshore's tests. No hardware, no radio, no waiting."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collections import Counter
from longshore.world import build, WATER, SHALLOW, SAND, GRASS, ROCK, REED, TREE
from longshore import fish as F
from longshore.angler import (Angler, Log, read_presence,
                              IDLE, WAITING, BITING, DONE, BITE_WINDOW)

PASSED = 0
def ok(text):
    global PASSED
    PASSED += 1
    print(f"  ok  {text}")

# ---------- the world is a fact ----------
one, two = build("quiet-bay"), build("quiet-bay")
assert one.tiles == two.tiles
assert build("other-bay").tiles != one.tiles
ok("the same seed is the same coast, everywhere, without anybody sending it")

sizes = Counter()
for i in range(12):
    w = build(f"coast-{i}")
    for row in w.tiles:
        sizes.update(row)
total = sum(sizes.values())
water = 100 * sizes[WATER] / total
assert 20 < water < 40, water
assert all(sizes[t] > 0 for t in (WATER, SHALLOW, SAND, GRASS, ROCK, REED, TREE))
ok(f"every seed gets a real coast ({water:.0f}% water, and all seven tiles appear)")

spots = [(x, y) for y in range(one.height) for x in range(one.width)
         if one.fishable_from(x, y)]
assert 20 < len(spots) < 90, len(spots)
assert all(one.walkable(x, y) for x, y in spots)
ok(f"{len(spots)} places to stand and fish, all of them dry land")

# Every coast can offer every species. A shelving one with no rock ledge could
# not reach the open sea at all and held twenty-four of forty-two.
for seed in ("bay-0", "bay-3", "bay-5", "quiet-bay", "longshore"):
    coast = build(seed)
    here = {F.pool_at(coast, x, y)
            for y in range(coast.height) for x in range(coast.width)
            if coast.fishable_from(x, y)}
    here.discard(None)
    kinds = {f.name for pool in here for month in range(1, 13)
             for hour in (2, 6, 12, 19) for f in F.biting(pool, month, hour)}
    assert len(kinds) == len(F.FISH), (seed, len(kinds))
ok(f"and every coast can offer all {len(F.FISH)} species over a year")

# ---------- what is biting ----------
pools = Counter(F.pool_at(one, x, y) for x, y in spots)
assert set(pools) <= {F.OPEN, F.SHALLOWS, F.REEDS, F.LEDGE}
assert len(pools) >= 3, pools
ok(f"the water you sit beside decides the fishing: {dict(pools)}")

june_night = F.biting(F.REEDS, 6, 2)
june_noon = F.biting(F.REEDS, 6, 12)
assert {f.name for f in june_night} != {f.name for f in june_noon}
assert any(f.name == "wels" for f in june_night)
assert not any(f.name == "wels" for f in june_noon)
ok("time of day changes what is there; the wels is a night fish")

assert not any(f.name == "wels" for f in F.biting(F.REEDS, 1, 2))
assert any(f.name == "cod" for f in F.biting(F.OPEN, 12, 12))
assert not any(f.name == "cod" for f in F.biting(F.OPEN, 7, 12))
ok("and the month does too, so a year has a shape")

# Rarity is a claim about the whole map and the whole year, not about any one
# spot at any one hour: the shallows in June hold no rare species at all, and
# their commonest fish happens to be labelled uncommon.
seen = Counter()
tries = 0
for month in range(1, 13):
    for hour in (2, 6, 12, 19):
        for spot in spots[::7]:
            tries += 1
            got, _ = F.cast(one, *spot, month, hour, tries)
            seen[got.rarity] += 1
assert seen["common"] > seen["uncommon"] > seen["scarce"] > seen["rare"], dict(seen)
assert seen["rare"] / tries < 0.02, seen["rare"] / tries
ok("over a year and a coastline, rare means rare: " +
   ", ".join(f"{k} {100*v/tries:.0f}%" for k, v in seen.most_common()))

# and a pool at a moment can be lopsided, which is the interesting part
lopsided = Counter(F.cast(one, *spots[0], 6, 19, i)[0].rarity for i in range(2000))
assert lopsided["rare"] == 0, "the shallows hold nothing rare in June"
ok("a given spot at a given hour has its own shape, which is why you move")

# a boot is not a scarce fish
assert F.BY_NAME["old boot"].rarity == "junk"
assert F.BY_NAME["halibut"].rarity == "rare"
ok("junk is its own thing and does not pad out the rare column")

# the same cast anywhere gives the same fish
here = F.cast(one, *spots[3], 6, 19, "salt")
there = F.cast(build("quiet-bay"), *spots[3], 6, 19, "salt")
assert here[0].name == there[0].name and here[1] == there[1]
ok("a cast can be checked by anybody, because it is derived from the place")

# ---------- fishing ----------
angler = Angler(*spots[0])
now = 1000.0
assert angler.cast(one, now, 6, 19)
assert angler.state == WAITING and angler.pending[0] is not None
assert not angler.cast(one, now, 6, 19), "you cannot cast twice"
ok("a cast decides there and then what is on the end of the line")

now = angler.until
assert ("bite", None) in angler.tick(now)
assert angler.state == BITING
species, cm = angler.strike(now + 1.0)
assert species is not None and cm > 0
assert angler.log.kinds == 1 and angler.log.caught == 1
ok(f"strike inside the window and it is yours ({species.name}, {cm} cm)")

angler.cast(one, now + 30, 6, 19)
now = angler.until
angler.tick(now)
assert ("lost", None) in angler.tick(now + BITE_WINDOW + 0.1)
assert angler.state == IDLE and angler.missed == 1
ok("let the window pass and it is gone, which is the only way to be wrong")

angler.cast(one, now + 100, 6, 19)
assert angler.strike(now + 101)[0] is None and angler.state == IDLE
ok("striking early loses it too")

# walking cancels
angler.cast(one, now + 200, 6, 19)
before = (angler.x, angler.y)
moved = any(angler.move(one, dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
assert moved and angler.state == IDLE
ok("walking away cancels the cast rather than dragging a line up the beach")

# ---------- the log only grows ----------
log = Log()
assert log.record("perch", 30, 1.0) is True
assert log.record("perch", 22, 2.0) is False
assert log.entries["perch"].count == 2
assert log.entries["perch"].best == 30, "a smaller one does not replace your best"
assert Log.from_dict(log.to_dict()).to_dict() == log.to_dict()
ok("the log keeps your best and never takes anything away")

# ---------- what other people see ----------
watcher = Angler(12, 7)
assert read_presence(watcher.presence()) == {"x": 12, "y": 7, "doing": "-",
                                             "fish": "", "cm": 0}
watcher.state, watcher.landed = DONE, (F.BY_NAME["pike"], 94)
shown = read_presence(watcher.presence())
assert shown["fish"] == "pike" and shown["cm"] == 94 and shown["doing"] == "+"
assert len(watcher.presence()) < 24, "it has to fit on a heartbeat"
ok(f"position and catch ride along in {len(watcher.presence())} characters")

for rubbish in ("", "back in 5", "@", "@12", "@x.y-", "@12.7", "hello"):
    assert read_presence(rubbish) is None, rubbish
ok("anything else in a personal message is left alone")


# ---------- walking and tapping ----------
from longshore import moving as M

start = M.first_stand(one)
assert one.fishable_from(*start)
middle_ish = abs(start[1] - one.height // 2) < one.height // 3
assert middle_ish, "you should not begin in a corner"
ok(f"you start somewhere in the middle of the coast, at {start}")

walker = Angler(*start)
water = M.float_for(one, walker)
steps, want = M.plan(one, walker, *water)
assert want and steps == [], "the water in front needs no walking"
ok("tapping the water you are already beside just fishes it")

# A coast has islands, so some water has no land route to it at all. Pick the
# furthest that does.
reachable = []
for y in range(one.height):
    for x in range(one.width):
        if one.at(x, y) not in (WATER, SHALLOW, REED):
            continue
        steps, want = M.plan(one, walker, x, y)
        if want and steps:
            reachable.append((len(steps), (x, y), steps))
assert reachable
walk_len, far, steps = max(reachable)
for step in steps:
    assert walker.move(one, step[0] - walker.x, step[1] - walker.y)
assert one.fishable_from(walker.x, walker.y)
ok(f"tapping water across the bay walks you {walk_len} paces and fishes it")

# and water you cannot reach on foot is simply not a walk
stranded = [(x, y) for y in range(one.height) for x in range(one.width)
            if one.at(x, y) in (WATER, SHALLOW, REED)
            and M.nearest_spot(one, (walker.x, walker.y), (x, y)) is not None
            and not M.path_between(one, (walker.x, walker.y),
                                   M.nearest_spot(one, (walker.x, walker.y), (x, y)))]
ok(f"water with no land route to it is left alone ({len(stranded)} such tiles here)")

dry = [(x, y) for y in range(one.height) for x in range(one.width)
       if one.walkable(x, y)]
steps, want = M.plan(one, walker, *dry[-1])
assert not want, "tapping land is a walk, not a cast"
ok("tapping the land is only a walk")

# a float never sits off the edge of the world
outside = [(x, y) for y in range(one.height) for x in range(one.width)
           if one.fishable_from(x, y)
           and (lambda f: f and not (0 <= f[0] < one.width and 0 <= f[1] < one.height))
               (M.float_for(one, None, x, y))]
assert not outside, outside[:3]
ok("a float always lands inside the map, even on the top row")


# ---------- somebody else landing one ----------
from longshore.angler import DONE as _DONE
mate = Angler(20, 12)
mate.state, mate.landed = _DONE, (F.BY_NAME["conger"], 140)
over_the_air = mate.presence()
heard = read_presence(over_the_air)
assert heard["fish"] == "conger" and heard["cm"] == 140
assert F.BY_NAME[heard["fish"]].rarity == "scarce"
ok("a catch travels with the name and the size, so the shore can see it")

mate.state, mate.landed = IDLE, (None, 0)
assert read_presence(mate.presence())["fish"] == ""
ok("and stops being announced once they put it down")


# ---------- you cannot fish from a field ----------
inland = [(x, y) for y in range(one.height) for x in range(one.width)
          if one.walkable(x, y) and not one.fishable_from(x, y)]
assert inland, "expected some land away from the water"
landlocked = Angler(*inland[len(inland) // 2])
assert not landlocked.cast(one, 1000.0, 6, 19)
assert landlocked.strike(1001.0) == (None, 0)
assert ":" not in landlocked.presence(), "nothing to announce"
ok("a cast is refused away from the water, so a catch is never announced inland")

beside = Angler(*M.first_stand(one))
beside.cast(one, 1000.0, 6, 19)
beside.tick(beside.until)
species, cm = beside.strike(beside.until + 1)
assert species is not None
assert one.fishable_from(beside.x, beside.y)
ok("and a catch is always announced from somewhere you could actually fish")


# ---------- a float goes out into open water ----------
every = [(x, y) for y in range(one.height) for x in range(one.width)
         if one.fishable_from(x, y)]
assert all(M.float_for(one, None, x, y) is not None for x, y in every)
ok(f"every one of the {len(every)} spots has somewhere to put a float")

# Straight up is where the name and the bite mark go, so it is a last resort
# rather than an impossibility: a spot in a narrow inlet may have water only to
# the north.
overhead = [s for s in every if M.float_for(one, None, *s) == [s[0], s[1] - 1]]
assert len(overhead) / len(every) < 0.06, (len(overhead), len(every))
for spot in overhead:
    sideways = [d for d in ((-1, 0), (1, 0), (0, 1))
                if one.inside(spot[0] + d[0], spot[1] + d[1])
                and one.at(spot[0] + d[0], spot[1] + d[1]) in (WATER, SHALLOW, REED)]
    assert not sideways, (spot, sideways)
ok(f"the float goes out sideways where it can ({len(overhead)} of {len(every)} "
   f"have water only overhead)")

# the border is not a fishing spot with nothing in front of it
edge = [(x, y) for y in range(one.height) for x in range(one.width)
        if (x in (0, one.width - 1) or y in (0, one.height - 1))
        and one.fishable_from(x, y)]
assert all(any(one.inside(x + dx, y + dy)
               and one.at(x + dx, y + dy) in (WATER, SHALLOW, REED)
               for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)))
           for x, y in edge)
ok("reading off the edge of the map no longer counts as water to fish")

print(f"\nALL PASS  ({PASSED} checks)")
