// NetQueue frontend: shows the state and plays the animation.
// All queue logic and statistics come from the backend API.
const API = 'http://localhost:5000/api';
const $ = id => document.getElementById(id);
const stage = $('stage'), slots = $('slots'), router = $('router'), dest = $('dest');
const sprites = new Map();      // packet id -> {el, hold, leaving}
const onLink = new Set();       // ids currently travelling router -> destination
let ST = null;                  // latest state received from the backend

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const dur = () => $('anim').checked ? { Slow: 900, Normal: 550, Fast: 250 }[$('speed').value] : 0;

// ---------- talking to the backend ----------
async function api(path, method = 'GET', body) {
  const res = await fetch(API + path, {
    method, headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}
async function run(fn) {
  try { $('err').textContent = ''; await fn(); }
  catch (e) {
    if (e instanceof TypeError) setOnline(false);     // backend is not answering
    else $('err').textContent = e.message;
  }
}
// Shows a red banner while the backend is unreachable, hides it as soon as it answers
let online = null;
function setOnline(ok) {
  if (ok === online) return;
  online = ok;
  $('conn').hidden = ok;
  $('conn').textContent = `Cannot reach the backend (${API}). Is it running?`;
}
function setState(s, fresh) {
  if (ST && s.boot !== ST.boot) {                      // backend was restarted: start clean
    sprites.forEach(x => x.el.remove()); sprites.clear(); onLink.clear();
    ST = null; fresh = true;
  }
  if (ST && s.version < ST.version) return;           // ignore an older response
  ST = s;
  if (fresh) {                                         // fill the form from the server
    $('pid').value = s.settings.nextId; $('cap').value = s.settings.capacity; $('mode').value = s.settings.mode;
  }
  render();
}

// ---------- button actions ----------
const add = () => run(async () => {
  const d = await api('/packets', 'POST', { id: $('pid').value, source: $('src').value, destination: $('dst').value,
    protocol: $('proto').value, size: $('size').value, priority: $('pri').value });
  spawn(d.packet, d.accepted, 0); setState(d.state, true);
});
const demo = () => run(async () => {
  const d = await api('/packets/demo', 'POST');
  d.results.forEach((r, i) => spawn(r.packet, r.accepted, i)); setState(d.state, true);
});
const transmit = () => run(async () => {
  const d = await api('/transmit', 'POST');
  leave(d.packet); setState(d.state);
});
const settings = () => run(async () => {
  setState((await api('/settings', 'PUT', { capacity: +$('cap').value, mode: $('mode').value })).state);
});
let rc = 0;
function reset() {
  const b = $('rst');
  if (!rc) { b.textContent = 'CLICK AGAIN TO CONFIRM'; rc = setTimeout(() => { rc = 0; b.textContent = 'RESET SIMULATION'; }, 3000); return; }
  clearTimeout(rc); rc = 0; b.textContent = 'RESET SIMULATION';
  run(async () => {
    sprites.forEach(s => s.el.remove()); sprites.clear(); onLink.clear();
    setState((await api('/reset', 'POST')).state, true);
  });
}
// Tell the backend the packet reached the destination -> it is counted as Transmitted
function deliver(p) {
  onLink.delete(p.id);
  api(`/packets/${encodeURIComponent(p.id)}/delivered`, 'POST').then(d => setState(d.state)).catch(() => {});
}

// ---------- animation ----------
function place(el, c) {
  el.style.width = c.offsetWidth - 8 + 'px'; el.style.height = c.offsetHeight - 8 + 'px';
  el.style.left = c.offsetLeft + 4 + 'px'; el.style.top = c.offsetTop + 4 + 'px';
}
function spawn(p, ok, k) {
  const el = document.createElement('div');
  el.className = 'pkt p' + p.priority;
  el.innerHTML = esc(p.id) + '<small>[' + p.priority + ']</small>';
  stage.appendChild(el);
  const s = { el, hold: true }; sprites.set(p.id, s);
  place(el, slots.children[0] || slots);
  el.style.transition = 'none'; el.style.left = '-100px'; el.offsetWidth;   // jump off-screen without animating
  el.style.transition = '';
  setTimeout(() => { if (!s.hold) return; s.hold = false; ok ? layout() : drop(p, s); }, dur() ? k * 150 : 0);
}
function layout() {
  if (!ST) return;
  const sl = [...slots.children];
  ST.waiting.forEach((p, i) => {
    const s = sprites.get(p.id);
    if (!s || s.hold || s.leaving) return;
    place(s.el, sl[Math.max(0, sl.length - 1 - i)]);
  });
}
function flash(el) { el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 350); }
function leave(p) {
  const s = sprites.get(p.id);
  if (!s) { deliver(p); return; }
  const el = s.el, d = dur() + 30;
  s.hold = false; s.leaving = true;
  el.style.left = router.offsetLeft + router.offsetWidth / 2 - el.offsetWidth / 2 + 'px';
  setTimeout(() => {
    flash(router); onLink.add(p.id); linkUI();
    const ld = dur() ? dur() * 3 : 30;               // the router -> destination trip is slower, so it is easy to see
    el.style.transition = `left ${ld}ms linear`;
    el.style.left = dest.offsetLeft + dest.offsetWidth / 2 - el.offsetWidth / 2 + 'px';
    setTimeout(() => { el.remove(); sprites.delete(p.id); deliver(p); }, ld + 50);
  }, d);
}
function drop(p, s) {
  const el = s.el, d = dur() + 30;
  s.leaving = true;
  el.style.left = slots.offsetLeft - el.offsetWidth - 6 + 'px';
  setTimeout(() => {
    el.classList.add('x'); el.textContent = 'X'; flash(slots);
    el.style.top = stage.offsetHeight + 10 + 'px';
    setTimeout(() => { el.remove(); sprites.delete(p.id); }, d);
  }, d);
}
function linkUI() {
  const t = [...onLink];
  $('link').classList.toggle('on', t.length > 0);
  $('ltxt').textContent = t.length ? 'Transmitting ' + t.slice(0, 2).join(', ') + (t.length > 2 ? ' +' + (t.length - 2) : '') + '...' : 'idle';
}

// ---------- display ----------
function render() {
  if (!ST) return;
  const cap = ST.settings.capacity, st = ST.stats;
  if (slots.children.length !== cap) slots.innerHTML = '<i class="slot"></i>'.repeat(cap);
  $('qtitle').textContent = `${ST.settings.mode} queue (capacity ${cap})`;
  stage.style.setProperty('--dur', dur() + 'ms');

  const row = (p, label, c) => `<tr class="${c}"><td>${esc(p.id)}<td>${p.source}<td>${p.destination}<td>${p.protocol}<td>${p.size}<td>${p.priority}<td>${label}</tr>`;
  $('rows').innerHTML = ST.waiting.map(p => row(p, 'Waiting', '')).join('')
    + ST.inTransit.map(p => row(p, 'In Transit', 'tr')).join('')
    + ST.transmitted.map(p => row(p, 'Transmitted', 'ok')).join('')
    + ST.dropped.map(p => row(p, 'Dropped', 'bad')).join('');

  $('gen').textContent = st.generated; $('tx').textContent = st.transmitted; $('drop').textContent = st.dropped;
  $('qs').textContent = st.queueSize; $('avg').textContent = st.averageWait.toFixed(2) + ' sec';
  $('thr').textContent = st.throughput.toFixed(2) + ' KB/s';
  const c = $('cong'); c.textContent = st.congestion;
  c.className = { LOW: 'ok', MEDIUM: 'warn', HIGH: 'bad' }[st.congestion];

  const text = ST.log.map(l => `[${new Date(l.t).toLocaleTimeString([], { hour12: false })}] ${l.msg}`).join('\n');
  const log = $('log');
  if (log.textContent !== text) { log.textContent = text; log.scrollTop = log.scrollHeight; }

  linkUI(); layout();
}

// ---------- start ----------
addEventListener('resize', layout);
async function poll() {                              // runs every second: live stats + connection check
  try {
    const s = await api('/state');
    setOnline(true);
    setState(s, ST === null);
  } catch (e) {
    if (e instanceof TypeError) setOnline(false);
  }
}
setInterval(poll, 1000);
poll();

// ---------- graphs (the backend draws them with matplotlib; we only show the picture) ----------
function loadGraph() {
  const im = new Image();                                  // preload, so the picture does not flicker
  im.onload = () => { $('gimg').src = im.src; };
  const theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';   // same theme as the page
  im.src = `${API}/graph.png?theme=${theme}&t=${Date.now()}`;
}
function toggleGraphs() {
  const w = $('gwin'); w.hidden = !w.hidden;
  if (!w.hidden) loadGraph();
}
addEventListener('keydown', e => { if (e.key === 'Escape') $('gwin').hidden = true; });
setInterval(() => { if (!$('gwin').hidden) loadGraph(); }, 1000);   // live update while the window is open
