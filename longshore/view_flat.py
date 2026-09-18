"""longshore, drawn the way a handheld drew things, seen from above.

The palette discipline of the isometric view without what it cost. Fifteen
bits a colour, three tones a surface, Bayer dithering, a hard black edge on
everything that stands up, and one framebuffer blitted once with nearest
neighbour.

Above rather than beside, because this is a game where people mostly stand
still. Isometric rewards traversal, which is what an action game does all day
and what this one barely does at all, and it charges for that in the only
currency here that matters: seeing who is on the shore. A coast is sixty-four
by thirty-six and at twelve pixels a tile the whole of it is on screen, with
everybody on it, which is most of the reason to be there.
"""

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>longshore</title>
<style>
html,body{margin:0;padding:0;background:#000;
  font-family:ui-monospace,Menlo,Consolas,monospace;-webkit-user-select:none;
  user-select:none;touch-action:manipulation}
/* Laid out in the flow rather than pinned to the viewport. Fixed at inset:0
   put the coast underneath loraline's switcher and the channel warning, with
   no way to scroll to what they covered. */
#shell{min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:radial-gradient(120% 100% at 50% 0%,#0d120f 0%,#000 80%)}
#panel{position:relative;image-rendering:pixelated;
  box-shadow:0 0 0 2px #060806,0 0 0 5px #141a14}
canvas{display:block;image-rendering:pixelated;cursor:crosshair}
#say{position:fixed;left:50%;transform:translateX(-50%);bottom:10px;display:flex;gap:6px;
  width:min(92vw,440px)}
#say input{flex:1;background:#0d120e;border:1px solid #263026;color:#cfd8c8;
  font:12px ui-monospace,monospace;padding:6px 8px;border-radius:2px;min-width:0}
#say button{background:#1a231a;border:1px solid #263026;color:#cfd8c8;
  font:12px ui-monospace,monospace;padding:6px 10px;border-radius:2px;cursor:pointer}
</style></head><body>
<div id="shell"><div id="panel"><canvas id="screen"></canvas></div></div>
<form id="say"><input id="text" maxlength="120" placeholder="say something"><button>say</button></form>
<script>
'use strict';

// ---------------------------------------------------------------------------
// 1. THE PANEL
// ---------------------------------------------------------------------------
// Eighteen, on a forty by twenty-four coast: 720 by 432 and the whole of it
// on screen. Twelve was small enough that people vanished into the ground
// they were standing on.
const TILE = 18, CHROME = 44;
let GW = 720, GH = 432 + CHROME;
const fb = document.createElement('canvas');
const g = fb.getContext('2d', {alpha:false});
const screenCv = document.getElementById('screen');
const sg = screenCv.getContext('2d', {alpha:false});

function shape(w, h){
  GW = w*TILE; GH = h*TILE + CHROME;
  fb.width = GW; fb.height = GH;
  g.imageSmoothingEnabled = false;
  fit();
}
function fit(){
  // Whole multiples, because a tile drawn at one and a half pixels is the one
  // thing this look cannot survive.
  //
  // Except on a screen smaller than the coast. A handheld is 640 across and
  // this wants 720, and a view that runs off the edge is worse than one drawn
  // at an awkward size, so below one the canvas is left alone and the browser
  // is allowed to scale it down.
  // Measure what is actually there rather than guess at it.
  //
  // This reserved forty-eight pixels for everything around the canvas, which
  // is about right on its own and nowhere near it inside loraline, where
  // there is a switcher, a channel warning and a log as well. It then chose a
  // scale too big for the space and the coast ran off the top and bottom,
  // with no way to scroll to the rest of it.
  // Measure the shell, not the panel.
  //
  // The panel has no width of its own and shrinks to whatever the canvas is,
  // so measuring it made the canvas smaller, which made the panel smaller,
  // which made the canvas smaller: a feedback loop that collapsed the coast
  // to a postage stamp in the middle of a black screen.
  const shell = document.getElementById('shell');
  const said = document.getElementById('say');
  const above = shell.getBoundingClientRect().top;
  const below = said ? said.getBoundingClientRect().height + 12 : 0;
  const haveW = Math.max(160, (shell.clientWidth || innerWidth) - 12);
  const haveH = Math.max(120, innerHeight - Math.max(0, above) - below - 8);

  const room = Math.min(haveW / GW, haveH / GH);
  const s = room >= 1 ? Math.min(3, Math.floor(room)) : 1;
  screenCv.width = GW*s; screenCv.height = GH*s;
  // Below one whole pixel a tile, and whenever the whole coast still will not
  // fit, let the browser scale the picture down. Seeing all of it matters
  // more than seeing it crisply: the point of this coast is who else is on it.
  const shown = Math.min(room, s);
  screenCv.style.width = Math.floor(GW*shown) + 'px';
  screenCv.style.height = Math.floor(GH*shown) + 'px';
  sg.imageSmoothingEnabled = false;
}
addEventListener('resize', fit);

// ---------------------------------------------------------------------------
// 2. FIFTEEN BITS
// ---------------------------------------------------------------------------
// Five bits a channel is what the hardware stored, so a colour that is not a
// multiple of eight could not have existed. Everything goes through q() once.
const q = hex => {
  const n = parseInt(hex.slice(1), 16);
  return '#' + ((1<<24) | ((n>>16&255)&0xF8)<<16 | ((n>>8&255)&0xF8)<<8
    | (n&255&0xF8)).toString(16).slice(1);
};
const shade = (hex, f) => {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n>>16&255),(n>>8&255),(n&255)]
    .map(v => Math.max(0, Math.min(255, Math.round(v*f))) & 0xF8);
  return '#' + ((1<<24)|(c[0]<<16)|(c[1]<<8)|c[2]).toString(16).slice(1);
};

const WATER=0, SHALLOW=1, SAND=2, GRASS=3, ROCK=4, REED=5, TREE=6;
// Three tones a surface: the flat, the dither, and the edge. Which is what a
// texture artist of the period was given, and enough.
const GROUND = {};
for(const [k,[a,b,c]] of Object.entries({
  0:['#1c4058','#143048','#2c5068'],
  1:['#2c6880','#245870','#387890'],
  2:['#c8b080','#b8a070','#d8c090'],
  3:['#4a6033','#3a5028','#5a7040'],
  4:['#807870','#686058','#989088'],
  5:['#2c6068','#245058','#387078'],
  6:['#3a5028','#2c4020','#48602f'],
})) GROUND[k] = {flat:q(a), dark:q(b), lit:q(c)};

/* The shallows uncovered: wet sand, darker and greener than the dry beach
   above it, so low water is something you can see rather than a word. */
const FLATS = {flat:q('#9c8f68'), dark:q('#8c8058'), lit:q('#b0a078')};

const P = {};
for(const [k,v] of Object.entries({
  ink:'#080a08', ink2:'#141a14', night:'#1c241c',
  bone:'#e8e4d0', parch:'#c8c0a0', dusk:'#7a8a78',
  ember:'#f09028', ember2:'#f8d868', emberlo:'#c04818', emberdk:'#78280c',
  skin:'#c89060', rod:'#9a7a4a', line:'#e8e4d0', bob:'#e85038',
  gold:'#e8c878', danger:'#d84028', reedgreen:'#7a9850', reedhead:'#a09040',
})) P[k] = q(v);

const BAYER = [[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]];

// ---------------------------------------------------------------------------
// Sound, synthesised rather than fetched. Frequency, where it slides to,
// seconds, waveform, volume.
const SOUNDS = {
  plop:    [420, 180, 0.10, 'sine',     0.10],
  bite:    [340, 520, 0.16, 'triangle', 0.24],
  landed:  [520, 780, 0.16, 'sine',     0.15],
  newkind: [660, 990, 0.30, 'triangle', 0.18],
  theirs:  [480, 620, 0.12, 'sine',     0.08],
  lost:    [300, 150, 0.22, 'sine',     0.09],
  said:    [700, 700, 0.05, 'sine',     0.06],
  // A fire is a lot of small dry noises. One short band of noise, pitched
  // low, repeated irregularly, is near enough at this volume.
  crackle: [900, 380, 0.05, 'sawtooth', 0.05],
  ready:   [440, 880, 0.34, 'triangle', 0.17],
};
let audio = null, muted = false;
try { muted = localStorage.getItem('longshore-muted') === '1'; } catch(e){}
function note(name, delay){
  if(muted || !SOUNDS[name]) return;
  if(!audio){ try{ audio = new (window.AudioContext||window.webkitAudioContext)(); }
              catch(e){ return; } }
  if(audio.state === 'suspended') audio.resume();
  const [from, to, dur, shape, vol] = SOUNDS[name];
  const t = audio.currentTime + (delay||0);
  const osc = audio.createOscillator(), gain = audio.createGain();
  osc.type = shape;
  osc.frequency.setValueAtTime(from, t);
  osc.frequency.exponentialRampToValueAtTime(Math.max(20,to), t + dur);
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(vol, t + 0.008);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(gain); gain.connect(audio.destination);
  osc.start(t); osc.stop(t + dur + 0.02);
}
const seatColour = i => [q('#e8b048'),q('#68a8d8'),q('#d878a0'),q('#78c888'),
                         q('#b088d8'),q('#d89058')][i % 6];

// ---------------------------------------------------------------------------
// 3. THE GROUND, ONCE
// ---------------------------------------------------------------------------
// The coast never changes, so it is painted into its own canvas the first time
// and then blitted whole. Redrawing two and a half thousand tiles sixty times
// a second to animate one float is how a battery dies.
const seenCatches = new Set();
let coast = null, coastSeed = '';
function paintCoast(w, low){
  if(coast && coastSeed === w.seed + (low ? ':low' : ':high')) return coast;
  coast = document.createElement('canvas');
  coast.width = w.w*TILE; coast.height = w.h*TILE;
  const t = coast.getContext('2d'); t.imageSmoothingEnabled = false;
  const at = (x,y) => (x<0||y<0||x>=w.w||y>=w.h) ? WATER : w.tiles[y].charCodeAt(x)-48;
  for(let y = 0; y < w.h; y++) for(let x = 0; x < w.w; x++){
    const k = at(x,y);
    const G = (low && k === SHALLOW) ? FLATS : GROUND[k];
    const px = x*TILE, py = y*TILE;
    // The dither is per pixel, not per tile, so a field of one colour stops
    // being a field of one colour without anything looking noisy.
    const lean = ((x*7 + y*13) % 11 === 0) ? 6 : ((x*3 + y*5) % 4 === 0) ? 3 : 1;
    for(let j = 0; j < TILE; j++) for(let i = 0; i < TILE; i++){
      t.fillStyle = BAYER[j&3][i&3] < lean ? G.dark : G.flat;
      t.fillRect(px+i, py+j, 1, 1);
    }
    // A lit edge wherever land meets water, which is the whole lighting model
    // and still the fastest way to say where the shore is.
    // At low water the flats are ground, so the lit edge belongs at their
    // seaward side rather than where the beach used to end.
    const wet = c => c === WATER || c === REED || (c === SHALLOW && !low);
    if(!wet(k) && wet(at(x, y-1))){
      t.fillStyle = G.lit; t.fillRect(px, py, TILE, 1);
    }
    if(!wet(k) && wet(at(x-1, y))){
      t.fillStyle = G.lit; t.fillRect(px, py, 1, TILE);
    }
    if(!wet(k) && wet(at(x, y+1))){
      t.fillStyle = shade(G.flat, 0.7); t.fillRect(px, py+TILE-1, TILE, 1);
    }
  }
  // What stands up, drawn over the ground it stands on.
  for(let y = 0; y < w.h; y++) for(let x = 0; x < w.w; x++){
    const k = at(x,y), px = x*TILE, py = y*TILE;
    if(k === TREE) t.drawImage(sprites.tree[(x*5+y*3)%2], px-3, py-9);
    else if(k === ROCK) t.drawImage(sprites.rock[(x*7+y*11)%2], px, py+1);
    else if(k === REED) t.drawImage(sprites.reed[(x*3+y*7)%3], px, py-1);
  }
  coastSeed = w.seed + (low ? ':low' : ':high');
  return coast;
}

// ---------------------------------------------------------------------------
// 4. THINGS THAT STAND UP
// ---------------------------------------------------------------------------
// A hard black edge on everything. The artists could not afford antialiasing
// and it became the look; without it a sprite dissolves into the ground.
function outlined(w, h, paint){
  const c = document.createElement('canvas'); c.width = w+2; c.height = h+2;
  const t = c.getContext('2d'); t.imageSmoothingEnabled = false;
  paint(t, 1, 1);
  const src = t.getImageData(0,0,w+2,h+2), out = t.createImageData(w+2,h+2);
  out.data.set(src.data);
  const alpha = (x,y) => (x<0||y<0||x>=w+2||y>=h+2) ? 0 : src.data[(y*(w+2)+x)*4+3];
  for(let y=0;y<h+2;y++) for(let x=0;x<w+2;x++){
    if(alpha(x,y)) continue;
    if(alpha(x-1,y)||alpha(x+1,y)||alpha(x,y-1)||alpha(x,y+1)){
      const i=(y*(w+2)+x)*4;
      out.data[i]=8; out.data[i+1]=10; out.data[i+2]=8; out.data[i+3]=255;
    }
  }
  t.putImageData(out,0,0);
  return c;
}

const sprites = {};
function buildSprites(){
  sprites.tree = [0,1].map(v => outlined(22, 26, (t,ox,oy) => {
    t.fillStyle = q('#4a3520'); t.fillRect(ox+9, oy+17, 4, 9);
    t.fillStyle = q('#243c1a');
    t.beginPath(); t.ellipse(ox+11, oy+13, 11, 11-v, 0, 0, 6.2832); t.fill();
    t.fillStyle = q('#33562a');
    t.beginPath(); t.ellipse(ox+9, oy+10, 7, 7, 0, 0, 6.2832); t.fill();
    t.fillStyle = q('#4a7030');
    t.beginPath(); t.ellipse(ox+8, oy+8, 3, 3, 0, 0, 6.2832); t.fill();
  }));
  sprites.rock = [0,1].map(v => outlined(18, 15, (t,ox,oy) => {
    t.fillStyle = q('#6a6058');
    t.beginPath();
    t.moveTo(ox+1, oy+14); t.lineTo(ox+3+v, oy+4); t.lineTo(ox+10, oy+1);
    t.lineTo(ox+17, oy+7); t.lineTo(ox+15, oy+14); t.closePath(); t.fill();
    t.fillStyle = q('#989088');
    t.beginPath();
    t.moveTo(ox+4, oy+5); t.lineTo(ox+10, oy+3); t.lineTo(ox+13, oy+7);
    t.lineTo(ox+7, oy+9); t.closePath(); t.fill();
  }));
  // Short, and only on some of them. Reeds taller than their tile turn a bay
  // into a lawn standing in front of everything behind it.
  sprites.reed = [0,1,2].map(v => outlined(17, 14, (t,ox,oy) => {
    const stalks = [[[3,10],[7,13],[12,9]], [[4,11],[10,10]],
                    [[2,9],[6,13],[11,11],[14,7]]][v];
    for(const [rx,h] of stalks){
      t.fillStyle = P.reedgreen; t.fillRect(ox+rx, oy+14-h, 1, h);
      t.fillStyle = P.reedhead; t.fillRect(ox+rx-1, oy+14-h-2, 3, 3);
    }
  }));
}

// Twenty pixels on a twelve pixel tile, and overhanging it.
//
// The first pass drew people the size of the ground they stood on, and on a
// coast of two and a half thousand tiles four of them vanished into the
// scenery: the trees read and the characters did not, which is backwards for
// a game about who is on the shore. So they are larger than their tile, they
// carry a shadow to hold them down, and there is a lamp under anybody the
// others should be looking at.
const bodies = {};
function body(colour){
  if(bodies[colour]) return bodies[colour];
  bodies[colour] = outlined(16, 26, (t,ox,oy) => {
    t.fillStyle = P.ink2; t.fillRect(ox+4, oy+22, 8, 4);            // boots
    t.fillStyle = shade(colour, 0.55); t.fillRect(ox+4, oy+15, 8, 7);
    t.fillStyle = colour; t.fillRect(ox+1, oy+7, 14, 8);            // body
    t.fillStyle = shade(colour, 1.35); t.fillRect(ox+1, oy+7, 14, 2);
    t.fillStyle = shade(colour, 0.7); t.fillRect(ox+1, oy+13, 14, 2);
    t.fillStyle = P.skin; t.fillRect(ox+5, oy, 6, 7);               // head
    t.fillStyle = shade(P.skin, 1.2); t.fillRect(ox+5, oy, 6, 2);
    t.fillStyle = shade(P.skin, 0.65); t.fillRect(ox+5, oy+6, 6, 1);
  });
  return bodies[colour];
}

// A soft plate under everybody, so a figure on busy ground still has a
// silhouette. Cheap, and it does more than another two pixels of height.
function footing(px, py, colour, loud){
  const cx = px + TILE/2, cy = py + TILE - 1;
  if(loud){
    const halo = g.createRadialGradient(cx, cy-6, 1, cx, cy-6, 22);
    halo.addColorStop(0, 'rgba(232,208,120,0.30)');
    halo.addColorStop(1, 'rgba(232,208,120,0)');
    g.fillStyle = halo; g.fillRect(cx-24, cy-28, 48, 34);
  }
  g.fillStyle = 'rgba(8,10,8,0.45)';
  g.beginPath(); g.ellipse(cx, cy, 8, 3, 0, 0, 6.2832); g.fill();
}

// ---------------------------------------------------------------------------
// 5. STATE
// ---------------------------------------------------------------------------
let state = {}, prev = {}, frame = 0, moveAt = 0, floats = [], ripples = [];
const ease = t => t<0?0:t>1?1:t*t*(3-2*t);
const esc = s => (s||'').replace(/[<>&]/g, c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));

// ---------------------------------------------------------------------------
// 6. THE SCENE
// ---------------------------------------------------------------------------
function draw(){
  frame++;
  const w = state.world;
  if(!w){ requestAnimationFrame(draw); return; }
  if(fb.width !== w.w*TILE) shape(w.w, w.h);

  g.fillStyle = P.ink; g.fillRect(0, 0, GW, GH);
  g.drawImage(paintCoast(w, (state.tide||{}).out), 0, 0);

  if(state.fire) drawFire(state.fire);

  // While anything is on the fire, it crackles. Irregularly, because a fire
  // that ticked would be a metronome.
  if((state.people||[]).some(p => p.doing === 'k') && (frame % 7) === 0
     && Math.random() < 0.4) note('crackle');

  const t = ease((performance.now() - moveAt)/220);
  const was = {}; (prev.people||[]).forEach(p => was[p.id] = p);
  const bubbles = [];

  for(const p of (state.people||[])){
    const from = was[p.id] || p;
    const px = Math.round((from.x + (p.x-from.x)*t) * TILE);
    const py = Math.round((from.y + (p.y-from.y)*t) * TILE);
    if(p.doing !== '-' && p.doing !== 'k' && p.doing !== 'f' && p.float)
      drawLine(px, py, p);
    if(p.doing !== 'k') delete started[p.id];
    const bob = p.doing === '-' ? (((frame + (p.seat||0)*17) >> 5) & 1) : 0;
    const colour = seatColour(p.seat||0);
    footing(px, py, colour, p.doing === '!' || p.doing === 'k');
    g.drawImage(body(colour), px, py-11+bob);
    if(p.doing === '!'){
      const hop = ((frame>>3)&3) < 2 ? 0 : 1;
      g.fillStyle = P.ink; g.fillRect(px+3, py-24-hop, 6, 12);
      g.fillStyle = P.danger; g.fillRect(px+5, py-22-hop, 2, 7);
      g.fillRect(px+5, py-14-hop, 2, 2);
    }
    if(p.doing === 'k') cooking(px, py, p);
    plate(px+TILE/2, py-12, p.name, colour);
    if(p.said) bubbles.push({x: px+TILE/2, y: py-24, text: p.said});
  }

  drawRipples();
  drawBubbles(bubbles);
  drawFloats();
  drawChrome();

  sg.drawImage(fb, 0, 0, GW, GH, 0, 0, screenCv.width, screenCv.height);
  requestAnimationFrame(draw);
}

function drawLine(px, py, p){
  const fx = p.float[0]*TILE + TILE/2, fy = p.float[1]*TILE + TILE/2;
  g.strokeStyle = P.rod; g.lineWidth = 1;
  g.beginPath(); g.moveTo(px+9, py+2); g.lineTo(px+13, py-4); g.stroke();
  g.strokeStyle = P.line;
  g.beginPath();
  g.moveTo(px+13, py-4);
  g.quadraticCurveTo((px+fx)/2, Math.min(py,fy)-14, fx, fy);
  g.stroke();
  const biting = p.doing === '!';
  if(biting && (frame & 7) === 0) ripples.push({x:fx, y:fy, at:frame});
  g.fillStyle = biting ? P.bob : P.line;
  const jerk = biting ? ((frame>>2)&1) : 0;
  g.fillRect(fx-1, fy-1+jerk, 3, 3);
  g.fillStyle = P.ink;
  g.fillRect(fx-1, fy+2+jerk, 3, 1);
}

// Twenty-five seconds of standing still needs something to watch, or it is
// the worst thing in the game rather than the quiet part of it.
//
// Your own ring is exact, because the node tells you how long is left. For
// everybody else it is counted from the moment their heartbeat first said
// they were cooking, which is a second or two out and nobody will ever know.
const started = {};
function cooking(px, py, p){
  let done;
  if(p.me && p.span){ done = 1 - (p.until / p.span); }
  else {
    if(!started[p.id]) started[p.id] = performance.now();
    done = Math.min(1, (performance.now() - started[p.id]) / 25000);
  }
  const cx = px + TILE/2, cy = py - 26;
  g.strokeStyle = P.emberdk; g.lineWidth = 2;
  g.beginPath(); g.arc(cx, cy, 9, 0, 6.2832); g.stroke();
  g.strokeStyle = done > 0.92 ? P.ember2 : P.ember;
  g.beginPath(); g.arc(cx, cy, 9, -Math.PI/2, -Math.PI/2 + 6.2832*done); g.stroke();

  // The fish, browning. It is a few pixels and it is the whole reason to
  // stand here rather than a number going up somewhere.
  const cook = done;
  const body = cook > 0.75 ? q('#a86038') : cook > 0.4 ? q('#c08048') : q('#b8b0a0');
  g.fillStyle = body;
  g.fillRect(cx-4, cy-2, 7, 4);
  g.fillStyle = P.ink; g.fillRect(cx+3, cy-2, 2, 4);     // tail
  g.fillStyle = shade(body, 1.3); g.fillRect(cx-4, cy-2, 7, 1);
  if(cook > 0.55 && (frame & 15) < 8){                   // a wisp off it
    g.fillStyle = 'rgba(200,200,190,0.35)';
    g.fillRect(cx - 1 + ((frame>>3)&1), cy - 7 - ((frame>>2)&3), 1, 2);
  }
}

function drawRipples(){
  ripples = ripples.filter(r => frame - r.at < 40);
  for(const r of ripples){
    const age = (frame - r.at)/40;
    g.strokeStyle = 'rgba(200,216,208,' + (0.55*(1-age)) + ')';
    g.lineWidth = 1;
    g.beginPath(); g.arc(r.x, r.y, 2 + age*9, 0, 6.2832); g.stroke();
  }
}

function drawFire(fire){
  const px = fire.x*TILE + TILE/2, py = fire.y*TILE + TILE - 1;
  g.fillStyle = q('#5a544c');
  for(const [dx,dy] of [[-6,0],[-2,2],[3,2],[6,0],[-4,-3],[5,-3]])
    g.fillRect(px+dx-1, py+dy-2, 3, 2);
  g.fillStyle = q('#4a3520');
  g.fillRect(px-5, py-5, 10, 2); g.fillRect(px-2, py-7, 8, 2);
  if(!fire.lit) return;
  // Widest at the bottom, shortest at the edges, or it does not read as a
  // flame. How big depends on how many are round it, and on nothing else:
  // it is lit because people are there and out because they are not.
  const size = Math.max(1, Math.min(3, fire.round_it));
  const tall = 6 + size*3, tick = frame * 0.14;
  g.fillStyle = P.emberdk; g.fillRect(px-4, py-8, 9, 2);
  for(let col = -2; col <= 2; col++){
    const edge = 1 - Math.abs(col)/2.6;
    const flap = 0.7 + 0.3*Math.sin(tick + col*0.9);
    const h = Math.max(2, Math.round(tall*edge*flap));
    for(let j = 0; j < h; j++){
      const up = j/h;
      g.fillStyle = up > 0.7 ? P.ember2 : up > 0.32 ? P.ember : P.emberlo;
      g.fillRect(px + col*2 - 1, py - 8 - j, 2, 1);
    }
  }
  const glow = g.createRadialGradient(px, py-6, 2, px, py-6, 26 + size*10);
  glow.addColorStop(0, 'rgba(240,144,40,0.18)');
  glow.addColorStop(1, 'rgba(240,144,40,0)');
  g.fillStyle = glow; g.fillRect(px-60, py-56, 120, 90);
}

// A name on a dark plate rather than loose on the ground. An outline alone
// disappears against grass and reeds, which is exactly where people stand.
function plate(px, py, text, colour){
  if(!text) return;
  g.font = '8px ui-monospace,monospace'; g.textAlign = 'center';
  const wide = g.measureText(text).width + 5;
  g.fillStyle = 'rgba(8,10,8,0.78)';
  g.fillRect(px - wide/2, py - 7, wide, 9);
  g.fillStyle = colour; g.fillText(text, px, py);
}

function drawBubbles(list){
  // Raised until they stop overlapping. Two people fishing side by side put
  // their speech in the same place, and both became unreadable.
  g.font = '8px ui-monospace,monospace'; g.textAlign = 'center';
  const placed = [];
  for(const b of list){
    const words = b.text.length > 28 ? b.text.slice(0,27) + '\u2026' : b.text;
    const wide = g.measureText(words).width + 6;
    let bx = b.x - wide/2, by = b.y;
    for(let guard = 0; guard < 8; guard++){
      const clash = placed.some(o => bx < o.x+o.w+2 && bx+wide+2 > o.x
                                  && by < o.y+11 && by+11 > o.y);
      if(!clash) break;
      by -= 13;
    }
    placed.push({x:bx, y:by, w:wide});
    g.fillStyle = P.ink; g.fillRect(bx-1, by-1, wide+2, 12);
    g.fillStyle = q('#20281e'); g.fillRect(bx, by, wide, 10);
    if(by === b.y){ g.fillStyle = P.ink; g.fillRect(b.x-1, by+10, 3, 2); }
    g.fillStyle = P.bone; g.fillText(words, bx+wide/2, by+8);
  }
}

function drawFloats(){
  floats = floats.filter(f => frame - f.at < 120);
  g.font = '8px ui-monospace,monospace'; g.textAlign = 'center';
  for(const f of floats){
    const age = (frame - f.at)/120;
    const px = f.x*TILE + TILE/2, py = f.y*TILE - 12 - age*14;
    g.globalAlpha = 1 - age*age;
    g.fillStyle = P.ink;
    for(const [dx,dy] of [[-1,0],[1,0],[0,-1],[0,1]]) g.fillText(f.text, px+dx, py+dy);
    g.fillStyle = f.gold ? P.gold : P.bone;
    g.fillText(f.text, px, py);
    g.globalAlpha = 1;
  }
}

// ---------------------------------------------------------------------------
// 7. THE CHROME
// ---------------------------------------------------------------------------
function drawChrome(){
  const top = GH - CHROME, me = state.me || {};
  g.fillStyle = P.ink; g.fillRect(0, top, GW, CHROME);
  g.fillStyle = P.ink2; g.fillRect(0, top, GW, 1);
  g.font = '8px ui-monospace,monospace'; g.textAlign = 'left';

  /* The tide beside the hour, because on a shore they are the same fact. */
  const tideNow = (state.tide||{}).state;
  g.fillStyle = P.dusk;
  g.fillText((state.status || '') + (tideNow ? '  \u00b7  tide ' + tideNow : ''),
             6, top+12);
  if(me.pool){ g.fillStyle = P.parch;
    g.fillText('the ' + me.pool, 6, top+23); }
  if(me.wood){ g.fillStyle = P.parch;
    g.fillText(me.wood + ' driftwood', 6, top+34); }
  else if(me.at_fire){ g.fillStyle = P.ember;
    g.fillText('F for the fire', 6, top+34); }

  // Yours and nobody else's, which is why it is down here and not over
  // anybody's head.
  g.textAlign = 'right';
  g.fillStyle = P.gold; g.fillText('FISHING ' + (me.level || 1), GW-6, top+12);
  g.fillStyle = P.ink2; g.fillRect(GW-86, top+16, 80, 3);
  g.fillStyle = P.gold;
  g.fillRect(GW-86, top+16, Math.round(80*(me.needs ? (me.into||0)/me.needs : 0)), 3);
  g.fillStyle = P.dusk;
  g.fillText((me.kinds||0) + ' kinds \u00b7 ' + (me.caught||0) + ' caught', GW-6, top+31);

  g.textAlign = 'left';
  const lines = (state.log||[]).slice(-3);
  lines.forEach((l, i) => {
    g.fillStyle = l.role === 'gold' ? P.gold : P.dusk;
    g.fillText(l.text.slice(0, 64), 150, top+12 + i*11);
  });
}

// ---------------------------------------------------------------------------
// 8. INTENT
// ---------------------------------------------------------------------------
const send = o => fetch('/', {method:'POST',
  body: JSON.stringify(Object.assign({panel:'longshore'}, o))});

screenCv.onclick = ev => {
  if(!state.world) return;
  const box = screenCv.getBoundingClientRect();
  const px = (ev.clientX - box.left) * GW / box.width;
  const py = (ev.clientY - box.top) * GH / box.height;
  if(py > GH - CHROME) return;
  if(state.me && state.me.doing === '!') return send({do:'strike'});
  send({do:'tap', x: Math.floor(px/TILE), y: Math.floor(py/TILE)});
};

addEventListener('keydown', e => {
  if(document.activeElement.tagName === 'INPUT') return;
  const mv = {ArrowLeft:'w',ArrowRight:'e',ArrowUp:'n',ArrowDown:'s',
              h:'w',l:'e',k:'n',j:'s'};
  if(mv[e.key]){ e.preventDefault(); return send({do:'step', dir:mv[e.key]}); }
  if(e.key === ' '){ e.preventDefault();
    return send({do: state.me && state.me.doing === '!' ? 'strike' : 'cast'}); }
  if(e.key === 'f' || e.key === 'F') return send({do:'cook'});
});

document.getElementById('say').onsubmit = e => {
  e.preventDefault();
  const box = document.getElementById('text');
  if(box.value.trim()) send({do:'say', text:box.value.trim()});
  box.value = ''; box.blur();
};

buildSprites();
new EventSource('/events').onmessage = m => {
  const all = JSON.parse(m.data);
  const next = all.longshore || all;
  const moved = JSON.stringify((next.people||[]).map(p=>[p.x,p.y]))
             !== JSON.stringify((state.people||[]).map(p=>[p.x,p.y]));
  const was = state.me || {}, now2 = next.me || {};
  if(now2.doing !== was.doing){
    if(now2.doing === 'c') note('plop');
    if(now2.doing === '!') note('bite');
    if(was.doing === '!' && now2.doing === '-') note('lost');
    if(was.doing === 'k' && now2.doing !== 'k') note('ready');
  }
  if((now2.kinds||0) > (was.kinds||0)) note('newkind');
  else if((now2.caught||0) > (was.caught||0)) note('landed');
  const mine = (next.people||[]).find(p => p.me) || {};
  (next.caught||[]).forEach(c => {
    // A catch lingers for three seconds so everybody sees it, and a snapshot
    // arrives about every second, so without this the name was drawn three
    // times over one fish.
    if(c.id !== undefined && seenCatches.has(c.id)) return;
    if(c.id !== undefined) seenCatches.add(c.id);
    if(!(c.x === mine.x && c.y === mine.y)) note('theirs');
    floats.push({text: c.name + ' ' + c.cm, x: c.x, y: c.y, at: frame,
                 gold: c.rarity === 'rare'});
    ripples.push({x: c.x*TILE+TILE/2, y: c.y*TILE+TILE/2, at: frame});
  });
  prev = state; state = next;
  if(moved) moveAt = performance.now();
};
draw();
</script></body></html>
"""
