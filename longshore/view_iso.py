"""longshore, as a handheld would have drawn it.

Everything here is one 288x180 framebuffer, blitted once at the end with
nearest neighbour. Nothing else scales. That is the whole discipline of the
look: a sprite drawn at one and a half pixels is wrong, so nothing is ever
allowed to be one.

No WebGL. The aesthetic is constraint rather than capability, and at thirty
thousand pixels a 2D context has nothing to apologise for. What does the work
is the fifteen-bit palette, the 2:1 diamond, three tones a surface, and a hard
black edge on everything that stands up.

The one thing isometric costs is the overview. A coast is sixty-four by
thirty-six, which at any diamond that reads as relief is far wider than a
handheld screen, so the camera has to follow you. Seeing everybody at a glance
is most of why anybody is on that shore, so the whole coast is drawn small
along the bottom and never scrolls.
"""

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>longshore</title>
<style>
html,body{margin:0;padding:0;height:100%;background:#000;overflow:hidden;
  font-family:ui-monospace,Menlo,Consolas,monospace;-webkit-user-select:none;
  user-select:none;touch-action:manipulation}
#shell{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;
  background:radial-gradient(120% 100% at 50% 0%,#0e1410 0%,#000 78%)}
#panel{position:relative;image-rendering:pixelated;
  box-shadow:0 0 0 2px #060806,0 0 0 6px #141a14,0 0 40px 6px rgba(90,160,110,.05)}
canvas{display:block;image-rendering:pixelated}
#hint{position:fixed;left:0;right:0;bottom:5px;text-align:center;color:#3d4a3d;
  font:10px ui-monospace,monospace;letter-spacing:.12em;pointer-events:none}
#say{position:fixed;left:50%;transform:translateX(-50%);bottom:22px;display:flex;gap:6px;
  width:min(90vw,420px)}
#say input{flex:1;background:#0d120e;border:1px solid #263026;color:#cfd8c8;
  font:12px ui-monospace,monospace;padding:6px 8px;border-radius:2px;min-width:0}
#say button{background:#1a231a;border:1px solid #263026;color:#cfd8c8;
  font:12px ui-monospace,monospace;padding:6px 10px;border-radius:2px;cursor:pointer}
</style></head><body>
<div id="shell"><div id="panel"><canvas id="screen"></canvas></div></div>
<form id="say"><input id="text" maxlength="120" placeholder="say something"><button>say</button></form>
<div id="hint">TAP WATER TO FISH &middot; TAP AGAIN TO STRIKE &middot; F THE FIRE &middot; ARROWS WALK</div>
<script>
'use strict';

// ---------------------------------------------------------------------------
// 1. THE PANEL
// ---------------------------------------------------------------------------
// One framebuffer, one blit. Nothing in the rest of this file knows about
// device pixels.
const GW = 288, GH = 192;
const STRIP = 44;               // the whole coast is thirty-six rows tall
const fb = document.createElement('canvas'); fb.width = GW; fb.height = GH;
const g = fb.getContext('2d', {alpha:false}); g.imageSmoothingEnabled = false;
const screenCv = document.getElementById('screen');
const sg = screenCv.getContext('2d', {alpha:false}); sg.imageSmoothingEnabled = false;

function fit(){
  const s = Math.max(1, Math.floor(Math.min(
    (innerWidth - 24) / GW, (innerHeight - 78) / GH)));
  screenCv.width = GW * s; screenCv.height = GH * s;
  sg.imageSmoothingEnabled = false;
}
addEventListener('resize', fit); fit();

// ---------------------------------------------------------------------------
// 2. FIFTEEN BITS
// ---------------------------------------------------------------------------
// Five bits a channel is what the hardware stored, so a colour that is not a
// multiple of eight could not have existed. Every colour here goes through q()
// once. It is a small constraint and it does most of the work: the slightly
// muddy, slightly too-warm cast of the era is what rounding looks like.
const q = hex => {
  const n = parseInt(hex.slice(1), 16);
  return '#' + ((1<<24) | ((n>>16&255)&0xF8)<<16 | ((n>>8&255)&0xF8)<<8 | (n&255&0xF8)
    ).toString(16).slice(1);
};
const P = {};
for(const [k,v] of Object.entries({
  ink:'#080a08', ink2:'#141a14', night:'#1c241c',
  bone:'#e8e4d0', parch:'#c8c0a0', dusk:'#6a7a68',
  ember:'#f09028', ember2:'#f8d868', emberlo:'#c04818', emberdk:'#78280c',
  skin:'#c89060', skinlo:'#906038',
  rod:'#9a7a4a', line:'#e8e4d0', bob:'#e85038', bobpale:'#e8e4d0',
  gold:'#e8c878', danger:'#d84028',
})) P[k] = q(v);

const shade = (hex, f) => {
  const n = parseInt(hex.slice(1), 16);
  const c = [(n>>16&255),(n>>8&255),(n&255)]
    .map(v => Math.max(0, Math.min(255, Math.round(v*f))) & 0xF8);
  return '#' + ((1<<24)|(c[0]<<16)|(c[1]<<8)|c[2]).toString(16).slice(1);
};

// Three tones a surface, which is what a texture artist of the period was
// given and exactly enough to read as relief.
const WATER=0, SHALLOW=1, SAND=2, GRASS=3, ROCK=4, REED=5, TREE=6;
const GROUND = {};
for(const [k,[t,s]] of Object.entries({
  0:['#1c4058','#0c2030'],   // open water
  1:['#2c6880','#184050'],   // shallows
  2:['#c8b080','#907048'],   // sand
  3:['#4a6033','#2c3a1e'],   // grass
  4:['#807870','#484440'],   // rock
  5:['#2c6068','#18383c'],   // reeds stand in water
  6:['#3a5028','#20301a'],   // the ground under a tree
})) GROUND[k] = {top:q(t), side:q(s)};

// Relief. Water sits below the sand, rock stands over it, and that difference
// is what turns a map into a place.
const ELEV = {0:-5, 1:-2, 2:0, 3:2, 4:5, 5:-2, 6:2};

const BAYER = [[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]];

// ---------------------------------------------------------------------------
// 3. THE PROJECTION
// ---------------------------------------------------------------------------
// 24 by 12. A 2:1 diamond is the only ratio whose edges land exactly on the
// pixel grid, and the camera is floored before anything is placed, so walking
// is a slide of whole pixels and the world never shimmers.
const TW = 24, TH = 12, LIP = 10;
const isoX = (x,y) => (x-y)*(TW/2);
const isoY = (x,y) => (x+y)*(TH/2);
let camX = 0, camY = 0, camReady = false;
const sx = (x,y) => Math.floor(isoX(x,y) - camX);
const sy = (x,y,e=0) => Math.floor(isoY(x,y) - camY - e);

function tileAt(px, py){
  const a = (px + camX) / (TW/2), b = (py + camY + TH/2) / (TH/2);
  return {x: Math.floor((b+a)/2), y: Math.floor((b-a)/2)};
}

// ---------------------------------------------------------------------------
// 4. THE GROUND
// ---------------------------------------------------------------------------
// One block per terrain per variant, drawn once into its own little canvas and
// never computed again. The top is a 2:1 diamond; below it the two visible
// faces of the cut earth, south-west lit and south-east in shadow, which is
// the whole of the era's lighting model.
const blocks = new Map();
function block(kind, v){
  const key = kind + ':' + v;
  const had = blocks.get(key); if(had) return had;
  const G = GROUND[kind] || GROUND[2];
  const c = document.createElement('canvas');
  c.width = TW; c.height = TH + LIP;
  const t = c.getContext('2d'); t.imageSmoothingEnabled = false;
  const bottom = new Int16Array(TW).fill(-1);
  for(let j = 0; j < TH; j++){
    const k = j < TH/2 ? j : TH-1-j;
    const x0 = (TW/2 - 2) - 2*k, w = 4 + 4*k;
    for(let i = 0; i < w; i++){
      const X = x0 + i;
      t.fillStyle = (BAYER[j&3][X&3] < (v===2 ? 5 : v===1 ? 2 : 0))
        ? shade(G.top, 0.88) : G.top;
      t.fillRect(X, j, 1, 1);
      bottom[X] = j;
    }
  }
  for(let X = 0; X < TW; X++){
    if(bottom[X] < 0) continue;
    const lit = X < TW/2;
    t.fillStyle = lit ? G.side : shade(G.side, 0.78);
    t.fillRect(X, bottom[X]+1, 1, LIP);
  }
  blocks.set(key, c);
  return c;
}

// ---------------------------------------------------------------------------
// 5. THINGS THAT STAND UP
// ---------------------------------------------------------------------------
// Everything here has a hard black edge. The artists could not afford
// antialiasing and it became the look; without it a sprite dissolves into the
// ground it is standing on.
function outlined(w, h, paint){
  const c = document.createElement('canvas'); c.width = w+2; c.height = h+2;
  const t = c.getContext('2d'); t.imageSmoothingEnabled = false;
  paint(t, 1, 1);
  const src = t.getImageData(0,0,w+2,h+2), out = t.createImageData(w+2,h+2);
  out.data.set(src.data);
  const at = (x,y) => (x<0||y<0||x>=w+2||y>=h+2) ? 0 : src.data[(y*(w+2)+x)*4+3];
  for(let y=0;y<h+2;y++) for(let x=0;x<w+2;x++){
    if(at(x,y)) continue;
    if(at(x-1,y)||at(x+1,y)||at(x,y-1)||at(x,y+1)){
      const i=(y*(w+2)+x)*4;
      out.data[i]=8; out.data[i+1]=10; out.data[i+2]=8; out.data[i+3]=255;
    }
  }
  t.putImageData(out,0,0);
  return c;
}

const sprites = {};
function buildSprites(){
  sprites.tree = outlined(20, 26, (t,ox,oy) => {
    t.fillStyle = q('#4a3520'); t.fillRect(ox+8, oy+16, 4, 10);
    t.fillStyle = q('#2c4420'); t.beginPath();
    t.ellipse(ox+10, oy+12, 10, 11, 0, 0, 6.2832); t.fill();
    t.fillStyle = q('#3a5c28'); t.beginPath();
    t.ellipse(ox+8, oy+10, 7, 7, 0, 0, 6.2832); t.fill();
    t.fillStyle = q('#4a7030'); t.beginPath();
    t.ellipse(ox+7, oy+7, 4, 4, 0, 0, 6.2832); t.fill();
  });
  sprites.rock = outlined(18, 14, (t,ox,oy) => {
    t.fillStyle = q('#6a6058'); t.beginPath();
    t.moveTo(ox+1,oy+13); t.lineTo(ox+4,oy+4); t.lineTo(ox+11,oy+1);
    t.lineTo(ox+17,oy+7); t.lineTo(ox+16,oy+13); t.closePath(); t.fill();
    t.fillStyle = q('#908880'); t.beginPath();
    t.moveTo(ox+4,oy+5); t.lineTo(ox+11,oy+2); t.lineTo(ox+13,oy+6);
    t.lineTo(ox+6,oy+8); t.closePath(); t.fill();
  });
  // Short. The first pass drew them fifteen pixels tall on a twelve pixel
  // tile, on every reed square, and a bay of them came out as a lawn standing
  // in front of everything behind it.
  sprites.reed = [0,1,2].map(v => outlined(14, 8, (t,ox,oy) => {
    t.strokeStyle = q('#5a7840'); t.lineWidth = 1;
    const stalks = [[[2,6],[6,8],[10,5]], [[4,7],[8,6]], [[3,5],[7,8],[11,6],[1,4]]][v];
    for(const [rx,h] of stalks){
      t.beginPath(); t.moveTo(ox+rx+0.5, oy+8); t.lineTo(ox+rx+0.5, oy+8-h); t.stroke();
      t.fillStyle = q('#8a9850'); t.fillRect(ox+rx-1, oy+8-h-1, 3, 2);
    }
  }));
}

// A person, drawn at a fixed size and facing whichever way the work is. Three
// tones and an edge, which is all the era allowed for something two dozen
// pixels tall.
function person(t, px, py, colour, doing, frame){
  const bob = (doing === '-' ? Math.sin(frame/22)*0.5 : 0) | 0;
  const c = outlined(10, 18, (q2,ox,oy) => {
    q2.fillStyle = P.ink2; q2.fillRect(ox+2, oy+15, 6, 3);         // boots
    q2.fillStyle = shade(colour, 0.62); q2.fillRect(ox+2, oy+9, 6, 6);  // legs
    q2.fillStyle = colour; q2.fillRect(ox+1, oy+4, 8, 6);          // body
    q2.fillStyle = shade(colour, 1.25); q2.fillRect(ox+1, oy+4, 8, 2);
    q2.fillStyle = P.skin; q2.fillRect(ox+3, oy, 4, 4);            // head
    q2.fillStyle = P.skinlo; q2.fillRect(ox+3, oy+3, 4, 1);
  });
  t.drawImage(c, px-6, py-20+bob);
}

// ---------------------------------------------------------------------------
// 6. STATE
// ---------------------------------------------------------------------------
let state = {}, frame = 0, flames = [], splashes = [], floats = [];
const seatColour = i => [q('#e8b048'),q('#68a8d8'),q('#d878a0'),q('#78c888'),
                         q('#b088d8'),q('#d89058')][i % 6];

function tileOf(w, x, y){
  if(x<0||y<0||x>=w.w||y>=w.h) return WATER;
  return w.tiles[y].charCodeAt(x) - 48;
}

// ---------------------------------------------------------------------------
// 7. THE SCENE
// ---------------------------------------------------------------------------
function draw(){
  frame++;
  const w = state.world;
  if(!w){ requestAnimationFrame(draw); return; }
  const me = (state.people||[]).find(p => p.me) || {x:0, y:0};

  // The camera is floored and eased, so it slides in whole pixels.
  const wantX = isoX(me.x, me.y) - GW/2 + TW/2;
  const wantY = isoY(me.x, me.y) - (GH-STRIP)/2;
  if(!camReady){ camX = wantX; camY = wantY; camReady = true; }
  else { camX += (wantX-camX)*0.14; camY += (wantY-camY)*0.14; }
  camX = Math.round(camX); camY = Math.round(camY);

  g.fillStyle = P.ink; g.fillRect(0,0,GW,GH);

  // Only what could possibly be on screen. A coast is two and a half thousand
  // tiles and all but a hundred of them are somewhere else.
  const here = tileAt(GW/2, (GH-STRIP)/2);
  const span = 14;
  const people = {}; (state.people||[]).forEach(p => {
    (people[p.y*1000+p.x] = people[p.y*1000+p.x] || []).push(p);
  });
  const fire = state.fire;

  const order = [];
  for(let y = here.y-span; y <= here.y+span; y++)
    for(let x = here.x-span; x <= here.x+span; x++){
      if(x<0||y<0||x>=w.w||y>=w.h) continue;
      order.push([x,y]);
    }
  // Painter's algorithm: further away is drawn first, and on a 2:1 diamond
  // "further" is simply a smaller x plus y.
  order.sort((a,b) => (a[0]+a[1]) - (b[0]+b[1]) || a[1]-b[1]);

  for(const [x,y] of order){
    const kind = tileOf(w, x, y);
    const e = ELEV[kind] || 0;
    const px = sx(x,y), py = sy(x,y,e);
    if(px < -TW || px > GW+TW || py < -40 || py > GH+40) continue;
    const v = ((x*7 + y*13) % 9 === 0) ? 2 : ((x*3 + y*5) % 4 === 0) ? 1 : 0;
    g.drawImage(block(kind===TREE?6:kind, v), px - TW/2, py);

    // Anything standing on this tile, in the same pass, so it is occluded by
    // whatever is drawn after it.
    if(kind === TREE) g.drawImage(sprites.tree, px-11, py-24);
    else if(kind === ROCK) g.drawImage(sprites.rock, px-10, py-9);
    else if(kind === REED && (x*5+y*11) % 3 !== 2)
      g.drawImage(sprites.reed[(x*7+y*3) % 3], px-8, py-6);

    if(fire && fire.x === x && fire.y === y) drawFire(px, py, fire);

    for(const p of (people[y*1000+x] || [])) drawPerson(px, py, e, p, w);
  }

  drawEffects();
  drawStrip(w, me);
  drawChrome();

  sg.drawImage(fb, 0, 0, GW, GH, 0, 0, screenCv.width, screenCv.height);
  requestAnimationFrame(draw);
}

function drawPerson(px, py, e, p, w){
  const colour = seatColour(p.seat || 0);
  // A line, going out over whatever water is in front of them.
  if(p.doing !== '-' && p.doing !== 'k' && p.doing !== 'f' && p.float){
    const fx = sx(p.float[0], p.float[1]);
    const fy = sy(p.float[0], p.float[1], ELEV[tileOf(w, p.float[0], p.float[1])] || 0);
    g.strokeStyle = P.line; g.lineWidth = 1;
    g.beginPath();
    g.moveTo(px+5, py-19);
    g.quadraticCurveTo((px+fx)/2, Math.min(py,fy)-26, fx, fy+2);
    g.stroke();
    const biting = p.doing === '!';
    if(biting){
      for(const r of [4,8]){
        g.strokeStyle = 'rgba(200,216,208,' + (0.5 - r*0.04) + ')';
        g.beginPath(); g.ellipse(fx, fy+2, r*1.6, r*0.8, 0, 0, 6.2832); g.stroke();
      }
    }
    g.fillStyle = biting ? P.bob : P.bobpale;
    const jerk = biting ? ((frame>>2)&1) : 0;
    g.fillRect(fx-1, fy+1+jerk, 3, 2);
    g.strokeStyle = P.rod; g.lineWidth = 1;
    g.beginPath(); g.moveTo(px+2, py-14); g.lineTo(px+6, py-21); g.stroke();
  }
  person(g, px, py, colour, p.doing, frame + (p.seat||0)*40);

  // A bite is worth looking up for, which is the only reason anything blinks.
  if(p.doing === '!'){
    const hop = ((frame>>2)&3) < 2 ? 0 : 1;
    g.fillStyle = P.ink; g.fillRect(px-2, py-34-hop, 4, 9);
    g.fillStyle = P.danger; g.fillRect(px-1, py-33-hop, 2, 5);
    g.fillRect(px-1, py-27-hop, 2, 2);
  }
  if(p.name) label(px, py-24, p.name, colour);
  if(p.said) bubble(px, py-36, p.said);
}

function drawFire(px, py, fire){
  // Stones first, then the wood, then whatever it is doing tonight.
  g.fillStyle = q('#5a544c');
  for(const [dx,dy] of [[-8,2],[-3,4],[3,4],[8,2],[-6,-1],[6,-1]])
    g.fillRect(px+dx-1, py+dy, 3, 2);
  g.fillStyle = q('#4a3520');
  g.fillRect(px-6, py-1, 12, 2); g.fillRect(px-2, py-3, 10, 2);
  if(!fire.lit) return;
  // Size from how many are round it. Nobody feeds this to keep it alive; it
  // is lit because people are there and out because they are not.
  // One flame is always drawn: a lit fire with nobody round it still burns.
  //
  // Shaped rather than stacked. The first pass drew columns up to nineteen
  // pixels on a twelve pixel tile and the fire came out as an orange post: a
  // flame has to be widest at the bottom and shortest at the edges or it does
  // not read as one.
  const size = Math.max(1, Math.min(3, fire.round_it));
  const t = frame * 0.19;
  const tall = 8 + size * 3;
  g.fillStyle = P.emberdk; g.fillRect(px-5, py-4, 10, 2);   // embers, under it
  for(let col = -3; col <= 3; col++){
    const edge = 1 - Math.abs(col) / 3.4;               // tallest in the middle
    const flap = 0.72 + 0.28 * Math.sin(t + col * 0.9);
    const h = Math.max(2, Math.round(tall * edge * flap));
    for(let j = 0; j < h; j++){
      const up = j / h;
      g.fillStyle = up > 0.72 ? P.ember2 : up > 0.34 ? P.ember : P.emberlo;
      g.fillRect(px + col*2 - 1, py - 4 - j, 2, 1);
    }
  }
  g.fillStyle = P.emberdk;
  g.fillRect(px-4, py-4, 8, 2);
  // Light on the sand around it.
  const glow = g.createRadialGradient(px, py, 2, px, py, 34 + size*8);
  glow.addColorStop(0, 'rgba(240,144,40,0.20)');
  glow.addColorStop(1, 'rgba(240,144,40,0)');
  g.fillStyle = glow; g.fillRect(px-46, py-34, 92, 60);
}

function label(px, py, text, colour){
  g.font = '8px ui-monospace,monospace'; g.textAlign = 'center';
  g.fillStyle = P.ink;
  for(const [dx,dy] of [[-1,0],[1,0],[0,-1],[0,1]]) g.fillText(text, px+dx, py+dy);
  g.fillStyle = colour; g.fillText(text, px, py);
}

function bubble(px, py, text){
  const words = text.length > 22 ? text.slice(0,21) + '\u2026' : text;
  g.font = '8px ui-monospace,monospace'; g.textAlign = 'center';
  const wide = g.measureText(words).width + 6;
  g.fillStyle = P.ink; g.fillRect(px-wide/2-1, py-9, wide+2, 11);
  g.fillStyle = q('#20281e'); g.fillRect(px-wide/2, py-8, wide, 9);
  g.fillStyle = P.ink; g.fillRect(px-1, py+1, 3, 2);
  g.fillStyle = P.bone; g.fillText(words, px, py-1);
}

function drawEffects(){
  floats = floats.filter(f => frame - f.at < 110);
  g.font = '8px ui-monospace,monospace'; g.textAlign = 'center';
  for(const f of floats){
    const age = (frame - f.at) / 110;
    const px = sx(f.x, f.y), py = sy(f.x, f.y) - 30 - age*16;
    g.globalAlpha = 1 - age*age;
    g.fillStyle = P.ink;
    for(const [dx,dy] of [[-1,0],[1,0],[0,-1],[0,1]]) g.fillText(f.text, px+dx, py+dy);
    g.fillStyle = f.gold ? P.gold : P.bone;
    g.fillText(f.text, px, py);
    g.globalAlpha = 1;
  }
}

// ---------------------------------------------------------------------------
// 8. THE WHOLE COAST, SMALL
// ---------------------------------------------------------------------------
// The one thing isometric takes away. A camera means you can no longer see who
// is on the shore, and that is most of the reason to be on it, so the whole
// map is along the bottom at one pixel a tile and never moves.
function drawStrip(w, me){
  const H = STRIP, top = GH - H;
  g.fillStyle = P.ink; g.fillRect(0, top, GW, H);
  g.fillStyle = P.ink2; g.fillRect(0, top, GW, 1);
  const ox = Math.floor((GW - w.w*2)/2), oy = top + Math.floor((H - w.h)/2);
  for(let y = 0; y < w.h; y++) for(let x = 0; x < w.w; x++){
    const k = tileOf(w, x, y);
    g.fillStyle = GROUND[k===TREE?6:k].top;
    g.fillRect(ox + x*2, oy + y, 2, 1);
  }
  if(state.fire){
    g.fillStyle = state.fire.lit ? P.ember : P.emberdk;
    g.fillRect(ox + state.fire.x*2 - 1, oy + state.fire.y - 1, 4, 3);
  }
  for(const p of (state.people||[])){
    g.fillStyle = P.ink; g.fillRect(ox + p.x*2 - 1, oy + p.y - 1, 4, 3);
    g.fillStyle = p.me ? P.bone : seatColour(p.seat||0);
    g.fillRect(ox + p.x*2, oy + p.y, 2, 1);
  }
}

// ---------------------------------------------------------------------------
// 9. THE CHROME
// ---------------------------------------------------------------------------
function drawChrome(){
  const me = state.me || {};
  g.font = '8px ui-monospace,monospace'; g.textAlign = 'left';
  g.fillStyle = P.ink; g.fillRect(0, 0, GW, 11);
  g.fillStyle = P.dusk; g.fillText(state.status || '', 4, 8);

  // Yours and nobody else's, which is why it is here and not over anybody's
  // head.
  const txt = 'FISHING ' + (me.level || 1);
  g.textAlign = 'right';
  g.fillStyle = P.gold; g.fillText(txt, GW-4, 8);
  const done = me.needs ? (me.into||0)/me.needs : 0;
  g.fillStyle = P.ink2; g.fillRect(GW-64, 9, 60, 2);
  g.fillStyle = P.gold; g.fillRect(GW-64, 9, Math.round(60*done), 2);

  g.textAlign = 'left';
  const lines = (state.log||[]).slice(-3);
  lines.forEach((l, i) => {
    g.fillStyle = l.role === 'gold' ? P.gold : P.dusk;
    g.fillText(l.text.slice(0, 46), 4, GH - STRIP - 4 - (lines.length-1-i)*9);
  });

  if(me.wood) { g.fillStyle = P.parch;
    g.fillText('driftwood ' + me.wood, 4, 20); }
  if(me.at_fire){ g.fillStyle = P.ember;
    g.fillText('F to use the fire', 4, me.wood ? 29 : 20); }
}

// ---------------------------------------------------------------------------
// 10. INTENT
// ---------------------------------------------------------------------------
const send = o => fetch('/', {method:'POST',
  body: JSON.stringify(Object.assign({panel:'longshore'}, o))});

screenCv.onclick = ev => {
  if(!state.world) return;
  const box = screenCv.getBoundingClientRect();
  const px = (ev.clientX - box.left) * GW / box.width;
  const py = (ev.clientY - box.top) * GH / box.height;
  if(py > GH - STRIP) return;                // the strip is for looking at
  if(state.me && state.me.doing === '!') return send({do:'strike'});
  const t = tileAt(px, py);
  send({do:'tap', x:t.x, y:t.y});
};

addEventListener('keydown', e => {
  if(document.activeElement.tagName === 'INPUT') return;
  const mv = {ArrowLeft:'w',ArrowRight:'e',ArrowUp:'n',ArrowDown:'s',
              a:'w',d:'e',w:'n',s:'s'};
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

const seenCatches = new Set();
buildSprites();
new EventSource('/events').onmessage = m => {
  const all = JSON.parse(m.data);
  const next = all.longshore || all;
  // A catch lingers three seconds so everybody sees it, and a snapshot
  // arrives about every second: without this the name is drawn three times.
  (next.caught||[]).forEach(c => {
    if(c.id !== undefined && seenCatches.has(c.id)) return;
    if(c.id !== undefined) seenCatches.add(c.id);
    floats.push({text: c.name + ' ' + c.cm, x: c.x, y: c.y, at: frame,
                 gold: c.rarity === 'rare'});
  });
  state = next;
};
draw();
</script></body></html>
"""
