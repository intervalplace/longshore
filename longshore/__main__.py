"""longshore: a coast, some fish, and whoever you can hear.

Rides loraline. Your position and what you are doing go out on the heartbeat
that was already being sent, so seeing each other costs nothing. Nothing else
is transmitted, because nothing else affects anybody: my catch does not change
your water, so there is no state to agree on and no engine to keep in step.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

from loraline import crypto
from loraline.client import Client
from loraline.crypto import GROUP, Identity, Keyring
from loraline.session import MessageEvent, SystemEvent
from loraline.transport import (Link, LoRaInterface, RadioConfig,
                                TCPClientInterface, TCPServerInterface)

from . import fish as F
from .angler import (Angler, COOK_SECONDS, Log, level_from, read_presence,
                     BITING, COOKING, DONE, FEEDING, IDLE, WAITING)
from .moving import first_stand, float_for, nearest_spot, path_between, plan
from .web import WebView
from . import tide
from .world import build

STEP_SECONDS = 0.28          # how long a pace takes
SPEECH_SECONDS = 7.0         # how long a line stays over somebody's head
BANDS = {"eu868": dict(channel=18, sf=7, power=8, duty=0.01),
         "us915": dict(channel=65, sf=10, power=22, duty=1.0),
         "au915": dict(channel=65, sf=10, power=22, duty=1.0)}


def run(client: Client, view: WebView, world, nick: str) -> None:
    session = client.session
    me = Angler(*first_stand(world))
    log: list = []
    walking: list = []
    walk_at = 0.0
    intent = None                 # a cast waiting for us to arrive
    caught_recently: list = []
    seats: dict = {}
    # What each person last announced catching. Their heartbeat repeats for as
    # long as they are holding the fish up, so without this the same perch
    # would be announced half a dozen times.
    heard_catch: dict = {}
    # What each person last said, and when. Speech belongs on the shore rather
    # than only in a panel: the whole game is people sitting by the water
    # talking, and a sidebar makes that look like a chat client with a picture
    # next to it.
    said: dict = {}

    def note(text, role="muted"):
        log.append((text, role))
        del log[:-60]

    def seat_of(address):
        if address not in seats:
            seats[address] = len(seats) % 6
        return seats[address]

    seat_of(session.address)
    note(f"longshore. You are {nick} on {world.seed}.")
    note("Tap the water to fish it, the land to walk. Tap again to strike.")

    while True:
        now = time.time()
        stamp = datetime.now()

        for event in client.pump():
            if isinstance(event, MessageEvent) and event.incoming:
                note(f"{event.who}: {event.text}", "gold")
                if event.src:
                    said[event.src] = (event.text, now)
            elif isinstance(event, SystemEvent):
                note(event.text, "muted")

        # walking
        if walking and now - walk_at >= STEP_SECONDS:
            step = walking.pop(0)
            me.move(world, step[0] - me.x, step[1] - me.y)
            walk_at = now
            if not walking and intent is not None:
                if me.cast(world, now, stamp.month, stamp.hour):
                    note("You cast.")
                intent = None

        for kind, what in me.tick(now):
            if kind == "bite":
                note("Something is on it.", "gold")
            elif kind == "lost":
                note("Gone.")
            elif kind == "cooked":
                note(f"The {what} is done.", "gold")

        for typed in view.drain():
            verb, _, rest = typed.partition(" ")
            if verb == "say" and rest:
                session.compose(rest, GROUP, now)
                note(f"{nick}: {rest}", "gold")
                said[session.address] = (rest, now)
            elif verb == "strike":
                species, cm = me.strike(now)
                if species is not None:
                    fresh = me.log.entries[species.name].count == 1
                    note(f"{species.name}, {cm} cm." +
                         (" A kind you have never caught." if fresh else ""),
                         "gold" if fresh or species.rarity == "rare" else "muted")
                    caught_recently.append({"name": species.name, "cm": cm,
                                            "rarity": species.rarity,
                                            "x": me.x, "y": me.y, "at": now})
            elif verb == "cast":
                if me.cast(world, now, stamp.month, stamp.hour):
                    note("You cast.")
            elif verb == "cook":
                if me.cook(world, now):
                    note(f"You put the {me.at_fire[0]} on the fire.", "gold")
                elif me.wood and me.feed(world, now):
                    note("You put a piece of driftwood on.")
                elif not me.by_the_fire(world):
                    note("You are not by the fire.")
                else:
                    note("Nothing to put on.")
            elif verb == "step" and rest:
                walking, intent = [], None
                delta = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}.get(rest)
                if delta:
                    me.move(world, *delta)
            elif verb == "tap":
                bits = rest.split()
                if len(bits) == 2 and all(b.lstrip("-").isdigit() for b in bits):
                    walking, want = plan(world, me, int(bits[0]), int(bits[1]))
                    walk_at = now
                    intent = True if want else None
                    if want and not walking:
                        if me.cast(world, now, stamp.month, stamp.hour):
                            note("You cast.")
                        intent = None
                    elif walking:
                        me.stop()

        # Somebody else landing one is the whole point of being here for it,
        # and the name and size were already on the air.
        for peer in session.online_peers():
            shown = read_presence(peer.app or "")
            if shown is None or not shown["fish"]:
                heard_catch.pop(peer.address, None)
                continue
            token = f'{shown["fish"]}:{shown["cm"]}'
            if heard_catch.get(peer.address) == token:
                continue
            heard_catch[peer.address] = token
            kind = F.BY_NAME.get(shown["fish"])
            rarity = kind.rarity if kind else "common"
            note(f'{peer.label} landed a {shown["fish"]}, {shown["cm"]} cm.',
                 "gold" if rarity == "rare" else "muted")
            caught_recently.append({"name": shown["fish"], "cm": shown["cm"],
                                    "rarity": rarity, "x": shown["x"],
                                    "y": shown["y"], "at": now})

        # Whatever we are doing, on the heartbeat that was going anyway.
        session.set_app_state(me.presence())

        caught_recently[:] = [c for c in caught_recently if now - c["at"] < 3]
        for who in [a for a, (_, when) in said.items() if now - when > SPEECH_SECONDS]:
            said.pop(who, None)
        view.publish(snapshot(world, me, session, log, nick,
                              seat_of, caught_recently, stamp, said))
        time.sleep(0.08)


# Every state a person can be in, as one character. Missing cooking and
# feeding here meant the snapshot raised the moment anybody put a fish on the
# fire, which is a poor way to find out a map is incomplete.
DOING = {IDLE: "-", WAITING: "c", BITING: "!", DONE: "+",
         COOKING: "k", FEEDING: "f"}


def snapshot(world, me, session, log, nick, seat_of, caught, stamp, said,
             levelled: int = 0) -> dict:
    import time as _time
    now = _time.time()
    pool = F.pool_at(world, me.x, me.y) if world.fishable_from(me.x, me.y) else None
    people = [{"id": session.address, "name": nick, "me": True,
               "said": said.get(session.address, ("", 0))[0],
               "x": me.x, "y": me.y, "doing": DOING.get(me.state, "-"),
               "seat": seat_of(session.address),
               # How far through the cook, so the page has something to draw
               # over twenty-five seconds of standing still.
               "until": max(0.0, me.until - now) if me.state == COOKING else 0.0,
               "span": COOK_SECONDS if me.state == COOKING else 0.0,
               "onfire": me.at_fire[0] or "",
               "float": float_for(world, me)}]
    for peer in session.online_peers():
        shown = read_presence(peer.app or "")
        if shown is None:
            continue
        people.append({"id": peer.address, "name": peer.label, "me": False,
                       "said": said.get(peer.address, ("", 0))[0],
                       "x": shown["x"], "y": shown["y"], "doing": shown["doing"],
                       "seat": seat_of(peer.address),
                       "float": float_for(world, None, shown["x"], shown["y"])})
    recent = sorted(me.log.entries.values(), key=lambda e: -e.last)[:8]
    # Yours, and nobody else's. It is not in the presence string and never
    # will be: the moment it is on the wire somebody can write a client that
    # shows everybody's, and then it is a leaderboard whether anybody meant
    # one or not. Being unverifiable is the point. Ask people, and they can
    # lie, and nobody minds.
    level, into, needs = level_from(me.log.points)

    # How the fire is doing is worked out from where everybody is standing,
    # which every machine already knows. Nothing about it is transmitted: it
    # is lit because people are there, and out because they are not, and
    # nobody has to tend it or come back to a cold one.
    from .world import firepit
    from .angler import FIRE_REACH
    pit = firepit(world)
    around = [p for p in people
              if pit and max(abs(p["x"] - pit[0]), abs(p["y"] - pit[1])) <= FIRE_REACH]
    tending = [p["name"] for p in around if p["doing"] in ("k", "f")]
    fire = None
    if pit:
        fire = {"x": pit[0], "y": pit[1], "lit": bool(around),
                "round_it": len(around),
                "cooking": [{"name": p["name"], "seat": p["seat"]}
                            for p in around if p["doing"] == "k"],
                "tending": tending}
    return {
        "world": {"seed": world.seed, "w": world.width, "h": world.height,
                  "tiles": ["".join(chr(48 + t) for t in row) for row in world.tiles]},
        "people": people,
        "me": {"kinds": me.log.kinds, "caught": me.log.caught, "pool": pool,
               "level": level, "into": into, "needs": needs,
               "wood": me.wood, "cooked": me.log.cooked,
               "at_fire": me.by_the_fire(world),
               "doing": people[0]["doing"],
               "recent": [{"name": e.name, "cm": e.best,
                           "rarity": F.BY_NAME[e.name].rarity
                           if e.name in F.BY_NAME else "common"} for e in recent]},
        "fire": fire,
        # Set for one snapshot when a level is reached, so the view says so
        # once and then stops.
        "levelled": levelled,
        # Worked out from the clock, so it is the same water on every machine
        # and no frame is ever spent saying so.
        "tide": {"state": tide.state(now), "height": round(tide.height(now), 3),
                 "out": tide.out(now)},
        "caught": caught,
        "log": [{"text": t, "role": r} for t, r in log[-40:]],
        "status": f"{stamp:%H:%M} \u00b7 {F.hour_band(stamp.hour)}",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="longshore")
    parser.add_argument("--nick", required=True)
    parser.add_argument("--coast", default="longshore",
                        help="which coastline; everybody must use the same one")
    parser.add_argument("--port", help="serial port of the radio")
    parser.add_argument("--band", choices=sorted(BANDS))
    parser.add_argument("--key", default=os.environ.get("LORALINE_KEY", ""))
    parser.add_argument("--identity")
    parser.add_argument("--tcp-listen", type=int)
    parser.add_argument("--tcp-connect")
    parser.add_argument("--web", type=int, nargs="?", const=8080, default=8080)
    args = parser.parse_args(argv)

    id_path = args.identity or crypto.DEFAULT_PATH
    identity = Identity.load_or_create(id_path)
    keyring = Keyring(identity, args.key or None,
                      keystore=str(id_path) + ".peers.json")

    bearers = []
    if args.port:
        if not args.band:
            print("--band is required with --port", file=sys.stderr)
            return 2
        preset = BANDS[args.band]
        bearers.append(LoRaInterface(args.port, RadioConfig(
            channel=preset["channel"], sf=preset["sf"],
            power=preset["power"], duty=preset["duty"])))
    if args.tcp_listen:
        bearers.append(TCPServerInterface(port=args.tcp_listen))
    if args.tcp_connect:
        host, _, port = args.tcp_connect.partition(":")
        bearers.append(TCPClientInterface(host, int(port or 4242)))
    if not bearers:
        bearers.append(TCPServerInterface(port=4242))

    for bearer in bearers:
        bearer.start()
    link = Link(bearers, keyring=keyring)
    client = Client(link, identity, keyring, nick=args.nick)
    world = build(args.coast)

    view = WebView(port=args.web)
    view.start()
    print(f"longshore on {args.coast}. Open http://localhost:{args.web}")
    try:
        run(client, view, world, args.nick)
    except KeyboardInterrupt:
        pass
    finally:
        view.close()
        link.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
