// Voces de la Asamblea (docs/PLAN.md, section 3). Reads only site/data, as docs/data-contract.md describes.
(async () => {
'use strict';
const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const fetchOk = async p => { const r = await fetch(p); if (!r.ok) throw new Error(`${p}: ${r.status}`); return r; };
const getJSON = async p => (await fetchOk(p)).json();
const getBin = async p => (await fetchOk(p)).arrayBuffer();
const store = new Map();
function want(p) {   // a lazy data file: fetched once, on first use; the view redraws when it arrives
  let e = store.get(p);
  if (!e) {
    store.set(p, e = {value: null, failed: false});
    getJSON('data/' + p).then(v => { e.value = v; update(); tipAgain?.(); }, err => { e.failed = true; console.error(err); update(); });
  }
  return e.value;
}
const waitMsg = p => t(store.get(p)?.failed ? 'loadError' : 'loading');

const texts = Promise.all([getJSON('i18n/es.json'), getJSON('i18n/en.json')]).then(([es, en]) => ({es, en}));
let M, I18N, GEO, IC, SHB, FRB, MFB, MSB, LABELS;
try {
  [M, I18N, GEO, IC, SHB, FRB, MFB, MSB, LABELS] = await Promise.all([
    getJSON('data/meta.json'), texts, getJSON('assets/world.json'), getJSON('assets/icons.json'),
    getBin('data/shares.bin'), getBin('data/frags.bin'), getBin('data/map_frag.bin'), getBin('data/map_speech.bin'),
    getJSON('data/map_labels.json')]);
} catch (e) {
  $('boot').textContent = (await texts.catch(() => null))?.es.loadError ?? 'No se pudieron cargar los datos.';
  console.error(e);
  return;
}
const icon = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${IC[n] || ''}</svg>`;

// ---------------- text ----------------
let lang = 'es';   // Spanish for everyone at start (docs/PLAN.md, section 3.5)
const t = (k, v = {}) => (I18N[lang][k] ?? k).replace(/\{(\w+)\}/g, (_, x) => v[x] ?? '');
let nf1;
const setFormats = () => { nf1 = new Intl.NumberFormat(lang, {minimumFractionDigits: 1, maximumFractionDigits: 1}); };
const pct = v => v == null || !isFinite(v) ? '–' : (v > 0 && v < 0.0005 ? '<' + nf1.format(0.1) : nf1.format(v * 100)) + (lang === 'es' ? ' %' : '%');
const ratioTxt = r => r == null || !isFinite(r) ? '–' : nf1.format(r) + '×';

// ---------------- data ----------------
const Y0 = M.years.first, Y1 = M.years.last, NY = Y1 - Y0 + 1;   // 2026 shows like any other year, with no label (docs/PLAN.md, section 2)
const LENSES = M.lenses, NL = LENSES.length, ALL = NL, NC = M.countries.length;
const TOPICS = M.topics;
const SH = new Float32Array(SHB), FRG = new Uint16Array(FRB);
const shareOf = (c, y, L) => SH[(c * NY + y) * (NL + 1) + L];
const measured = L => L === ALL || LENSES[L].pass !== false;   // a lens short of the pass bar: passages only
const lensName = L => L === ALL ? t('allUNODC') : LENSES[L][lang];
const lensIcon = L => L === ALL ? 'world' : LENSES[L].icon;
const lensFile = L => L === ALL ? 'all' : LENSES[L].id;
const inSentence = s => /^\p{Lu}\p{Ll}/u.test(s) ? s[0].toLocaleLowerCase(lang) + s.slice(1) : s;   // acronyms keep their capitals
const topicName = k => k < NL ? LENSES[k][lang] : (TOPICS[k]?.[lang] ?? '');
function points(buf, spec) {   // one column after another, as meta.binaries lists them
  const T = {uint16: Uint16Array, uint8: Uint8Array}, n = spec.count, col = {};
  let at = 0;
  for (const [name, dt] of spec.columns) { col[name] = new T[dt](buf, at, n); at += n * T[dt].BYTES_PER_ELEMENT; }
  const P = {n, c: col.c, m: col.lensmask, yr: col.yr, t: col.topic, x: new Float32Array(n), y: new Float32Array(n)};
  for (let i = 0; i < n; i++) { P.x[i] = col.x[i] / 65535; P.y[i] = 1 - col.y[i] / 65535; }
  return P;
}
const PF = points(MFB, M.binaries['map_frag.bin']), PS = points(MSB, M.binaries['map_speech.bin']);
const CSTART = new Int32Array(M.countries.length);   // fragment points are in country order
for (let i = PF.n - 1; i >= 0; i--) CSTART[PF.c[i]] = i;
const ISO = Object.fromEntries(M.countries.map((c, i) => [c.iso3, i]));
const cname = (c, y, bare) => {
  const C = M.countries[c], h = y != null && C.hist.find(r => y >= r.from && y <= r.to);
  return h ? h[lang] + (bare ? '' : ` (${h.from}–${h.to})`) : C[lang];
};

// ---------------- selections ----------------
const OPT = new Map();
M.groups.forEach(g => OPT.set('g:' + g.slug, {v: 'g:' + g.slug, g, key: g.slug, members: new Set(g.members)}));
M.countries.forEach((c, i) => OPT.set('c:' + c.iso3, {v: 'c:' + c.iso3, c: i, key: c.iso3, members: new Set([i])}));
const optLabel = o => o.g ? (o.g.type === 'office' ? `${o.g.short_es} · ${o.g[lang]}` : o.g[lang]) : cname(o.c);
const optShort = o => o.g ? o.g['short_' + lang] : cname(o.c);
const state = {tab: 'reg', slots: ['g:rocol', '', ''], lens: ALL, y0: Y0, y1: Y1, layer: 'frag', country: ISO.COL ?? 0, amode: 0, wordSlot: 0};
const active = () => state.slots.map((v, s) => ({s, v, o: OPT.get(v)})).filter(x => x.o);
const slotCol = s => css('--s' + (s + 1));
// the period: one year, a range of years, or all years (y0 to y1, inclusive)
const isAll = () => state.y0 === Y0 && state.y1 === Y1;
const single = () => state.y0 === state.y1 ? state.y0 : null;
const inP = yi => yi >= state.y0 - Y0 && yi <= state.y1 - Y0;
const per = () => single() != null ? String(state.y0) : `${state.y0}–${state.y1}`;
const periodKey = () => isAll() ? 'all' : single() != null ? String(state.y0) : null;   // word bars and alignment: one year or all
const yearsInP = () => d3.range(state.y0, state.y1 + 1);

function applyHash() {
  const h = decodeURIComponent(location.hash.slice(1)).toLowerCase();
  if (h && OPT.has('g:' + h)) { state.slots = ['g:' + h, '', '']; state.tab = 'reg'; return true; }
  return false;
}

// ---------------- tooltip ----------------
const tip = $('tip');
let tipAgain = null;   // redraws the open tooltip when a file it waits for arrives
function showTip(e, html) {
  tip.innerHTML = html; tip.style.opacity = 1;
  const r = tip.getBoundingClientRect(), W = innerWidth, H = innerHeight;
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + r.width > W - 8) x = Math.max(8, e.clientX - r.width - 14);
  if (y + r.height > H - 8) y = Math.max(8, e.clientY - r.height - 14);
  tip.style.transform = `translate(${x}px,${y}px)`;
}
const hideTip = () => { tip.style.opacity = 0; tipAgain = null; };
addEventListener('scroll', hideTip, {passive: true});

// ---------------- aggregates (each country weighs the same) ----------------
let CM = {};
function cmOf(L) {   // each country's mean over the years of the period in which it spoke
  if (CM[L]) return CM[L];
  const out = new Array(NC).fill(null);
  for (let c = 0; c < NC; c++) {
    let a = 0, k = 0;
    for (const y of yearsInP()) { const v = shareOf(c, y - Y0, L); if (!Number.isNaN(v)) { a += v; k++; } }
    if (k) out[c] = a / k;
  }
  return (CM[L] = out);
}
const meanOf = (cm, members) => { let a = 0, k = 0; for (const c of members) if (cm[c] != null) { a += cm[c]; k++; } return k ? a / k : null; };
const worldOf = cm => { let a = 0, k = 0; for (const v of cm) if (v != null) { a += v; k++; } return k ? a / k : null; };

// ---------------- controls ----------------
function fillSelects() {
  const byName = xs => xs.sort((a, b) => a[0].localeCompare(b[0], lang));
  ['slot0', 'slot1', 'slot2'].forEach((id, s) => {
    const el = $(id); el.innerHTML = '';
    el.setAttribute('aria-label', `${t('compare')} ${s + 1}`);
    el.append(new Option(t('none'), ''));
    const og = [t('gOff'), t('gBloc'), t('gCty')].map(l => { const g = document.createElement('optgroup'); g.label = l; return g; });
    M.groups.forEach(g => og[g.type === 'office' || g.type === 'nofield' ? 0 : 1].append(new Option(optLabel(OPT.get('g:' + g.slug)), 'g:' + g.slug)));
    byName(M.countries.map((c, i) => [cname(i), 'c:' + c.iso3])).forEach(([l, v]) => og[2].append(new Option(l, v)));
    el.append(...og); el.value = state.slots[s];
  });
  const cs = $('countrySel'); cs.innerHTML = '';
  byName(M.countries.map((c, i) => [cname(i), i])).forEach(([l, i]) => cs.append(new Option(l, i)));
  cs.value = state.country;
}
['slot0', 'slot1', 'slot2'].forEach((id, s) => $(id).addEventListener('change', e => { state.slots[s] = e.target.value; update(); }));
$('countrySel').addEventListener('change', e => { state.country = +e.target.value; update(); });
const yFrom = $('yearFrom'), yTo = $('yearTo');
let linked = null;   // from all years, the first move of a handle picks one year: the other handle follows it
[yFrom, yTo].forEach(el => {
  el.min = Y0; el.max = Y1;
  el.addEventListener('pointerdown', () => { if (isAll()) linked = el; });
  el.addEventListener('input', () => {
    if (isAll() && !linked) linked = el;
    if (linked === el) (el === yFrom ? yTo : yFrom).value = el.value;
    const a = +yFrom.value, b = +yTo.value;
    state.y0 = Math.min(a, b); state.y1 = Math.max(a, b); update();
  });
  el.addEventListener('change', () => { linked = null; });
});
yFrom.value = Y0; yTo.value = Y1;
$('allYears').addEventListener('click', () => { state.y0 = yFrom.value = Y0; state.y1 = yTo.value = Y1; update(); });
document.querySelectorAll('[data-layer]').forEach(b => b.addEventListener('click', () => { state.layer = b.dataset.layer; update(); }));
document.querySelectorAll('#amodeSeg button').forEach(b => b.addEventListener('click', () => { state.amode = +b.dataset.mode; update(); }));
document.querySelectorAll('#langSeg button').forEach(b => b.addEventListener('click', () => { if (lang !== b.dataset.lang) { lang = b.dataset.lang; applyLang(); } }));
function setTab(tab) {
  state.tab = tab;
  $('tabReg').setAttribute('aria-selected', tab === 'reg'); $('tabCty').setAttribute('aria-selected', tab === 'cty');
  $('paneReg').hidden = tab !== 'reg'; $('paneCty').hidden = tab !== 'cty';
  $('ctlSlots').hidden = tab !== 'reg'; $('ctlCountry').hidden = tab !== 'cty';
  hideTip(); update();
}
$('tabReg').addEventListener('click', () => setTab('reg'));
$('tabCty').addEventListener('click', () => setTab('cty'));
[$('tabReg'), $('tabCty')].forEach(b => b.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { const n = state.tab === 'reg' ? 'cty' : 'reg'; setTab(n); $(n === 'reg' ? 'tabReg' : 'tabCty').focus(); }
}));
$('icReg').innerHTML = icon('world'); $('icCty').innerHTML = icon('map-pin');

// ---------------- lens strip ----------------
function dumbbell(vals, w, mx) {
  const X = v => (100 * (v || 0) / mx).toFixed(1) + '%';
  let h = `<span class="db" aria-hidden="true"><i class="tr"></i>`;
  const v1 = vals[0];
  if (v1 && v1.v != null && w != null) { const a = Math.min(w, v1.v), b = Math.max(w, v1.v); h += `<i class="lk" style="left:${X(a)};width:${(100 * (b - a) / mx).toFixed(1)}%;background:var(--s${v1.s + 1})"></i>`; }
  if (w != null) h += `<i class="w" style="left:${X(w)}"></i>`;
  for (const x of vals.slice().reverse()) if (x.v != null) h += `<i class="d" style="left:${X(x.v)};background:var(--s${x.s + 1})"></i>`;
  return h + '</span>';
}
function drawStrip() {
  const act = active(), s1 = act[0];
  $('stripHint').textContent = s1 ? t('stripHint', {sel: optShort(s1.o), per: per()}) : t('stripHintNone', {per: per()});
  const order = [ALL, ...d3.range(NL)];
  $('lenses').innerHTML = order.map(L => {
    const cls = 'lens' + (L === ALL ? ' all' : '') + (L !== ALL && LENSES[L].reference ? ' ref' : '');
    const head = `<span class="ic-row">${icon(lensIcon(L))}<span class="nm">${esc(lensName(L))}</span></span>`;
    if (!measured(L)) return `<button class="${cls}" data-l="${L}" aria-pressed="${state.lens === L}" aria-label="${esc(lensName(L))}: ${esc(t('notMeasured'))}">${head}<span class="rt">–</span><span class="na">${esc(t('notMeasured'))}</span></button>`;
    const cm = cmOf(L), w = worldOf(cm);
    const vals = act.map(a => ({s: a.s, v: meanOf(cm, a.o.members), lab: optShort(a.o)}));
    const r = s1 && vals[0].v != null && w ? vals[0].v / w : null;
    const mx = Math.max(w || 0, ...vals.map(x => x.v || 0)) * 1.15 || 1;
    const parts = (s1 ? [`${vals[0].lab} ${pct(vals[0].v)}`] : []).concat([`${t('world')} ${pct(w)}`]);
    return `<button class="${cls}" data-l="${L}" aria-pressed="${state.lens === L}" aria-label="${esc(lensName(L))}: ${r != null ? esc(ratioTxt(r) + ' ' + t('timesWorld')) + '. ' : ''}${esc(parts.join(' · '))}">
      ${head}<span class="rt">${ratioTxt(r)}<small>${r != null ? t('timesWorld') : ''}</small></span>
      ${dumbbell(vals, w, mx)}<span class="vals">${parts.map(x => `<span>${esc(x)}</span>`).join(' · ')}</span></button>`;
  }).join('');
  $('lenses').querySelectorAll('.lens').forEach(b => {
    const L = +b.dataset.l;
    b.onclick = () => { state.lens = L; update(); };
    b.onmousemove = e => {
      if (!measured(L)) return showTip(e, `<b>${esc(lensName(L))}</b><br>${esc(t('notMeasured'))}`);
      const cm = cmOf(L);
      showTip(e, `<b>${esc(lensName(L))}</b><br>` + active().map(a => `${esc(optShort(a.o))}: ${pct(meanOf(cm, a.o.members))}`).concat([`${t('world')}: ${pct(worldOf(cm))}`]).join('<br>'));
    };
    b.onmouseleave = hideTip;
  });
}

// ---------------- semantic maps ----------------
const coarse = matchMedia('(pointer: coarse)').matches;
const qtCache = {};
const quadtree = sp => {   // the points of the chosen years only: the other years' outline does not answer a hover
  const k = state.y0 + '|' + state.y1, P = sp ? PS : PF;
  if (qtCache[sp]?.k !== k) qtCache[sp] = {k, t: d3.quadtree().x(i => P.x[i]).y(i => P.y[i]).addAll(d3.range(P.n).filter(i => inP(P.yr[i])))};
  return qtCache[sp].t;
};
function SemMap(wrap, layersOf) {
  const cv = wrap.querySelector('canvas'), ctx = cv.getContext('2d'), rb = wrap.querySelector('.reset'), PAD = 18;
  let tf = d3.zoomIdentity, cw = 0, ch = 0, groups = null, key = '';
  const sx = x => tf.applyX(PAD + x * (cw - 2 * PAD)), sy = y => tf.applyY(PAD + y * (ch - 2 * PAD));
  this.resize = () => { const r = wrap.getBoundingClientRect(), dpr = devicePixelRatio || 1; cw = r.width; ch = r.height; cv.width = Math.max(1, cw * dpr); cv.height = Math.max(1, ch * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
  this.invalidate = () => { groups = null; };
  this.draw = () => {
    if (!cw || wrap.offsetParent === null) return;
    const sp = state.layer === 'speech', P = sp ? PS : PF;
    const spec = layersOf(sp);   // [{col, rad?, alpha?, ring?}] from back to front, and which layer each point is on
    const k = sp + '|' + spec.key;
    if (!groups || key !== k) {   // points grouped by layer once per state change, not per zoom step
      const lists = spec.layers.map(() => []);
      for (let i = 0; i < P.n; i++) { const l = spec.layerOf(i); if (l >= 0) lists[l].push(i); }
      groups = lists; key = k;
    }
    ctx.clearRect(0, 0, cw, ch);
    const dens = Math.min(1, Math.max(0.5, Math.sqrt(cw * ch / 430000)));
    const base = sp ? 1.6 * Math.max(0.75, dens) : (P.n > 150000 ? 0.8 : 1.1) * dens, r = Math.max(base, Math.min(sp ? 3.4 : 2.4, base * Math.sqrt(tf.k)));
    spec.layers.forEach((ly, l) => {
      const rad = r + (ly.bump || 0), round = sp || ly.round;
      ctx.globalAlpha = ly.alpha ?? 1; ctx.fillStyle = ly.col; ctx.beginPath();
      for (const i of groups[l]) {
        const x = sx(P.x[i]), y = sy(P.y[i]);
        if (x > -4 && x < cw + 4 && y > -4 && y < ch + 4) { if (round) { ctx.moveTo(x + rad, y); ctx.arc(x, y, rad, 0, 6.2832); } else ctx.rect(x - rad, y - rad, rad * 2, rad * 2); }
      }
      ctx.fill();
      if (ly.ring) { ctx.lineWidth = 1; ctx.strokeStyle = ly.ring; ctx.stroke(); }
    });
    ctx.globalAlpha = 1;
    const placed = [], labels = (sp ? LABELS.speeches : LABELS.fragments).slice().sort((a, b) => (b.t < NL) - (a.t < NL) || b.n - a.n);
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
    const ink2 = css('--ink-2'), bg = css('--panel'), unt = css('--un-text');
    for (const lb of labels) {
      let X = sx(lb.x), Y = sy(1 - lb.y);
      if (X < 0 || X > cw || Y < 0 || Y > ch) continue;
      const label = topicName(lb.t), lensT = lb.t < NL;
      ctx.font = `${lensT ? 700 : 600} ${lensT ? 12.5 : 11.5}px "Roboto Condensed", "Arial Narrow", sans-serif`;
      const w = ctx.measureText(label).width + 8, h = lensT ? 17 : 15;
      if (w > cw - 4) continue;
      X = Math.min(Math.max(X, w / 2 + 2), cw - w / 2 - 2); Y = Math.min(Math.max(Y, h / 2 + 2), ch - h / 2 - 2);
      const box = [X - w / 2, Y - h / 2, X + w / 2, Y + h / 2];
      if (placed.some(b => !(box[2] < b[0] || box[0] > b[2] || box[3] < b[1] || box[1] > b[3]))) continue;
      placed.push(box);
      ctx.lineWidth = 3.5; ctx.strokeStyle = bg; ctx.strokeText(label, X, Y);
      ctx.fillStyle = lensT ? unt : ink2; ctx.fillText(label, X, Y);
    }
    rb.hidden = tf.k === 1 && tf.x === 0 && tf.y === 0;
  };
  const zoom = d3.zoom().scaleExtent([1, 14]).on('zoom', e => { tf = e.transform; hideTip(); this.draw(); });
  if (!coarse) d3.select(cv).call(zoom);
  rb.addEventListener('click', () => { d3.select(cv).call(zoom.transform, d3.zoomIdentity); tf = d3.zoomIdentity; this.draw(); });
  const pick = e => {
    const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    const dx = (tf.invertX(mx) - PAD) / (cw - 2 * PAD), dy = (tf.invertY(my) - PAD) / (ch - 2 * PAD), rad = (coarse ? 14 : 8) / (tf.k * (cw - 2 * PAD));
    return quadtree(state.layer === 'speech').find(dx, dy, rad);
  };
  const hover = e => {
    const i = pick(e); if (i == null) return hideTip();
    if (state.layer === 'speech') {
      const c = PS.c[i], y = Y0 + PS.yr[i], iso = M.countries[c].iso3;
      const comp = want('composition.json'), sp = want('speeches.json');
      const parts = comp ? (comp[iso]?.[y] || []).slice(0, 3).map(([k, v]) => `${esc(topicName(k))} ${pct(v)}`).join(' · ') : waitMsg('composition.json');
      const [, rep, rl] = sp?.[iso]?.[y] || [];
      const on = rep && rl >= 0 ? `<span class="ql">${icon(LENSES[rl].icon)}${esc(LENSES[rl][lang])}</span>` : '';
      showTip(e, `<b>${esc(cname(c, y))} · ${y}</b><br>${parts}${rep ? `<q>${on}“${esc(rep)}”</q>` : ''}`);
    } else {
      const c = PF.c[i], y = Y0 + PF.yr[i], m = PF.m[i], ls = [];
      for (let j = 0; j < NL; j++) if (m & (1 << j)) ls.push(LENSES[j][lang]);
      const f = `snips/${M.countries[c].iso3}.json`, sn = want(f), txt = sn?.[i - CSTART[c]];
      showTip(e, `<b>${esc(cname(c, y))} · ${y}</b><br><span class="tl">${esc(ls.length ? ls.slice(0, 2).join(' · ') : topicName(PF.t[i]))}</span>`
        + (txt ? `<q>“${esc(txt)}”</q>` : `<q>${waitMsg(f)}</q>`));
    }
    tipAgain = () => hover(e);
  };
  cv.addEventListener('pointermove', e => { if (e.pointerType === 'mouse') hover(e); });
  cv.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse') hover(e); });
  cv.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') hideTip(); });
  new ResizeObserver(() => { this.resize(); this.draw(); }).observe(wrap);
  this.resize();
}
// Selection colour per country: the smallest active selection wins
const cSlot = new Int8Array(NC);
function computeSlots() {
  cSlot.fill(-1);
  const cSize = new Float64Array(NC).fill(Infinity);
  for (const a of active()) { const n = a.o.members.size; for (const c of a.o.members) if (n < cSize[c]) { cSize[c] = n; cSlot[c] = a.s; } }
}
const regMap = new SemMap($('regMapWrap'), sp => {
  const P = sp ? PS : PF;
  const alpha = isAll() ? (sp ? 0.8 : 0.55) : 1, bump = isAll() ? 0 : (sp ? 0.6 : 0.3);
  // the selections over the rest; with a year chosen, the other years stay as a faint outline of the map
  const layers = [{col: css('--dot'), alpha: 0.3}, {col: css('--dot')}, ...[2, 1, 0].map(s => ({col: slotCol(s), alpha, bump}))];
  return {layers, key: [state.y0, state.y1, state.slots.join(','), css('--dot')].join('|'),
    layerOf: i => { if (!inP(P.yr[i])) return 0; const s = cSlot[P.c[i]]; return s >= 0 ? 4 - s : 1; }};
});
const ctyMap = new SemMap($('ctyMapWrap'), sp => {
  const P = sp ? PS : PF, c = state.country;
  return {layers: [{col: css('--dot'), alpha: 0.3}, {col: css('--dot')}, {col: css('--s1'), bump: sp ? 2 : 1.9, round: true, ring: css('--panel')}],
    key: [c, state.y0, state.y1, css('--dot')].join('|'), layerOf: i => !inP(P.yr[i]) ? 0 : P.c[i] === c ? 2 : 1};
});
function drawLegends() {
  const items = active().map(({s, o}) => `<span><i style="background:var(--s${s + 1})"></i>${esc(optShort(o))}</span>`);
  items.push(`<span><i style="background:var(--dot)"></i>${t('rest')}</span>`);
  $('regLegend').innerHTML = items.join('');
  $('ctyLegend').innerHTML = `<span><i style="background:var(--s1)"></i>${esc(cname(state.country))}</span><span><i style="background:var(--dot)"></i>${t('rest')}</span>`;
  document.querySelectorAll('[data-layer]').forEach(b => b.setAttribute('aria-pressed', b.dataset.layer === state.layer));
  $('semHint').textContent = t(state.layer === 'speech' ? 'semHintSpeech' : 'semHintFrag');
}

// ---------------- world map ----------------
const feats = topojson.feature(GEO, GEO.objects.countries).features.filter(f => f.id !== '010');
const featCountry = new Map();   // feature -> country index, by world-atlas id or by name for extra features
M.countries.forEach((c, i) => { if (c.map_id) featCountry.set('id:' + c.map_id, i); c.map_extra.forEach(n => featCountry.set('nm:' + n, i)); });
const cOfFeat = f => featCountry.get('id:' + f.id) ?? featCountry.get('nm:' + f.properties?.name);
const drawn = new Set(feats.map(cOfFeat));
const dots = M.countries.map((c, i) => ({c: i, p: c.point})).filter(d => d.p && !drawn.has(d.c));
const WW = 640, WH = 330;
const proj = d3.geoEqualEarth().fitExtent([[4, 4], [WW - 4, WH - 4]], {type: 'FeatureCollection', features: feats});
const gpath = d3.geoPath(proj);
const wsvg = d3.select('#world').append('svg').attr('viewBox', `0 0 ${WW} ${WH}`).attr('role', 'img');
const wpaths = wsvg.append('g').selectAll('path').data(feats).join('path').attr('d', gpath);
const wdots = wsvg.append('g').selectAll('circle').data(dots).join('circle')
  .attr('cx', d => proj([d.p[1], d.p[0]])[0]).attr('cy', d => proj([d.p[1], d.p[0]])[1]).attr('r', 2.6);
const wsel = wsvg.append('g');
const wmsg = wsvg.append('text').attr('x', WW / 2).attr('y', WH / 2).attr('text-anchor', 'middle').attr('font-size', 13);
function drawWorld() {
  const L = state.lens, ok = measured(L), cm = ok ? cmOf(L) : new Array(NC).fill(null);
  const vals = cm.filter(v => v != null && v > 0);
  const qs = vals.length ? d3.scaleQuantile().domain(vals).range([1, 2, 3, 4]).quantiles() : [];
  const cols = ['--q0', '--q1', '--q2', '--q3', '--q4'].map(css), nod = css('--nodata'), line = css('--land-line');
  const colOf = v => v == null ? nod : v === 0 ? cols[0] : cols[1 + d3.bisectRight(qs, v)];
  wpaths.attr('fill', f => { const c = cOfFeat(f); return colOf(c != null ? cm[c] : null); }).attr('stroke', line).attr('stroke-width', 0.4);
  const inSel = d => cSlot[d.c] >= 0;   // states too small to draw: a ring in their selection's colour
  wdots.attr('fill', d => colOf(cm[d.c])).attr('stroke', d => inSel(d) ? slotCol(cSlot[d.c]) : line)
    .attr('stroke-width', d => inSel(d) ? 1.8 : 0.6).attr('r', d => inSel(d) ? 3.4 : 2.6);
  // Each member country outlined in its selection's colour, the largest selection first
  const outl = [];
  active().forEach(({s, o}) => feats.forEach(f => { if (o.members.has(cOfFeat(f))) outl.push({f, s, n: o.members.size}); }));
  outl.sort((a, b) => b.n - a.n);
  wsel.selectAll('path').data(outl).join('path').attr('d', d => gpath(d.f)).attr('fill', 'none')
    .attr('stroke', d => slotCol(d.s)).attr('stroke-width', 1.6).attr('stroke-linejoin', 'round').attr('pointer-events', 'none');
  const tipOf = (e, c) => c == null ? hideTip() : showTip(e, `<b>${esc(cname(c, single()))}</b><br>${ok ? (cm[c] == null ? t('noSpeech') : pct(cm[c])) : esc(t('notMeasured'))}`);
  wpaths.on('mousemove', (e, f) => tipOf(e, cOfFeat(f))).on('mouseleave', hideTip);
  wdots.on('mousemove', (e, d) => tipOf(e, d.c)).on('mouseleave', hideTip);
  wmsg.text(ok ? '' : t('notMeasured')).attr('fill', css('--ink-2'));
  const title = L === ALL ? t('worldTitleAll') : t('worldTitle', {l: inSentence(lensName(L))});
  wsvg.attr('aria-label', title); $('worldTitle').textContent = title;
  $('worldHint').textContent = single() != null ? t('yearN', {y: single()}) : t('avg', {per: per()});
  const sels = active().map(({s, o}) => `<span><i class="ol" style="border-color:var(--s${s + 1})"></i><em>${esc(optShort(o))}</em></span>`).join('');
  $('worldScale').innerHTML = cols.map(c => `<i style="background:${c}"></i>`).join('') + `<em>${t('lessMore')}</em><i style="background:${nod}"></i><em>${t('noSpeech')}</em>`
    + (sels && `<span class="sels">${sels}</span>`);   // the selections' outlines on a line of their own
}

// ---------------- trend ----------------
let TW = 640; const TH = 250, TM = {t: 12, r: 96, b: 24, l: 40};
const tsvg = d3.select('#trend').append('svg').attr('viewBox', `0 0 ${TW} ${TH}`).attr('role', 'img');
const tx = d3.scaleLinear().domain([Y0, Y1]).range([TM.l, TW - TM.r]), ty = d3.scaleLinear().range([TH - TM.b, TM.t]);
const gGrid = tsvg.append('g'), gAx = tsvg.append('g'), gLines = tsvg.append('g'), gMark = tsvg.append('g'), gHover = tsvg.append('g');
let series = [];
function seriesFor(members, L) {   // equal-weight mean per year, then a centred 3-year average
  const raw = d3.range(NY).map(y => { let a = 0, k = 0; for (let c = 0; c < NC; c++) { if (members && !members.has(c)) continue; const v = shareOf(c, y, L); if (!Number.isNaN(v)) { a += v; k++; } } return k ? a / k : null; });
  return raw.map((v, k) => { if (v == null) return null; const w = [raw[k - 1], v, raw[k + 1]].filter(x => x != null); return d3.mean(w); });
}
function drawTrend() {
  const L = state.lens, title = L === ALL ? t('trendTitleAll') : t('trendTitle', {l: lensName(L)});
  $('trendTitle').textContent = title; tsvg.attr('aria-label', title);
  TW = Math.max(300, Math.round($('trend').clientWidth || 640)); TM.r = TW < 480 ? 80 : 96;
  tsvg.attr('viewBox', `0 0 ${TW} ${TH}`); tx.range([TM.l, TW - TM.r]);
  gGrid.selectAll('*').remove(); gAx.selectAll('*').remove(); gLines.selectAll('*').remove(); gMark.selectAll('*').remove();
  if (!measured(L)) { series = []; gAx.append('text').attr('x', TW / 2).attr('y', TH / 2).attr('text-anchor', 'middle').attr('font-size', 13).attr('fill', css('--ink-2')).text(t('notMeasured')); return; }
  series = active().map(({s, o}) => ({name: optShort(o), col: slotCol(s), v: seriesFor(o.members, L)}));
  series.push({name: t('world'), col: css('--world'), v: seriesFor(null, L), dash: '4 3'});
  const mx = d3.max(series, s => d3.max(s.v)) || 0.01;
  ty.domain([0, mx * 1.08]).nice(4);
  const muted = css('--muted');
  gGrid.selectAll('line').data(ty.ticks(4)).join('line').attr('x1', TM.l).attr('x2', TW - TM.r).attr('y1', d => ty(d)).attr('y2', d => ty(d)).attr('stroke', css('--line-2'));
  gAx.selectAll('text.y').data(ty.ticks(4)).join('text').attr('class', 'y').attr('x', TM.l - 6).attr('y', d => ty(d)).attr('dy', '0.32em').attr('text-anchor', 'end').attr('fill', muted).attr('font-size', 11).text(d => d3.format(d < 0.01 && d > 0 ? '.1~%' : '.0%')(d));
  gAx.selectAll('text.x').data(TW - TM.r - TM.l > 330 ? [1950, 1970, 1990, 2010, Y1] : [1950, 1990, Y1]).join('text').attr('class', 'x').attr('x', d => tx(d)).attr('y', TH - 6).attr('text-anchor', d => d === Y1 ? 'end' : 'middle').attr('fill', muted).attr('font-size', 11).text(d => d);
  const line = d3.line().defined(d => d != null).x((d, k) => tx(Y0 + k)).y(d => ty(d)).curve(d3.curveMonotoneX);
  gLines.selectAll('path').data(series).join('path').attr('fill', 'none').attr('stroke', d => d.col).attr('stroke-width', d => d.dash ? 1.6 : 2).attr('stroke-dasharray', d => d.dash || null).attr('d', d => line(d.v));
  const ends = series.map(s => { let k = s.v.length - 1; while (k > 0 && s.v[k] == null) k--; return {s, y: ty(s.v[k] ?? 0)}; }).sort((a, b) => a.y - b.y);
  for (let k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 15) ends[k].y = ends[k - 1].y + 15;
  const over = ends.length ? ends[ends.length - 1].y - (TH - TM.b) : 0;
  if (over > 0) ends.forEach(e => e.y -= over);
  gLines.selectAll('text').data(ends).join('text').attr('x', TW - TM.r + 6).attr('y', d => d.y).attr('dy', '0.32em').attr('font-size', 11.5).attr('font-weight', 600).attr('fill', d => d.s.col).attr('font-family', 'Roboto Condensed, Arial Narrow, sans-serif').text(d => d.s.name.length > 15 ? d.s.name.slice(0, 14) + '…' : d.s.name);
  if (!isAll() && single() == null) gGrid.append('rect').attr('x', tx(state.y0)).attr('width', tx(state.y1) - tx(state.y0)).attr('y', TM.t).attr('height', TH - TM.b - TM.t).attr('fill', css('--ink')).attr('opacity', 0.06);
  if (single() != null) gMark.append('line').attr('x1', tx(single())).attr('x2', tx(single())).attr('y1', TM.t).attr('y2', TH - TM.b).attr('stroke', css('--ink')).attr('stroke-width', 1).attr('stroke-dasharray', '2 3');
}
tsvg.on('mousemove', e => {
  const [mx] = d3.pointer(e), y = Math.round(tx.invert(mx)); if (!series.length || y < Y0 || y > Y1) { gHover.selectAll('*').remove(); return hideTip(); }
  gHover.selectAll('line').data([y]).join('line').attr('x1', tx(y)).attr('x2', tx(y)).attr('y1', TM.t).attr('y2', TH - TM.b).attr('stroke', css('--muted')).attr('stroke-width', 1);
  gHover.selectAll('circle').data(series.filter(s => s.v[y - Y0] != null)).join('circle').attr('cx', tx(y)).attr('cy', s => ty(s.v[y - Y0])).attr('r', 4).attr('fill', s => s.col).attr('stroke', css('--panel')).attr('stroke-width', 2);
  showTip(e, `<b>${y}</b><br>` + series.map(s => `<i class="sw" style="background:${s.col}"></i>${esc(s.name)}: ${s.v[y - Y0] == null ? esc(t('noSpeech')) : pct(s.v[y - Y0])}`).join('<br>'));
}).on('mouseleave', () => { gHover.selectAll('*').remove(); hideTip(); });
let trendW = 0;
new ResizeObserver(() => { const w = $('trend').clientWidth; if (w && w !== trendW && state.tab === 'reg') { trendW = w; drawTrend(); } }).observe($('trend'));

// ---------------- distinctive words (precomputed Fightin' Words z-scores) ----------------
function drawWords() {
  const act = active();
  $('wordsHint').textContent = state.lens === ALL ? t('wordsHintAll') : t('wordsHint', {l: inSentence(lensName(state.lens))});
  if (!act.find(a => a.s === state.wordSlot)) state.wordSlot = act[0]?.s ?? 0;
  $('wordTabs').innerHTML = act.length > 1 ? act.map(({s, o}) => `<button data-s="${s}" aria-pressed="${s === state.wordSlot}"><i style="background:var(--s${s + 1})"></i>${esc(optShort(o))}</button>`).join('') : '';
  $('wordTabs').querySelectorAll('button').forEach(b => b.onclick = () => { state.wordSlot = +b.dataset.s; drawWords(); });
  const box = $('words'), a = act.find(x => x.s === state.wordSlot);
  if (!a) return box.innerHTML = `<div class="empty">${t('pickSel')}</div>`;
  if (!measured(state.lens)) return box.innerHTML = `<div class="empty">${t('notMeasured')}</div>`;
  const file = `keyness/${lensFile(state.lens)}.json`, data = want(file);
  if (!data) return box.innerHTML = `<div class="empty">${waitMsg(file)}</div>`;
  if (periodKey() == null) return box.innerHTML = `<div class="empty">${t('rangeNA')}</div>`;
  const e = data[a.o.key]?.[periodKey()];
  if (!e) return box.innerHTML = `<div class="empty">${t('fewText')}</div>`;
  const uni = e.words.slice(0, 8), bi = e.bigrams.slice(0, 8);
  const zmax = d3.max(uni.concat(bi), x => x[1]), col = `var(--s${a.s + 1})`;
  const list = xs => xs.length ? `<div class="bars">${xs.map(([w, z, n]) => `<div class="brow" data-w="${esc(w)}" data-n="${n}" data-z="${z}"><span>${esc(w)}</span><b style="width:${(100 * z / zmax).toFixed(1)}%;background:${col}"></b></div>`).join('')}</div>` : `<div class="empty">–</div>`;
  box.innerHTML = `<div class="wcols"><div><h3>${t('words')}</h3>${list(uni)}</div><div><h3>${t('phrases')}</h3>${list(bi)}</div></div>`;
  box.querySelectorAll('.brow').forEach(r => { r.onmousemove = ev => showTip(ev, `<b>${esc(r.dataset.w)}</b><br>${t('times', {n: r.dataset.n})} · z ${nf1.format(+r.dataset.z)}`); r.onmouseleave = hideTip; });
}

// ---------------- excerpts ----------------
const quoteHTML = (q, colVar) => `<div class="quote" style="--c:${colVar}"><div class="meta">${esc(cname(q.c, q.y))} · ${q.y}<span class="ln">${icon(lensIcon(q.l))}${esc(LENSES[q.l][lang])}</span><small>EN</small></div><p>“${esc(q.x)}”</p></div>`;
function candidates(data, members) {   // the members' excerpts in the period, most recent year first, then by probability
  const out = [];
  for (const c of members) {
    const byYear = data[M.countries[c].iso3]; if (!byYear) continue;
    for (const y of yearsInP()) for (const [l, p, x] of byYear[y] || []) out.push({c, y, l, p, x});
  }
  return out.sort((a, b) => b.y - a.y || b.p - a.p);
}
function drawQuotes() {
  const box = $('quotes'), act = active();
  if (!act.length) return box.innerHTML = `<div class="empty">${t('pickSel')}</div>`;
  const file = `excerpts/${lensFile(state.lens)}.json`, data = want(file);
  if (!data) return box.innerHTML = `<div class="empty">${waitMsg(file)}</div>`;
  const pools = act.map(({s, o}) => candidates(data, o.members).map(q => ({...q, slot: s})));
  const out = [], used = new Set();
  for (let round = 0; out.length < 3 && round < 3; round++) for (const pool of pools) {
    if (out.length >= 3) break;
    const q = pool.find(x => !used.has(x.c)); if (q) { used.add(q.c); out.push(q); }
  }
  box.innerHTML = out.length ? out.map(q => quoteHTML(q, `var(--s${q.slot + 1})`)).join('') : `<div class="empty">${t('noQuotes')}</div>`;
}

// ---------------- country tab ----------------
function drawCountry() {
  const c = state.country, iso = M.countries[c].iso3, ys = yearsInP().filter(y => FRG[c * NY + y - Y0] > 0);
  const one = single();
  $('ctyName').textContent = cname(c, one);
  const sp = want('speeches.json'), who = one != null ? sp?.[iso]?.[one]?.[0] : '';
  $('ctyWhen').textContent = isAll() ? t('allYears', {per: per()}) : one != null ? t('speechOf', {y: one}) + (who ? ` · ${who}` : '') : t('speechesOf', {per: per()});
  document.querySelectorAll('#amodeSeg button').forEach(b => b.setAttribute('aria-pressed', +b.dataset.mode === state.amode));
  const empty = !ys.length ? t('noCtySpeech', {c: cname(c), y: per()}) : null;
  // composition: the mean of its speeches' parts, each speech weighing the same
  const comp = want('composition.json');
  if (empty || !comp) $('comp').innerHTML = `<div class="empty">${empty || waitMsg('composition.json')}</div>`;
  else {
    const agg = new Map();
    for (const y of ys) for (const [k, v] of comp[iso]?.[y] || []) agg.set(k, (agg.get(k) || 0) + v / ys.length);
    const items = [...agg].sort((a, b) => b[1] - a[1]), top = items.slice(0, 5), rest = 1 - d3.sum(top, x => x[1]);
    // blue for UNODC topics, grey for the others; neighbours of one family alternate two shades
    let g = 0, u = 0;
    const segs = top.map(([k, n]) => ({k, n, col: k < NL ? (u++ % 2 ? 'var(--comp-u2)' : 'var(--comp-u)') : (g++ % 2 ? 'var(--comp-g2)' : 'var(--comp-g1)')}));
    if (rest > 0.0005) segs.push({k: -1, n: rest, col: 'var(--comp-o)'});
    $('comp').innerHTML = `<div class="compbar" role="img" aria-label="${esc(t('compTitle'))}">${segs.map(x => `<i style="flex:${x.n} 1 0;background:${x.col}" data-k="${x.k}" data-n="${x.n}"></i>`).join('')}</div>
      <ul class="clegend">${segs.map(x => `<li><i class="sw" style="background:${x.col}"></i>${x.k >= 0 && x.k < NL ? icon(LENSES[x.k].icon) : ''}<span>${esc(x.k < 0 ? t('others') : topicName(x.k))}</span><b>${pct(x.n)}</b></li>`).join('')}</ul>`;
    $('comp').querySelectorAll('.compbar i').forEach(el => { el.onmousemove = e => showTip(e, `<b>${esc(+el.dataset.k < 0 ? t('others') : topicName(+el.dataset.k))}</b><br>${pct(+el.dataset.n)}`); el.onmouseleave = hideTip; });
  }
  // alignment
  $('alignHint').textContent = isAll() ? t('alignHintAll') : one != null ? t('alignHintY', {y: one}) : '';
  const alFile = `alignment/${periodKey()}.json`, al = empty || periodKey() == null ? null : want(alFile);
  if (empty || !al) $('align').innerHTML = `<div class="empty">${empty || (periodKey() == null ? t('rangeNA') : waitMsg(alFile))}</div>`;
  else {
    const rec = al[iso]?.[state.amode ? 'unodc' : 'overall'];
    if (!rec || !rec.top.length) $('align').innerHTML = `<div class="empty">${t('noU')}</div>`;
    else {
      const rows = rec.top.map(([k, p], i) => `<div class="arow"><span class="rk">${i + 1}</span><button data-c="${ISO[k]}">${esc(cname(ISO[k], one, true))}</button><span class="bt"><b style="width:${p}%"></b></span><span class="v">${p}</span></div>`).join('');
      const bySlug = new Map(M.groups.map(g => [g.slug, g]));
      const grows = rec.groups.map(([slug, p]) => ({g: bySlug.get(slug), p})).filter(x => x.g).sort((a, b) => b.p - a.p)
        .map(x => `<div class="grow${x.g.members.includes(c) ? ' own' : ''}" data-g="${x.g.slug}" data-p="${x.p}"><span>${esc(optShort(OPT.get('g:' + x.g.slug)))}</span><span class="tk"><i style="left:${x.p}%"></i></span><span class="v">${x.p}</span></div>`).join('');
      $('align').innerHTML = `<div class="acols"><div><h3>${t('similar')}</h3>${rows}</div><div><h3>${t('closeness')}</h3>${grows}</div></div>`;
      $('align').querySelectorAll('.arow button').forEach(b => b.onclick = () => { state.country = +b.dataset.c; $('countrySel').value = state.country; update(); });
      $('align').querySelectorAll('.grow').forEach(r => { r.onmousemove = e => showTip(e, `<b>${esc(optLabel(OPT.get('g:' + r.dataset.g)))}</b><br>${r.dataset.p} / 100`); r.onmouseleave = hideTip; });
    }
  }
  $('ctyMapHint').textContent = state.layer === 'speech' ? t(ys.length > 1 ? 'mapHintSpeechAll' : 'mapHintSpeech') : t('mapHintFrag');
  // excerpts: its most present UNODC lenses in the period, the most recent passage for each
  const qb = $('ctyQuotes'), ex = empty ? null : want('excerpts/all.json');
  if (empty || !ex) qb.innerHTML = `<div class="empty">${empty || waitMsg('excerpts/all.json')}</div>`;
  else {
    const byLens = new Map();
    for (const q of candidates(ex, [c])) if (!byLens.has(q.l)) byLens.set(q.l, q);
    const out = [...byLens.values()].sort((a, b) => (cmOf(b.l)[c] ?? 0) - (cmOf(a.l)[c] ?? 0)).slice(0, 3);
    qb.innerHTML = out.length ? out.map(q => quoteHTML(q, 'var(--s1)')).join('') : `<div class="empty">${t('noU')}</div>`;
  }
}

// ---------------- language ----------------
function applyLang() {
  document.documentElement.lang = lang; setFormats();
  document.title = t('title');
  document.querySelectorAll('[data-i]').forEach(el => { el.textContent = t(el.dataset.i); });
  $('langES').setAttribute('aria-pressed', lang === 'es'); $('langEN').setAttribute('aria-pressed', lang === 'en');
  $('langSeg').setAttribute('aria-label', t('langLabel'));
  yFrom.setAttribute('aria-label', t('yearFrom')); yTo.setAttribute('aria-label', t('yearTo'));
  document.querySelector('.tabbar').setAttribute('aria-label', t('views'));
  $('controls').setAttribute('aria-label', t('filters'));
  // a development build, or a build whose lenses have not all been through the validation test (pass: null)
  const badge = $('badge'), dev = M.build.placeholder, prelim = !dev && LENSES.some(l => l.pass == null);
  badge.hidden = !dev && !prelim; badge.textContent = t(dev ? 'devBadge' : 'prelimBadge');
  badge.title = prelim ? t('prelimTip') : ''; badge.classList.toggle('dev', dev);
  fillSelects(); update();
}

// ---------------- update ----------------
function update() {
  CM = {};
  $('allYears').setAttribute('aria-pressed', isAll());
  document.querySelector('.years').dataset.all = isAll();
  const f = y => (y - Y0) / (Y1 - Y0), fill = document.querySelector('.yrange .fill');
  fill.style.left = `calc(7px + (100% - 14px) * ${f(state.y0)})`; fill.style.width = `calc((100% - 14px) * ${f(state.y1) - f(state.y0)})`;
  $('yearOut').textContent = per();
  computeSlots(); drawLegends();
  if (state.tab === 'reg') { drawStrip(); regMap.draw(); drawWorld(); drawTrend(); drawWords(); drawQuotes(); }
  else { drawCountry(); ctyMap.draw(); }
}
addEventListener('hashchange', () => { if (applyHash()) { fillSelects(); setTab('reg'); } });
applyHash();
$('boot').hidden = true; $('controls').hidden = false;
setFormats(); applyLang(); setTab(state.tab);
const redraw = () => { regMap.invalidate(); ctyMap.invalidate(); update(); };
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redraw);
new MutationObserver(redraw).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
document.fonts?.ready.then(() => { regMap.draw(); ctyMap.draw(); });
})();
