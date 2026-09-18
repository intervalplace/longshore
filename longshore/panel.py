"""longshore, riding on the loraline app.

The coast, the fish and the angler are untouched. This does what the
standalone loop did: walk you about, mind the clock, read other people's
positions off their heartbeats, and hand the page something to draw.

Not always on. Nothing here happens without you, and a line left in the water
while you read something else would be catching fish on your behalf, which is
the opposite of the point.
"""

from __future__ import annotations

import time
from datetime import datetime

from loraline.host import Panel

from . import fish as F
from .angler import (Angler, BITING, DONE, IDLE, WAITING, level_from,
                     load_log, read_presence, save_log)
from .world import firepit
from .moving import first_stand, float_for, plan
from .web import PAGE
from .world import build

STEP_SECONDS = 0.28
SPEECH_SECONDS = 7.0
APP = "longshore"


class ShorePanel(Panel):
    tag = APP
    title = "longshore"
    route = "/longshore"
    always = False

    def __init__(self, coast: str = "longshore") -> None:
        self.world = build(coast)
        self.me = None
        self.host = None
        self.log: list = []
        self.walking: list = []
        self.walk_at = 0.0
        self.intent = None
        self.caught: list = []
        # A catch stays in the list for three seconds so everybody nearby sees
        # it, and a snapshot goes out about once a second, so the page was
        # handed the same catch three times and drew the name three times. An
        # id it can remember settles it.
        self.catch_no = 0
        self.said: dict = {}
        self.heard_catch: dict = {}
        self.seats: dict = {}
        self.log_path = None
        self.dirty = False
        self.last_save = 0.0

    # -- housekeeping ------------------------------------------------------

    def note(self, text: str, role: str = "muted") -> None:
        self.log.append((text, role))
        del self.log[:-60]

    def seat_of(self, address: str) -> int:
        if address not in self.seats:
            self.seats[address] = len(self.seats) % 6
        return self.seats[address]

    # -- the panel ---------------------------------------------------------

    def start(self, host) -> None:
        self.host = host
        from loraline import crypto
        self.log_path = str(getattr(host.identity, "path", "")
                            or crypto.DEFAULT_PATH) + ".longshore.json"
        kept = load_log(self.log_path)
        self.me = Angler(*first_stand(self.world), log=kept)
        if kept.caught:
            self.note(f"Picked up where you left off: fishing {kept.level}, "
                      f"{kept.kinds} kinds.")
        self.seat_of(host.address)
        self.note(f"A coast. You are {host.nick} on {self.world.seed}.")
        self.note("Tap the water to fish it, the land to walk.")

    def heard(self, src: str, payload: str) -> None:
        """Nothing to do: positions ride on everybody's heartbeat, so there is
        no traffic of our own to listen for. Kept so the tag is claimed."""

    def tick(self, now: float) -> None:
        if self.me is None:
            return
        stamp = datetime.now()
        # The sea comes in around anybody stood out on the flats.
        if self.me.wade_back(self.world, now):
            self.walking = []
            self.note("The tide came in and you waded back.")
        if self.walking and now - self.walk_at >= STEP_SECONDS:
            step = self.walking.pop(0)
            self.me.move(self.world, step[0] - self.me.x, step[1] - self.me.y, now)
            self.walk_at = now
            if not self.walking and self.intent is not None:
                if self.me.cast(self.world, now, stamp.month, stamp.hour):
                    self.note("You cast.")
                self.intent = None
        for kind, what in self.me.tick(now):
            if kind == "bite":
                self.note("Something is on it.", "gold")
            elif kind == "lost":
                self.note("Gone.")
            elif kind == "cooked":
                self.note(f"The {what} is done.", "gold")
                self.dirty = True

        # Somebody else landing one is most of the reason to be on a shore
        # with other people, and it is already on their heartbeat.
        for peer in self.host.peers():
            shown = read_presence(peer.app or "")
            if shown is None or not shown["fish"]:
                self.heard_catch.pop(peer.address, None)
                continue
            token = f'{shown["fish"]}:{shown["cm"]}'
            if self.heard_catch.get(peer.address) == token:
                continue
            self.heard_catch[peer.address] = token
            kind = F.BY_NAME.get(shown["fish"])
            self.note(f'{peer.label} landed a {shown["fish"]}, {shown["cm"]} cm.',
                      "gold" if kind and kind.rarity == "rare" else "muted")
            self.catch_no += 1
            self.caught.append({"id": self.catch_no,
                                "name": shown["fish"], "cm": shown["cm"],
                                "rarity": kind.rarity if kind else "common",
                                "x": shown["x"], "y": shown["y"], "at": now})

        # Where we are and what we are doing, on the heartbeat that was going
        # out anyway. Costs fifteen milliseconds on a frame already sent.
        self.host.client.session.set_app_state(self.me.presence())
        # Written every half minute rather than on every fish: a log that
        # rewrites itself for each roach spends the evening on a disk.
        if self.dirty and now - self.last_save > 30.0:
            save_log(self.me.log, self.log_path)
            self.dirty, self.last_save = False, now
        self.caught[:] = [c for c in self.caught if now - c["at"] < 3]
        for who, (_, when) in list(self.said.items()):
            if now - when > SPEECH_SECONDS:
                self.said.pop(who, None)

    def handle(self, order: dict) -> None:
        if self.me is None:
            return
        now = time.time()
        stamp = datetime.now()
        what = order.get("do")
        if what == "tap":
            x, y = int(order.get("x", 0)), int(order.get("y", 0))
            self.walking, want = plan(self.world, self.me, x, y)
            self.walk_at = now
            self.intent = True if want else None
            if want and not self.walking:
                if self.me.cast(self.world, now, stamp.month, stamp.hour):
                    self.note("You cast.")
                self.intent = None
            elif self.walking:
                self.me.stop()
        elif what == "strike":
            species, cm = self.me.strike(now)
            if species is not None:
                self.dirty = True
                fresh = self.me.log.entries[species.name].count == 1
                self.note(f"{species.name}, {cm} cm." +
                          (" A kind you have never caught." if fresh else ""),
                          "gold" if fresh or species.rarity == "rare" else "muted")
                self.catch_no += 1
                self.caught.append({"id": self.catch_no,
                                    "name": species.name, "cm": cm,
                                    "rarity": species.rarity,
                                    "x": self.me.x, "y": self.me.y, "at": now})
        elif what == "cast":
            if self.me.cast(self.world, now, stamp.month, stamp.hour):
                self.note("You cast.")
        elif what == "cook":
            if self.me.cook(self.world, now):
                self.note(f"You put the {self.me.at_fire[0]} on the fire.", "gold")
            elif self.me.wood and self.me.feed(self.world, now):
                self.note("You put a piece of driftwood on.")
            elif not self.me.by_the_fire(self.world):
                self.note("You are not by the fire.")
            else:
                self.note("Nothing to put on.")
        elif what == "step":
            self.walking, self.intent = [], None
            delta = {"n": (0, -1), "s": (0, 1),
                     "e": (1, 0), "w": (-1, 0)}.get(order.get("dir", ""))
            if delta:
                self.me.move(self.world, *delta)
        elif what == "say":
            text = (order.get("text") or "").strip()
            if text:
                session = self.host.client.session
                session.compose(text, "*", now)
                self.note(f"{session.nick}: {text}", "gold")
                self.said[self.host.address] = (text, now)

    def spoke(self, address: str, text: str, now: float) -> None:
        """The host hands us chat so it can appear over people's heads."""
        self.said[address] = (text, now)

    def snapshot(self) -> dict:
        if self.me is None:
            return {"world": None, "people": [], "log": []}
        from .__main__ import snapshot as build_snapshot
        return build_snapshot(self.world, self.me, self.host.client.session,
                              [(t, r) for t, r in self.log], self.host.nick,
                              self.seat_of, self.caught, datetime.now(), self.said)

    def page(self, path: str = "") -> str:
        """The coast. The path is taken and ignored: loraline passes the route
        it matched, and a panel that would not accept it raised a TypeError
        the host swallowed, serving the chat page instead."""
        return PAGE
