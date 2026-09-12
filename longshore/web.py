"""The browser view.

Same arrangement as catacomms: the page is a screen and a pair of hands. It
receives snapshots over Server-Sent Events and posts back what you clicked;
nothing in it decides anything. Unlike catacomms there is no determinism to
protect, so a snapshot arriving a second late is not a fault, it is just a
second late.

Standard library only, one file, nothing fetched.
"""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class WebView:
    def __init__(self, port: int = 8080, host: str = "0.0.0.0") -> None:
        self.port, self.host = port, host
        self.inbox: "queue.Queue[str]" = queue.Queue()
        self._listeners: list = []
        self._lock = threading.Lock()
        self._latest = "{}"
        self._server = None

    def start(self) -> None:
        view = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                    pass        # a closed tab is not an error worth printing

            def do_GET(self):
                if self.path.startswith("/events"):
                    return view._stream(self)
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                view.inbox.put(self.rfile.read(length).decode("utf-8", "replace").strip())
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()

    def _stream(self, handler) -> None:
        channel: "queue.Queue[str]" = queue.Queue(maxsize=32)
        with self._lock:
            self._listeners.append(channel)
            first = self._latest
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        try:
            handler.wfile.write(f"data: {first}\n\n".encode())
            handler.wfile.flush()
            while True:
                try:
                    handler.wfile.write(f"data: {channel.get(timeout=15)}\n\n".encode())
                except queue.Empty:
                    handler.wfile.write(b": still here\n\n")
                handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with self._lock:
                if channel in self._listeners:
                    self._listeners.remove(channel)

    def publish(self, snapshot: dict) -> None:
        message = json.dumps(snapshot, separators=(",", ":"))
        with self._lock:
            if message == self._latest:
                return
            self._latest = message
            listeners = list(self._listeners)
        for channel in listeners:
            try:
                channel.put_nowait(message)
            except queue.Full:
                pass

    def drain(self) -> list:
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                return out


FLAT_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>longshore</title>
<style>
:root{--ink:#e7e3d8;--soft:#a9b0a2;--faint:#7d857a;--rule:#39423a;
      --paper:#11170f;--panel:#1a2118;--gold:#d9b25e;
      --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--mono);
     font-size:13px;-webkit-user-select:none;user-select:none}
.wrap{max-width:1000px;margin:0 auto;padding:10px;display:flex;
      flex-direction:column;gap:8px;min-height:100vh}
.bar{display:flex;justify-content:space-between;align-items:baseline;
     color:var(--faint);font-size:11px;gap:10px}
h1{font-size:14px;margin:0;font-weight:600}
h1 span{color:var(--gold)}
canvas{width:100%;height:auto;display:block;image-rendering:pixelated;
       background:var(--panel);border-radius:6px;touch-action:manipulation;
       cursor:crosshair}
.cols{display:flex;gap:10px;align-items:flex-start}
.side{width:150px;flex:none;font-size:11px;line-height:1.5}
.side h2{font-size:11px;margin:8px 0 3px;color:var(--faint);font-weight:600}
.lvl{color:var(--gold);font-size:13px;font-weight:600;letter-spacing:.01em}
.bar{height:3px;background:var(--rule);border-radius:2px;margin:3px 0 4px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--gold)}
.kind{display:flex;justify-content:space-between;gap:6px}
.kind i{font-style:normal;color:var(--faint)}
.r-common{color:#9fb39a}.r-uncommon{color:#8fc8d8}.r-scarce{color:#c8a0e0}
.r-rare{color:var(--gold)}.r-junk{color:#8a8070}
#log{flex:1;overflow-y:auto;max-height:22vh;font-size:11px;line-height:1.5;
     border-top:1px solid var(--rule);padding-top:6px}
.muted{color:var(--soft)}.gold{color:var(--gold)}
form{display:flex;gap:6px}
input{flex:1;background:var(--panel);border:1px solid var(--rule);color:var(--ink);
      font:inherit;padding:7px;border-radius:5px;min-width:0}
button{background:var(--panel);border:1px solid var(--rule);color:var(--ink);
       font:inherit;padding:7px 11px;border-radius:5px;cursor:pointer}
button:active{background:var(--rule)}
.hint{color:var(--faint);font-size:10px;text-align:center}
#mute{font:inherit;font-size:10px;padding:3px 8px;margin-right:8px;
      background:var(--panel);border:1px solid var(--rule);color:var(--soft);
      border-radius:5px;cursor:pointer}
#mute:hover{color:var(--ink)}
</style></head><body>
<div class="wrap">
  <div class="bar"><h1><span>~~~</span> longshore</h1>
    <span><button id="mute" type="button" aria-pressed="true">sound on</button>
    <span id="status"></span></span></div>
  <div class="cols">
    <canvas id="sea" width="640" height="360"></canvas>
    <div class="side" id="side"></div>
  </div>
  <div class="hint">tap the water to fish it &middot; tap the land to walk &middot; tap again to strike &middot; <b>c</b> at the fire</div>
  <div id="log"></div>
  <form id="say"><input id="text" placeholder="say something" autocomplete="off"><button>send</button></form>
</div>
<script>
/* Sound, synthesised rather than fetched, so the page stays one file.

   The bite is the one that matters. You will be looking somewhere else, which
   is rather the point of the game, and a bite lasts under three seconds.

   Each line is frequency, where it slides to, seconds, waveform, volume. */
const SOUNDS = {
  plop:     [420, 180, 0.10, 'sine',     0.11],
  bite:     [340, 520, 0.16, 'triangle', 0.24],
  landed:   [520, 780, 0.16, 'sine',     0.16],
  newkind:  [660, 990, 0.30, 'triangle', 0.18],
  theirs:   [480, 620, 0.12, 'sine',     0.09],
  lost:     [300, 150, 0.22, 'sine',     0.09],
  said:     [700, 700, 0.05, 'sine',     0.06],
};
let audio = null, muted = localStorage.getItem('longshore-muted') === '1';
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
  gain.gain.exponentialRampToValueAtTime(vol, t + 0.01);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(gain); gain.connect(audio.destination);
  osc.start(t); osc.stop(t + dur + 0.02);
}
function setMuted(on){
  muted = on;
  localStorage.setItem('longshore-muted', on ? '1' : '0');
  const b = document.getElementById('mute');
  if(b){ b.textContent = on ? 'sound off' : 'sound on'; b.setAttribute('aria-pressed', String(!on)); }
}

const T = 16;                 // screen pixels per tile
const WATER=0, SHALLOW=1, SAND=2, GRASS=3, ROCK=4, REED=5, TREE=6;
/* Reeds must read as water with things growing in it, not as a lawn. The
   first palette had them a green a shade off the grass, and a reed bed was
   indistinguishable from a field. */
const TILE = {0:'#1d4a60',1:'#367a94',2:'#d6bd8c',3:'#54743f',
              4:'#7a7469',5:'#2c6a70',6:'#2b4a26'};
const SEAT = ['#d9b25e','#7fb0d8','#d88fa8','#8fd8a0','#c8a0e0','#d8a070'];

const cv = document.getElementById('sea'), ctx = cv.getContext('2d');
let state = {}, prev = {}, moveAt = 0, ripples = [], floats = [];

function hash(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=(h*16777619)>>>0;}return h;}
function ease(t){return t<0?0:t>1?1:t*t*(3-2*t);}

/* The coast is drawn once into an offscreen canvas. It never changes, and
   redrawing two thousand tiles sixty times a second to animate one float
   would be a waste of a battery. */
let backdrop = null, backdropSeed = '';
function paintCoast(w){
  if(backdrop && backdropSeed === w.seed) return backdrop;
  backdrop = document.createElement('canvas');
  backdrop.width = w.w * T; backdrop.height = w.h * T;
  const g = backdrop.getContext('2d');
  for(let y=0;y<w.h;y++) for(let x=0;x<w.w;x++){
    const t = w.tiles[y].charCodeAt(x) - 48, px = x*T, py = y*T, v = hash(x+','+y);
    g.fillStyle = TILE[t]; g.fillRect(px,py,T,T);
    // a little grain, so a field of one colour is not a field of one colour
    g.fillStyle = (v%5===0) ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.04)';
    g.fillRect(px,py,T,T);
    if(t===REED){
      g.strokeStyle='#7fae72'; g.lineWidth=1;
      for(let k=0;k<3;k++){
        const rx = px + 3 + ((v>>(k*3))%3)*4;
        g.beginPath(); g.moveTo(rx+0.5, py+T); g.lineTo(rx+0.5, py+3); g.stroke();
      }
    }
    if(t===TREE){
      g.fillStyle='#4a3a28'; g.fillRect(px+T/2-1, py+T-5, 2, 5);
      g.fillStyle='#3f6b36';
      g.beginPath(); g.arc(px+T/2, py+T/2-1, T*0.38, 0, 6.2832); g.fill();
    }
    if(t===ROCK){
      g.fillStyle='#8a857c';
      g.beginPath(); g.ellipse(px+T/2, py+T/2+1, T*0.34, T*0.28, 0, 0, 6.2832); g.fill();
    }
  }
  backdropSeed = w.seed;
  return backdrop;
}

function fire(g, f, t){
  const px = f.x*T, py = f.y*T;
  // The stones are always there. The flame is there when people are.
  g.fillStyle = '#6b645a';
  for(let i=0;i<6;i++){
    const a = i/6*6.2832;
    g.beginPath();
    g.ellipse(px+T/2+Math.cos(a)*6.5, py+T/2+Math.sin(a)*4.5+2, 2.6, 2, 0, 0, 6.2832);
    g.fill();
  }
  if(!f.lit){
    g.fillStyle = '#2b2723';
    g.beginPath(); g.ellipse(px+T/2, py+T/2+1, 4, 2.6, 0, 0, 6.2832); g.fill();
    return;
  }
  // Bigger with more people round it, which is the only thing that feeds it.
  const size = 1 + Math.min(3, f.round_it) * 0.28;
  const flick = 0.82 + Math.sin(t/90)*0.1 + Math.sin(t/37)*0.06;
  const glow = g.createRadialGradient(px+T/2, py+T/2, 1, px+T/2, py+T/2, 34*size);
  glow.addColorStop(0, 'rgba(255,196,104,0.52)');
  glow.addColorStop(0.45, 'rgba(255,150,60,0.22)');
  glow.addColorStop(1, 'rgba(255,140,50,0)');
  g.fillStyle = glow;
  g.beginPath(); g.arc(px+T/2, py+T/2, 34*size, 0, 6.2832); g.fill();
  const h = 11*size*flick;
  g.fillStyle = '#e8642a';
  g.beginPath();
  g.moveTo(px+T/2-4.5*size, py+T/2+3);
  g.quadraticCurveTo(px+T/2-2, py+T/2-h*0.5, px+T/2, py+T/2-h);
  g.quadraticCurveTo(px+T/2+2, py+T/2-h*0.5, px+T/2+4.5*size, py+T/2+3);
  g.fill();
  g.fillStyle = '#f5b93f';
  g.beginPath();
  g.moveTo(px+T/2-2.4*size, py+T/2+3);
  g.quadraticCurveTo(px+T/2-1, py+T/2-h*0.35, px+T/2, py+T/2-h*0.62);
  g.quadraticCurveTo(px+T/2+1, py+T/2-h*0.35, px+T/2+2.4*size, py+T/2+3);
  g.fill();
}

function person(g, px, py, colour, doing, t){
  const bob = Math.sin(t/600 + px) * 0.6;
  g.fillStyle = 'rgba(0,0,0,0.35)';
  g.beginPath(); g.ellipse(px+T/2, py+T-2, T*0.30, 2.5, 0, 0, 6.2832); g.fill();
  g.fillStyle = colour;
  g.fillRect(px+T/2-2, py+3+bob, 4, 6);        // body
  g.fillRect(px+T/2-3, py+9+bob, 6, 4);        // legs
  g.fillStyle = '#e8dcc8';
  g.fillRect(px+T/2-2, py+bob, 4, 3);          // head
  if(doing === 'k' || doing === 'f'){
    // crouched at the fire rather than holding a rod out
    g.fillStyle = 'rgba(245,185,63,0.5)';
    g.beginPath(); g.arc(px+T/2, py+5+bob, 5, 0, 6.2832); g.fill();
  } else if(doing !== '-'){
    // the rod, and a line out over the water
    g.strokeStyle = '#9a7a4a'; g.lineWidth = 1;
    g.beginPath(); g.moveTo(px+T/2+2, py+6+bob); g.lineTo(px+T/2+9, py-1+bob); g.stroke();
  }
}

function draw(){
  const w = state.world;
  if(!w){ requestAnimationFrame(draw); return; }
  if(cv.width !== w.w*T){ cv.width = w.w*T; cv.height = w.h*T; }
  const now = performance.now();
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(paintCoast(w), 0, 0);
  if(state.fire) fire(ctx, state.fire, now);

  // where a cast lands, and what it is doing there
  const t = ease((now - moveAt)/240);
  const was = {}; (prev.people||[]).forEach(p=>was[p.id]=p);
  const speeches = [];
  (state.people||[]).forEach(p=>{
    const from = was[p.id] || p;
    const px = (from.x + (p.x-from.x)*t) * T;
    const py = (from.y + (p.y-from.y)*t) * T;
    if(p.doing !== '-' && p.doing !== 'k' && p.doing !== 'f' && p.float){
      const fx = p.float[0]*T + T/2, fy = p.float[1]*T + T/2;
      ctx.strokeStyle = 'rgba(240,236,220,0.55)'; ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(px+T/2+9, py-1);
      ctx.quadraticCurveTo((px+fx)/2, Math.min(py,fy)-14, fx, fy);
      ctx.stroke();
      // the float bobs, and jerks when something is on it
      const jerk = p.doing === '!' ? Math.sin(now/70)*2.2 : 0;
      const dip  = p.doing === '!' ? 1.5 : 0;
      ctx.fillStyle = p.doing === '!' ? '#e86a5a' : '#e8dcc8';
      ctx.beginPath();
      ctx.arc(fx + jerk, fy + Math.sin(now/700 + fx)*0.8 + dip, 2.6, 0, 6.2832);
      ctx.fill();
      if(p.doing === '!' && Math.random() < 0.22)
        ripples.push({x:fx, y:fy, at:now});
    }
    person(ctx, px, py, SEAT[p.seat % SEAT.length], p.doing, now + hash(p.id)%900);

    /* A bite is worth looking up for, and the whole reason to be on a shore
       with other people is to be there when somebody else gets one. A count
       over every head would say something else entirely: four people on a
       beach with numbers above them are being ranked whether anybody meant
       it. This says what is happening, not what has accumulated. */
    if(p.doing === '!'){
      const jump = Math.abs(Math.sin(now/140)) * 3;
      ctx.font = 'bold 12px ui-monospace,monospace'; ctx.textAlign = 'center';
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillText('!', px+T/2+1, py-11-jump+1);
      ctx.fillStyle = '#e8503f';
      ctx.fillText('!', px+T/2, py-11-jump);
    }
    if(p.said) speeches.push({x: px + T/2, y: py - 36, text: p.said});
    if(p.name){
      ctx.font = '9px ui-monospace,monospace'; ctx.textAlign = 'center';
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillText(p.name, px+T/2+1, py-3+1);
      ctx.fillStyle = SEAT[p.seat % SEAT.length];
      ctx.fillText(p.name, px+T/2, py-3);
    }
  });

  /* Speech last, and stacked. Two people fishing side by side put their
     bubbles in the same place, and both became unreadable: the one underneath
     showed through the one on top. Anything that would overlap gets raised
     until it does not. */
  ctx.font = '10px ui-monospace,monospace'; ctx.textAlign = 'center';
  const placed = [];
  speeches.forEach(sp=>{
    const words = sp.text.length > 30 ? sp.text.slice(0,29) + '\u2026' : sp.text;
    const wide = ctx.measureText(words).width + 10;
    let bx = sp.x - wide/2, by = sp.y;
    for(let guard = 0; guard < 8; guard++){
      const clash = placed.some(q => bx < q.x + q.w + 3 && bx + wide + 3 > q.x
                                  && by < q.y + q.h + 2 && by + 15 + 2 > q.y);
      if(!clash) break;
      by -= 18;
    }
    placed.push({x: bx, y: by, w: wide, h: 15});
    ctx.fillStyle = 'rgba(14,20,16,0.82)';
    ctx.beginPath();
    if(ctx.roundRect) ctx.roundRect(bx, by, wide, 15, 4);
    else ctx.rect(bx, by, wide, 15);
    ctx.fill();
    if(by === sp.y){                       // only the unmoved one keeps a tail
      ctx.beginPath();
      ctx.moveTo(sp.x-3, by+15); ctx.lineTo(sp.x+3, by+15);
      ctx.lineTo(sp.x, by+20); ctx.fill();
    }
    ctx.fillStyle = '#e7e3d8';
    ctx.fillText(words, bx + wide/2, by + 11);
  });

  ripples = ripples.filter(r => now - r.at < 900);
  ripples.forEach(r=>{
    const age = (now - r.at)/900;
    ctx.strokeStyle = `rgba(232,220,200,${(1-age)*0.5})`;
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(r.x, r.y, 2 + age*11, 0, 6.2832); ctx.stroke();
  });

  floats = floats.filter(f => now - f.at < 2200);
  ctx.textAlign = 'center';
  floats.forEach(f=>{
    const age = (now - f.at)/2200;
    ctx.globalAlpha = 1 - age*age;
    ctx.font = 'bold 11px ui-monospace,monospace';
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillText(f.text, f.x*T+T/2+1, f.y*T-6-age*22+1);
    ctx.fillStyle = f.col;
    ctx.fillText(f.text, f.x*T+T/2, f.y*T-6-age*22);
    ctx.globalAlpha = 1;
  });
  requestAnimationFrame(draw);
}

function side(){
  const s = document.getElementById('side'), me = state.me || {};
  let h = '<h2>you</h2>';
  /* Yours alone. It is not sent anywhere, so somebody who asks has to take
     your word for it, which is the entire charm of the thing. */
  const done = me.needs ? Math.round(100 * (me.into||0) / me.needs) : 0;
  h += `<div class="lvl">fishing ${me.level||1}</div>`;
  h += `<div class="bar"><i style="width:${done}%"></i></div>`;
  h += `<div class="muted">${(me.kinds||0)} kinds &middot; ${(me.caught||0)} caught</div>`;
  h += `<div class="muted">${me.pool ? 'fishing the '+me.pool : 'not by the water'}</div>`;
  const recent = (me.recent||[]);
  if(recent.length){
    h += '<h2>lately</h2>';
    recent.forEach(r=>{ h += `<div class="kind r-${r.rarity}">${r.name}<i> ${r.cm}cm</i></div>`; });
  }
  if(state.fire){
    h += '<h2>the fire</h2>';
    if(!state.fire.lit) h += '<div class="muted">out; nobody there</div>';
    else {
      h += `<div class="lvl">burning</div>`;
      const cooking = state.fire.cooking.map(c=>c.name);
      h += `<div class="muted">${state.fire.round_it} round it${
        cooking.length ? ' &middot; ' + cooking.join(', ') + ' cooking' : ''}</div>`;
    }
    if(me.at_fire) h += `<div class="muted">you are here &middot; <b>c</b> to cook</div>`;
    if(me.wood) h += `<div class="muted">${me.wood} driftwood</div>`;
  }
  const others = (state.people||[]).filter(p=>!p.me);
  h += '<h2>on the shore</h2>';
  if(!others.length) h += '<div class="muted">nobody yet</div>';
  others.forEach(p=>{
    const what = {'-':'about','c':'fishing','!':'a bite','+':'landed one',
                  'k':'at the fire','f':'feeding the fire'}[p.doing]||'';
    h += `<div style="color:${SEAT[p.seat%SEAT.length]}">${p.name} <i class="muted">${what}</i></div>`;
  });
  s.innerHTML = h;
}

function log(){
  const el = document.getElementById('log');
  el.innerHTML = (state.log||[]).map(l =>
    `<div class="${l.role}">${l.text.replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]))}</div>`
  ).join('');
  el.scrollTop = el.scrollHeight;
}

const send = b => fetch('/do', {method:'POST', body:b});

cv.onclick = ev => {
  const w = state.world; if(!w) return;
  const box = cv.getBoundingClientRect(), cell = box.width / w.w;
  const x = Math.floor((ev.clientX - box.left)/cell);
  const y = Math.floor((ev.clientY - box.top)/cell);
  // One gesture does everything: a bite is struck, otherwise the tap is a
  // place to go and, if it is water, a thing to do when you get there.
  if(state.me && state.me.doing === '!') return send('strike');
  if(state.fire && x === state.fire.x && y === state.fire.y && state.me.at_fire)
    return send('cook');
  send(`tap ${x} ${y}`);
};

addEventListener('keydown', e=>{
  if(document.activeElement.tagName === 'INPUT') return;
  if(e.key === ' '){ e.preventDefault(); send(state.me && state.me.doing==='!' ? 'strike' : 'cast'); }
  const mv = {ArrowLeft:'w',ArrowRight:'e',ArrowUp:'n',ArrowDown:'s',
              h:'w',l:'e',k:'n',j:'s'};
  if(mv[e.key]) send('step ' + mv[e.key]);
  if(e.key === 'c') send('cook');
});

document.getElementById('mute').onclick = () => { setMuted(!muted); if(!muted) note('landed'); };
setMuted(muted);
document.getElementById('say').onsubmit = e => {
  e.preventDefault();
  const box = document.getElementById('text');
  if(box.value.trim()) send('say ' + box.value.trim());
  box.value = ''; box.blur();
};

new EventSource('/events').onmessage = m => {
  const next = JSON.parse(m.data);
  const was = state.me || {}, now2 = next.me || {};
  if(now2.doing !== was.doing){
    if(now2.doing === 'c') note('plop');
    if(now2.doing === '!') note('bite');
    if(was.doing === '!' && now2.doing === '-') note('lost');
  }
  if((now2.kinds||0) > (was.kinds||0)) note('newkind');
  else if((now2.caught||0) > (was.caught||0)) note('landed');
  const speaking = (next.people||[]).filter(p=>p.said)
                     .map(p=>p.id+':'+p.said).join('|');
  const spoke = (state.people||[]).filter(p=>p.said).map(p=>p.id+':'+p.said).join('|');
  if(speaking && speaking !== spoke) note('said');
  const moved = !state.people || JSON.stringify((next.people||[]).map(p=>[p.x,p.y]))
              !== JSON.stringify((state.people||[]).map(p=>[p.x,p.y]));
  prev = state; state = next;
  if(moved) moveAt = performance.now();
  const mine = (next.people||[]).find(p=>p.me) || {};
  (next.caught||[]).forEach(c=>{
    if(!(c.x === mine.x && c.y === mine.y)) note('theirs');
    floats.push({text:`${c.name} ${c.cm}cm`, x:c.x, y:c.y, at:performance.now(),
                 col: c.rarity==='rare' ? '#d9b25e' : c.rarity==='junk' ? '#8a8070' : '#e7e3d8'});
    ripples.push({x:c.x*T+T/2, y:c.y*T+T/2, at:performance.now()});
  });
  document.getElementById('status').textContent = next.status || '';
  side(); log();
};
draw();
</script></body></html>
"""


# Above rather than beside. Isometric was tried and cost the one thing this
# place needs: a camera means you cannot see who is on the shore, and seeing
# who is on the shore is most of why anybody is. The palette discipline came
# back with it; the projection did not.
#
# view_iso is kept because it is genuinely better for walking about, and
# FLAT_PAGE above is the plain one it all started from.
from .view_flat import PAGE as HANDHELD_PAGE
from .view_iso import PAGE as ISO_PAGE

PAGE = HANDHELD_PAGE
