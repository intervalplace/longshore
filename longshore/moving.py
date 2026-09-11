"""Getting about: walking, tapping, and where a float lands.

Pure, and deliberately free of loraline, so the parts of longshore that are
just a coast and a person on it can be tested without a radio anywhere in
sight.
"""

from __future__ import annotations

from collections import deque


def path_between(world, start, goal):
    """Shortest walk over dry land. Breadth first, because a coastline is
    small and anything cleverer would be for its own sake."""
    if start == goal:
        return []
    seen = {start: None}
    queue = deque([start])
    while queue:
        here = queue.popleft()
        if here == goal:
            break
        x, y = here
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            step = (x + dx, y + dy)
            if step in seen or not world.walkable(*step):
                continue
            seen[step] = here
            queue.append(step)
    if goal not in seen:
        return []
    out, node = [], goal
    while node != start:
        out.append(node)
        node = seen[node]
    return list(reversed(out))


def nearest_spot(world, start, target):
    """Somewhere dry beside `target` that you can fish from, closest to you.

    Tapping water means fishing it, which means finding a place to stand. The
    nearest such place is nearly always the obvious one.
    """
    options = []
    tx, ty = target
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            spot = (tx + dx, ty + dy)
            if world.fishable_from(*spot):
                options.append(spot)
    if not options:
        return None
    return min(options, key=lambda s: (abs(s[0] - start[0]) + abs(s[1] - start[1]), s))


def plan(world, me, x, y):
    """A tap. Returns (the walk, whether to cast when you arrive).

    Tapping dry land is a walk. Tapping water is a walk to the nearest place
    you could fish it from, and then a cast: one gesture, because asking
    somebody to walk and then cast is asking them to do the obvious thing
    twice.
    """
    if world.walkable(x, y):
        target, want_cast = (x, y), False
    else:
        target, want_cast = nearest_spot(world, (me.x, me.y), (x, y)), True
    if target is None:
        return [], False
    return path_between(world, (me.x, me.y), target), want_cast


def first_stand(world):
    """Somewhere in the middle of the coast rather than in a corner, since
    this is the first thing anybody sees of the place."""
    middle = (world.width // 2, world.height // 2)
    spots = [(x, y) for y in range(world.height) for x in range(world.width)
             if world.fishable_from(x, y)]
    if not spots:
        return middle
    return min(spots, key=lambda s: (abs(s[1] - middle[1]) * 2 + abs(s[0] - middle[0]), s))


def float_for(world, angler, x=None, y=None):
    """Where the float sits: the nearest water in front of where they stand.

    Reading off the edge of the map returns water, so without the bounds check
    a float on the top row sat a tile above the sky.
    """
    if angler is not None:
        x, y = angler.x, angler.y
    wet = (0, 1, 5)          # water, shallow, reed
    options = []
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                   (-2, 0), (2, 0), (0, -2), (0, 2)):
        fx, fy = x + dx, y + dy
        if not (0 <= fx < world.width and 0 <= fy < world.height):
            continue
        if world.at(fx, fy) not in wet:
            continue
        # How open it is out there. Taking the first wet tile put the float
        # directly above the angler whenever the water happened to be north,
        # and the float, the name and the bite mark all landed on one spot.
        openness = sum(1 for ax in (-1, 0, 1) for ay in (-1, 0, 1)
                       if world.at(fx + ax, fy + ay) in wet)
        # Straight up is where the name and the bite mark go, so take it only
        # if there is nothing to either side.
        overhead = 1 if (dx == 0 and dy < 0) else 0
        options.append((overhead, -openness, abs(dx) + abs(dy), [fx, fy]))
    if not options:
        return None
    return min(options)[3]
