# longshore

A coast, some fish, and whoever you can hear. Played over LoRa radio, on
[loraline](https://github.com/intervalplace/loraline).

Nothing is at stake and nothing decays. You walk about, you fish, you talk. The
number that goes up is how many kinds you have ever caught, and being away for
a month costs you nothing.

## Why it is nothing like catacomms

catacomms is four minutes, everybody present, every machine agreeing on one
room to the byte. That took turn locking, state hashes and divergence
detection, because a disagreement there would matter.

Here nobody is racing anybody and my catch does not change your water. So there
is no consensus to reach, no engine to keep in step, and no lockstep: you keep
your own state, your position rides along on a heartbeat, and if my view of you
is a second stale then it is a second stale.

Which leaves a nice property. In catacomms a stale view is a fault. Here it is
distance: somebody at the edge of your range updates rarely and hazily, and
somebody beside you is crisp. The fidelity of the world falls off with the
radio.

## The world

Forty by twenty-four, derived and never transmitted. A seed gives a coastline, and everyone with the
same seed is on the same coast without a byte crossing the air. Bays,
headlands, reed beds, rocks standing out of the water.

Thresholds are picked by quantile rather than fixed, because fixed cut-offs
gave one seed 4% water and the next 28%. Every coast is guaranteed a few rocks
standing in reachable water: seven coasts in twenty came out with none, and a
coast without a ledge cannot reach the open sea at all, so it offered
twenty-four species of forty-two.

There are about thirty-five places to stand and fish on a coast. There appeared
to be a hundred and twenty until reading off the edge of the map stopped
counting as water to cast into.

## The fish

Forty-two species across four waters: open sea, the shallows, reed beds and
rock ledges. What is biting depends on where you sit, the hour, and the month,
so a year has a shape and a spot has its own.

Over a whole coast and a whole year: 40% common, 38% uncommon, 8% scarce, 2%
rare, 13% junk. A given spot at a given hour is lopsided, which is the reason
to get up and walk somewhere else.

A cast is derived from the place, the day, the hour and a salt, so anybody can
check that a cast produced what was claimed.

## Fishing

Tap the water to fish it: you walk to the nearest place you could cast from,
and cast when you arrive. Tap the land to walk. Tap again to strike.

A bite comes in seven to twenty-four seconds and you have under three seconds
to strike. Walking away cancels the cast rather than dragging a line up the
beach.

The log keeps your best of each kind and never takes anything away, and is
written beside your identity every half minute. Without that the angler was
rebuilt from nothing at every start and a level meant to take a year reset
whenever the window closed, which made the whole of it a lie.

## The tide

Twelve hours and twenty-five minutes, worked out from the clock. Every machine
has the same water at the same moment and no frame is ever spent saying so,
which is the third thing here that costs nothing because nobody has to be
told: the firepit comes from the seed, the fire from who is standing near it.

At low water the flats are out and you can walk on them, which opens about
twenty more places to fish from. It never closes one. A tide that shut the
fishing until eight would be a schedule, and a schedule is an obligation:
there are no stakes here and nothing decays, and something you have to turn up
for is both.

The sea coming in around you walks you back up the beach. Being stood in the
water is not a punishment and losing a cast to the tide would be.

Low, coming in, high, going out. Four words, because nobody on a shore says
the tide is at zero point four.

## The fire

Every coast has one, where the fishing is. Derived from the seed like
everything else, so nobody places it and nobody is told where it is.

**It is lit while people are there and out when they are not**, and that costs
nothing: it is not tended, it does not go out while you are away, and you
cannot come back to a cold one. A fire that needed feeding would be decay with
a flame on it.

Whether it is burning is worked out from where everybody is standing, which
every machine already knows from the heartbeats. No part of the fire crosses
the radio.

Put your last catch on with **c** and everybody nearby sees what it is, in the
same fourteen characters a catch already uses. Nothing is gained by cooking
and nothing is lost. It is a reason to walk over to where the others are.

The driftwood you keep pulling out, the one disappointment in the game, turns
out to be what it burns.

You cannot stand in it.

## A number only you can see

Your fishing goes up with every fish. Rare ones count for more, gently: a
person who fished all evening and caught roach should not end up behind where
they started.

An evening reaches about level six, a month of weekly ones about eleven, a
year about twenty-two, and there is no last level. The curve is polynomial
rather than exponential, because an exponent put level forty at fourteen
thousand hours, which is not a level, it is a joke.

It is derived from the log rather than stored, so there is no second number to
keep in step. And it is **not in the presence string and never will be**: the
moment it is on the wire somebody can write a client that shows everybody's,
and then it is a leaderboard whether anybody meant one or not.

Which means if you want to know somebody's, you have to ask, and they can lie,
and nobody minds. That is the whole of it.

The collection is still there, and still the thing worth having: what you have
ever caught, which stops moving once you have seen most of it. The level keeps
moving after that, which is why both exist.

When something takes the float it turns red and throws ripples. On the strike
the name and size float up and fade, tinted by rarity, and land in the log. The
sidebar keeps what you have had lately, and two counters: kinds, and caught.

Somebody else landing one shows the same way over their head, because the name
and the size are already in the fourteen characters riding on their heartbeat.

Anybody with a bite gets a bouncing mark above them, so you can glance along
the shore and see that something is about to happen to somebody. There is no
catch count over anybody's head: four people on a beach with numbers above them
are being ranked whether anybody meant it, and your own count is in your own
sidebar where only you see it.
That is the most social thing that happens here, and for a while the client was
parsing it off the air and throwing it away.

## The look

Isometric, and drawn the way a handheld of about 2003 drew things: one 288x192
framebuffer blitted once with nearest neighbour, a fifteen-bit palette so every
colour is a multiple of eight, 2:1 diamonds with the cut earth showing beneath
them, Bayer-dithered top faces, and a hard black edge on everything that stands
up.

No WebGL, and it would not help. The look is constraint rather than
capability, and at thirty thousand pixels a 2D context has nothing to
apologise for.

Above rather than beside. Isometric was built and then put away: a camera
means you cannot see who is on the shore, and seeing who is on the shore is
most of why anybody is on it. It also spends its whole budget on traversal,
which an action game does all day and this one barely does at all. The palette
discipline came back from it; the projection did not.

`view_iso.py` is still there and is genuinely nicer for walking about.
`FLAT_PAGE` in `web.py` is the plain one it all started from.

People are drawn larger than their tile and wear a name on a dark plate. That
helped and did not settle it, so the coast came down from sixty-four by
thirty-six to forty by twenty-four and the tiles went up to eighteen pixels.
Two and a half thousand tiles swallowed four figures whole; a thousand does
not.

Shrinking it cost ten species before anything else was changed. Rock ledges
were guaranteed on every coast and reed beds were not, which mattered not at
all on a large map and a great deal on a small one. Both are guaranteed now.

## Sound and speech

What somebody just said appears over their head for seven seconds, as well as
in the panel. The whole game is people sitting by the water talking, and
keeping speech in a sidebar makes that look like a chat client with a picture
beside it.

Sound is synthesised in the page, so there is nothing to fetch: a plop on the
cast, a knock when something takes it, a lift when you land one, a better one
for a kind you have never caught, and a quieter version when somebody else
lands theirs. The bite is the one that matters, because you will be looking
somewhere else, which is rather the point, and a bite lasts under three
seconds. One button turns it off.

## On a phone

The browser view listens on every interface, so the radio can stay plugged into
a laptop while you play from the sofa: open `http://that-machine:8080` on a
phone on the same network. Tapping is the whole interface anyway.

## Seeing each other

Position and what you are doing fit in fourteen characters, which ride on the
heartbeat loraline was sending anyway. It costs 15 ms on a frame already going
out, so seeing everybody is free.

## Playing

```
git clone https://github.com/intervalplace/loraline
git clone https://github.com/intervalplace/longshore
pip install -r longshore/requirements.txt
cd longshore && PYTHONPATH=../loraline python tests.py
```

Then, with no radio at all:

```
PYTHONPATH=../loraline python -m longshore --nick yourname --coast ourbay
```

Open `localhost:8080`. With a radio, and everybody on the same coast:

```
PYTHONPATH=../loraline python -m longshore --nick yourname --coast ourbay \
    --port /dev/ttyUSB0 --band eu868
```

Everyone must pass the same `--coast`, or you will each be on your own
coastline, alone.

## Licence

MIT.
