// Voces de la Asamblea (docs/PLAN.md, section 3). Reads only site/data, as docs/data-contract.md describes.
(async () => {
'use strict';
const $ = id => document.getElementById(id);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
// every file revalidated on each load: a browser must not mix the files of two builds (GitHub Pages lets it keep
// them ten minutes without asking)
const fetchOk = async p => { const r = await fetch(p, {cache: 'no-cache'}); if (!r.ok) throw new Error(`${p}: ${r.status}`); return r; };
const getJSON = async p => (await fetchOk(p)).json();
const getBin = async p => (await fetchOk(p)).arrayBuffer();
const store = new Map();
function want(p) {   // a lazy data file: fetched once, on first use; the view redraws when it arrives
  let e = store.get(p);
  if (!e) {
    store.set(p, e = {value: null, failed: false});
    getJSON('data/' + p).then(v => { e.value = v; update(); tipAgain?.(); cardAgain?.(); },
      err => { e.failed = true; console.error(err); update(); cardAgain?.(); });
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
const TINY = 0.0005;   // a share under it reads "<0,1 %", too little to compare with the world's
const pct = v => v == null || !isFinite(v) ? '–' : (v > 0 && v < TINY ? '<' + nf1.format(0.1) : nf1.format(v * 100)) + (lang === 'es' ? ' %' : '%');
const ratioTxt = r => r == null || !isFinite(r) ? '–' : nf1.format(r) + '×';

// ---------------- data ----------------
const Y0 = M.years.first, Y1 = M.years.last, NY = Y1 - Y0 + 1;   // 2026 shows like any other year, with no label (docs/PLAN.md, section 2)
const LENSES = M.lenses, NL = LENSES.length, ALL = NL, NC = M.countries.length;
const TOPICS = M.topics;
const SH = new Float32Array(SHB), FRG = new Uint16Array(FRB);
const shareOf = (c, y, L) => SH[(c * NY + y) * (NL + 1) + L];
const approx = L => L !== ALL && LENSES[L].pass === false;   // short of the pass bar: shown with a badge
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
  if (h === 'anexo' || h === 'annex') { state.tab = 'anx'; return true; }
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

// ---------------- fragment card ----------------
// A fragment about a UNODC topic, opened from the map: its whole text, its speaker, and for each topic it is about
// its confidence (the model's hit rate at its probability), or "read" where the reader placed it there
// (docs/data-contract.md, cards); the column's name links to the annex, which explains both
const card = $('card');
let cardAgain = null;   // redraws the open card when its file arrives or the language changes
function openCard(i) {   // i: a fragment point
  hideTip();
  const c = PF.c[i], y = Y0 + PF.yr[i], f = `cards/${M.countries[c].iso3}.json`;
  cardAgain = () => {
    const d = want(f), e = d?.frags[i - CSTART[c]], who = d?.who[y];
    let body = `<div class="empty">${waitMsg(f)}</div>`;
    if (e) {
      const [ls, a, read, x] = e, first = state.tab === 'reg' && ls.includes(state.lens) ? state.lens : ls[0];
      const rows = [first, ...ls.filter(l => l !== first)].map(l => {   // the chosen topic first, as in the quotes
        const n = a?.[ls.indexOf(l)];
        const val = read.includes(l) ? `<span class="v rd">${esc(t('cardRead'))}</span>`
          : n != null ? `<span class="bt"><b style="width:${10 * n}%"></b></span><span class="v">${esc(t('cardOf', {n}))}</span>` : '';
        return `<li><span class="ln">${icon(LENSES[l].icon)}<span>${esc(LENSES[l][lang])}${approx(l) ? ` <small class="apx">${esc(t('apx'))}</small>` : ''}</span></span>${val}</li>`;
      }).join('');
      const conf = a != null ? `<button class="apx-link" type="button" title="${esc(t('cardConfTip'))}" aria-label="${esc(t('cardConfTip'))}">${esc(t('cardConf'))}</button>` : '';
      body = `<div class="chead"><span>${esc(t('cardTopics'))}</span>${conf}</div><ul class="crows">${rows}</ul>`
        + `<p class="ctext">“${esc(x)}” <small>EN</small></p>`;
    }
    card.innerHTML = `<div class="cin"><button class="x" type="button" aria-label="${esc(t('close'))}">×</button>
      <h2 id="cardTitle">${esc(cname(c, y))} · ${y}</h2>${who ? `<p class="who">${esc(who)}</p>` : ''}${body}</div>`;
  };
  cardAgain();
  if (!card.open) card.showModal();
}
card.addEventListener('close', () => { cardAgain = null; });
// the close button, or a click beside the card; the second click of a double click leaves it open
card.addEventListener('click', e => {
  if (e.target.closest('.apx-link')) { card.close(); toAnnex('anxUse'); }
  else if (e.detail < 2 && (e.target === card || e.target.closest('.x'))) card.close();
});

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
const TABS = {reg: ['tabReg', 'paneReg'], cty: ['tabCty', 'paneCty'], anx: ['tabAnx', 'paneAnx']};
function setTab(tab) {
  state.tab = tab;
  for (const [k, [b, p]] of Object.entries(TABS)) { $(b).setAttribute('aria-selected', k === tab); $(p).hidden = k !== tab; }
  $('ctlSlots').hidden = tab !== 'reg'; $('ctlCountry').hidden = tab !== 'cty'; $('controls').hidden = tab === 'anx';
  hideTip(); update();
}
Object.entries(TABS).forEach(([k, [b]]) => {
  $(b).addEventListener('click', () => setTab(k));
  $(b).addEventListener('keydown', e => {
    const d = {ArrowRight: 1, ArrowLeft: -1}[e.key], ks = Object.keys(TABS);
    if (d) { const n = ks[(ks.indexOf(state.tab) + d + ks.length) % ks.length]; setTab(n); $(TABS[n][0]).focus(); }
  });
});
$('icReg').innerHTML = icon('world'); $('icCty').innerHTML = icon('map-pin'); $('icAnx').innerHTML = icon('file-text');
const toAnnex = (to = 'anxAcc') => { setTab('anx'); $(to).scrollIntoView({block: 'start'}); };
// The note on a topic short of the pass bar: a link to the annex's table
const apxNote = L => approx(L) ? ` <button class="apx-link" type="button">${esc(t('apxTip'))}</button>` : '';
const wireApx = el => el.querySelectorAll('.apx-link').forEach(b => { b.onclick = () => toAnnex(); });

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
  $('stripHint').textContent = s1 ? t('stripHint', {sel: new Intl.ListFormat(lang, {type: 'conjunction'}).format(act.map(a => optShort(a.o))), per: per()}) : t('stripHintNone', {per: per()});
  const order = [ALL, ...d3.range(NL)];
  $('lenses').innerHTML = order.map(L => {
    const cls = 'lens' + (L === ALL ? ' all' : '') + (L !== ALL && LENSES[L].reference ? ' ref' : '');
    const head = `<span class="ic-row">${icon(lensIcon(L))}<span class="nm">${esc(lensName(L))}${approx(L) ? ` <small class="apx">${esc(t('apx'))}</small>` : ''}</span></span>`;
    const cm = cmOf(L), w = worldOf(cm);
    const vals = act.map(a => ({s: a.s, v: meanOf(cm, a.o.members), lab: optShort(a.o)}));
    const r = s1 && vals[0].v >= TINY && w ? vals[0].v / w : null;
    const mx = Math.max(w || 0, ...vals.map(x => x.v || 0)) * 1.15 || 1;
    // every selection's value, a dot of its colour when there are several (the ratio is the first selection's)
    const parts = vals.map(x => ({s: x.s, txt: `${x.lab} ${pct(x.v)}`})).concat([{s: -1, txt: `${t('world')} ${pct(w)}`}]);
    const sw = s => s >= 0 && vals.length > 1 ? `<i class="sw" style="background:var(--s${s + 1})"></i>` : '';
    return `<button class="${cls}" data-l="${L}" aria-pressed="${state.lens === L}" aria-label="${esc(lensName(L))}${approx(L) ? ` (${esc(t('apxTip'))})` : ''}: ${r != null ? esc(ratioTxt(r) + ' ' + t('timesWorld')) + '. ' : ''}${esc(parts.map(x => x.txt).join(' · '))}">
      ${head}<span class="rt">${ratioTxt(r)}<small>${r != null ? t('timesWorld') : ''}</small></span>
      ${dumbbell(vals, w, mx)}<span class="vals">${parts.map(x => `<span>${sw(x.s)}${esc(x.txt)}</span>`).join(' · ')}</span></button>`;
  }).join('');
  $('lenses').querySelectorAll('.lens').forEach(b => {
    const L = +b.dataset.l;
    b.onclick = () => { state.lens = L; update(); };
    b.onmousemove = e => {
      const cm = cmOf(L);
      showTip(e, `<b>${esc(lensName(L))}</b><br>` + active().map(a => `${esc(optShort(a.o))}: ${pct(meanOf(cm, a.o.members))}`).concat([`${t('world')}: ${pct(worldOf(cm))}`]).join('<br>')
        + (approx(L) ? `<br><span class="tl">${esc(t('apxTip'))}</span>` : ''));
    };
    b.onmouseleave = hideTip;
  });
}

// ---------------- semantic maps ----------------
const coarse = matchMedia('(pointer: coarse)').matches;
const qtCache = {};
const quadtree = sp => {   // the points of the chosen years, the only ones drawn
  const k = state.y0 + '|' + state.y1, P = sp ? PS : PF;
  if (qtCache[sp]?.k !== k) qtCache[sp] = {k, t: d3.quadtree().x(i => P.x[i]).y(i => P.y[i]).addAll(d3.range(P.n).filter(i => inP(P.yr[i])))};
  return qtCache[sp].t;
};
function SemMap(wrap, layersOf) {
  const cv = wrap.querySelector('canvas'), ctx = cv.getContext('2d'), rb = wrap.querySelector('.reset'), PAD = 18, IP = 4;
  let tf = d3.zoomIdentity, cw = 0, ch = 0, groups = null, key = '', inset = null, insetKey = '', insetBox = null;
  const clamp01 = v => Math.min(1, Math.max(0, v));
  const overview = (P, layers, iw, ih) => {   // the corner map: every layer's points, a pixel each, drawn once per state
    const dpr = devicePixelRatio || 1, oc = document.createElement('canvas'), o = oc.getContext('2d');
    oc.width = iw * dpr; oc.height = ih * dpr; o.setTransform(dpr, 0, 0, dpr, 0, 0);
    o.globalAlpha = 0.94; o.fillStyle = css('--panel'); o.fillRect(0, 0, iw, ih);
    layers.forEach((ly, l) => {
      o.globalAlpha = ly.alpha ?? 1; o.fillStyle = ly.col; o.beginPath();
      for (const i of groups[l]) o.rect(IP + P.x[i] * (iw - 2 * IP) - 0.4, IP + P.y[i] * (ih - 2 * IP) - 0.4, 0.8, 0.8);
      o.fill();
    });
    return oc;
  };
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
    const small = cw < 520;
    // each name at its first place that covers no name already written; a UNODC topic's name, when all its places
    // are covered, moves a line or more up or down from its first one (a sub-topic shares its parent's region)
    for (const lb of labels) {
      const label = topicName(lb.t), lensT = lb.t < NL;
      ctx.font = `${lensT ? 700 : 600} ${(lensT ? 12.5 : 11.5) - (small ? 1 : 0)}px "Roboto Condensed", "Arial Narrow", sans-serif`;
      const w = ctx.measureText(label).width + 8, h = (lensT ? 17 : 15) - (small ? 1 : 0);
      if (w > cw - 4) continue;
      const spots = [[lb.x, lb.y, 0], ...(lb.alt || []).map(([x, y]) => [x, y, 0]), ...(lensT ? [1, -1, 2, -2, 3, -3].map(n => [lb.x, lb.y, n]) : [])];
      for (const [ax, ay, lines] of spots) {
        let X = sx(ax), Y = sy(1 - ay) + lines * h;
        if (X < 0 || X > cw || Y < 0 || Y > ch) continue;
        X = Math.min(Math.max(X, w / 2 + 2), cw - w / 2 - 2); Y = Math.min(Math.max(Y, h / 2 + 2), ch - h / 2 - 2);
        const box = [X - w / 2 + 1, Y - h / 2 + 1, X + w / 2 - 1, Y + h / 2 - 1];   // names may touch, never overlap
        if (placed.some(b => !(box[2] < b[0] || box[0] > b[2] || box[3] < b[1] || box[1] > b[3]))) continue;
        placed.push(box);
        ctx.lineWidth = 3.5; ctx.strokeStyle = bg; ctx.strokeText(label, X, Y);
        ctx.fillStyle = lensT ? unt : ink2; ctx.fillText(label, X, Y);
        break;
      }
    }
    insetBox = null;
    if (tf.k >= 2) {   // zoomed in: the whole map in a corner, the part in view outlined
      const iw = Math.round(Math.min(170, Math.max(110, cw * 0.26))), ih = Math.round(iw * ch / cw), ix = 8, iy = ch - ih - 8;
      const ik = [k, iw, ih, ...spec.layers.map(ly => ly.col)].join('|');
      if (insetKey !== ik) { inset = overview(P, spec.layers, iw, ih); insetKey = ik; }
      ctx.drawImage(inset, ix, iy, iw, ih);
      ctx.lineWidth = 1; ctx.strokeStyle = css('--line'); ctx.strokeRect(ix + 0.5, iy + 0.5, iw - 1, ih - 1);
      const fx = X => ix + IP + clamp01((tf.invertX(X) - PAD) / (cw - 2 * PAD)) * (iw - 2 * IP);
      const fy = Y => iy + IP + clamp01((tf.invertY(Y) - PAD) / (ch - 2 * PAD)) * (ih - 2 * IP);
      ctx.lineWidth = 1.5; ctx.strokeStyle = css('--ink'); ctx.strokeRect(fx(0), fy(0), fx(cw) - fx(0), fy(ch) - fy(0));
      insetBox = [ix, iy, ix + iw, iy + ih];
    }
    rb.hidden = tf.k === 1 && tf.x === 0 && tf.y === 0;
  };
  const zoom = d3.zoom().scaleExtent([1, 24]).on('zoom', e => { tf = e.transform; hideTip(); this.draw(); });
  if (!coarse) d3.select(cv).call(zoom);
  const inBox = (mx, my) => insetBox && mx >= insetBox[0] && mx <= insetBox[2] && my >= insetBox[1] && my <= insetBox[3];
  cv.addEventListener('click', e => {   // a click on the corner map centres the view there; on a point, opens its card
    const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    if (!inBox(mx, my)) { const i = pick(e), f = i == null ? null : opens(i); if (f != null) openCard(f); return; }
    const x = clamp01((mx - insetBox[0] - IP) / (insetBox[2] - insetBox[0] - 2 * IP)), y = clamp01((my - insetBox[1] - IP) / (insetBox[3] - insetBox[1] - 2 * IP));
    d3.select(cv).call(zoom.translateTo, PAD + x * (cw - 2 * PAD), PAD + y * (ch - 2 * PAD));
  });
  rb.addEventListener('click', () => { d3.select(cv).call(zoom.transform, d3.zoomIdentity); tf = d3.zoomIdentity; this.draw(); });
  let topKey = '', topTree = null;
  const pick = e => {
    const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    if (inBox(mx, my)) return null;   // the corner map hides the points beneath it
    const dx = (tf.invertX(mx) - PAD) / (cw - 2 * PAD), dy = (tf.invertY(my) - PAD) / (ch - 2 * PAD), rad = (coarse ? 14 : 8) / (tf.k * (cw - 2 * PAD));
    const P = state.layer === 'speech' ? PS : PF;
    if (groups && topKey !== key) { topTree = d3.quadtree().x(i => P.x[i]).y(i => P.y[i]).addAll(groups.slice(2).flat()); topKey = key; }
    return topTree?.find(dx, dy, rad) ?? quadtree(state.layer === 'speech').find(dx, dy, rad);   // the highlighted points first: they are drawn on top
  };
  // the fragment a point opens: a fragment about a UNODC topic, or a speech's most probable one (its hover passage)
  const opens = i => {
    if (state.layer !== 'speech') return PF.m[i] ? i : null;
    const k = want('speeches.json')?.[M.countries[PS.c[i]].iso3]?.[Y0 + PS.yr[i]]?.[3];
    return k >= 0 ? CSTART[PS.c[i]] + k : null;
  };
  const hover = e => {
    const i = pick(e); if (i == null) { cv.style.cursor = ''; return hideTip(); }
    const open = opens(i) != null, more = open && e.pointerType === 'mouse' ? `<span class="more">${esc(t('cardHint'))}</span>` : '';
    cv.style.cursor = open ? 'pointer' : '';
    if (state.layer === 'speech') {
      const c = PS.c[i], y = Y0 + PS.yr[i], iso = M.countries[c].iso3;
      const comp = want('composition.json'), sp = want('speeches.json');
      const parts = comp ? (comp[iso]?.[y] || []).slice(0, 3).map(([k, v]) => `${esc(topicName(k))} ${pct(v)}`).join(' · ') : waitMsg('composition.json');
      const [, rep, rl] = sp?.[iso]?.[y] || [];
      const on = rep && rl >= 0 ? `<span class="ql">${icon(LENSES[rl].icon)}${esc(LENSES[rl][lang])}</span>` : '';
      showTip(e, `<b>${esc(cname(c, y))} · ${y}</b><br>${parts}${rep ? `<q>${on}“${esc(rep)}”</q>` : ''}${more}`);
    } else {
      const c = PF.c[i], y = Y0 + PF.yr[i], m = PF.m[i], ls = [];
      for (let j = 0; j < NL; j++) if (m & (1 << j)) ls.push(LENSES[j][lang]);
      const f = `snips/${M.countries[c].iso3}.json`, sn = want(f), txt = sn?.[i - CSTART[c]];
      showTip(e, `<b>${esc(cname(c, y))} · ${y}</b><br><span class="tl">${esc(ls.length ? ls.slice(0, 2).join(' · ') : topicName(PF.t[i]))}</span>`
        + (txt ? `<q>“${esc(txt)}”</q>` : `<q>${waitMsg(f)}</q>`) + more);
    }
    tipAgain = () => hover(e);
  };
  cv.addEventListener('pointermove', e => { if (e.pointerType === 'mouse') hover(e); });
  cv.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse') hover(e); });
  cv.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') { hideTip(); cv.style.cursor = ''; } });
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
// A selection's points about topic L (a speech: if any of its fragments is)
const onTopic = (P, L) => { const b = L === ALL ? 0xffff : 1 << L; return i => (P.m[i] & b) !== 0; };
// Only the period's points, back to front: the rest of the world in light grey, the selections' points in dark
// grey, and in each selection's colour its points about the chosen topic
const regMap = new SemMap($('regMapWrap'), sp => {
  const P = sp ? PS : PF, on = onTopic(P, state.lens);
  const alpha = isAll() ? (sp ? 0.8 : 0.55) : 1, bump = isAll() ? 0 : (sp ? 0.6 : 0.3);
  const layers = [{col: css('--dot')}, {col: css('--dot-sel'), alpha, bump}, ...[2, 1, 0].map(s => ({col: slotCol(s), alpha, bump}))];
  return {layers, key: [state.y0, state.y1, state.slots.join(','), state.lens, css('--dot'), css('--dot-sel')].join('|'),
    layerOf: i => { if (!inP(P.yr[i])) return -1; const s = cSlot[P.c[i]]; return s < 0 ? 0 : on(i) ? 4 - s : 1; }};
});
const ctyMap = new SemMap($('ctyMapWrap'), sp => {   // the country tab has no topic choice: all UNODC topics
  const P = sp ? PS : PF, c = state.country, on = onTopic(P, ALL), dot = {bump: sp ? 2 : 1.9, round: true, ring: css('--panel')};
  return {layers: [{col: css('--dot')}, {col: css('--dot-sel'), ...dot}, {col: css('--s1'), ...dot}],
    key: [c, state.y0, state.y1, css('--dot'), css('--dot-sel')].join('|'), layerOf: i => !inP(P.yr[i]) ? -1 : P.c[i] !== c ? 0 : on(i) ? 2 : 1};
});
function drawLegends() {
  const other = t(state.layer === 'speech' ? 'otherSpeech' : 'otherFrag');   // the selection's points not about the topic
  const sw = (col, txt) => `<span><i style="background:${col}"></i>${esc(txt)}</span>`, lead = L => `<span class="lt">${esc(lensName(L))}:</span>`;
  const sel = active().map(({s, o}) => sw(`var(--s${s + 1})`, optShort(o)));
  const topic = sel.length ? [lead(state.lens), ...sel, sw('var(--dot-sel)', other)] : sel;
  $('regLegend').innerHTML = [...topic, sw('var(--dot)', t('rest'))].join('');
  state.slots.forEach((v, s) => { const o = OPT.get(v); $('slot' + s).title = o?.g ? [...o.members].map(c => cname(c)).sort((a, b) => a.localeCompare(b, lang)).join(', ') : ''; });   // a group's members on hover
  $('ctyLegend').innerHTML = [lead(ALL), sw('var(--s1)', cname(state.country)), sw('var(--dot-sel)', other), sw('var(--dot)', t('rest'))].join('');
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
const STEPS = [0.01, 0.05, 0.1, 0.2];   // the world map's classes, the same for every topic: under 1 %, 1–5, 5–10, 10–20, 20 % or more
function drawWorld() {
  const L = state.lens, cm = cmOf(L);
  const cols = ['--q0', '--q1', '--q2', '--q3', '--q4'].map(css), nod = css('--nodata'), line = css('--land-line');
  const colOf = v => v == null ? nod : cols[d3.bisectRight(STEPS, v)];
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
  const tipOf = (e, c) => c == null ? hideTip() : showTip(e, `<b>${esc(cname(c, single()))}</b><br>${cm[c] == null ? t('noSpeech') : pct(cm[c])}`);
  wpaths.on('mousemove', (e, f) => tipOf(e, cOfFeat(f))).on('mouseleave', hideTip);
  wdots.on('mousemove', (e, d) => tipOf(e, d.c)).on('mouseleave', hideTip);
  const title = L === ALL ? t('worldTitleAll') : t('worldTitle', {l: inSentence(lensName(L))});
  wsvg.attr('aria-label', title); $('worldTitle').textContent = title;
  $('worldHint').innerHTML = esc(single() != null ? t('yearN', {y: single()}) : t('avg', {per: per()})) + apxNote(L); wireApx($('worldHint'));
  const sels = active().map(({s, o}) => `<span><i class="ol" style="border-color:var(--s${s + 1})"></i><em>${esc(optShort(o))}</em></span>`).join('');
  const tick = v => Math.round(v * 100) + (lang === 'es' ? '\u00a0%' : '%');   // at the joins of the 34-pixel steps
  $('worldScale').innerHTML = `<span class="ramp">${cols.map(c => `<i style="background:${c}"></i>`).join('')}${STEPS.map((v, k) => `<b style="left:${36 * k + 35}px">${tick(v)}</b>`).join('')}</span>`
    + `<i style="background:${nod}"></i><em>${t('noSpeech')}</em>`
    + (sels && `<span class="sels">${sels}</span>`);   // the selections' outlines on a line of their own
}

// ---------------- trend ----------------
let TW = 640; const TH = 250, TM = {t: 12, r: 96, b: 24, l: 40};
const tsvg = d3.select('#trend').append('svg').attr('viewBox', `0 0 ${TW} ${TH}`).attr('role', 'img');
const tx = d3.scaleLinear().domain([Y0, Y1]).range([TM.l, TW - TM.r]), ty = d3.scaleLinear().range([TH - TM.b, TM.t]);
const gGrid = tsvg.append('g'), gAx = tsvg.append('g'), gLines = tsvg.append('g'), gMark = tsvg.append('g'), gHover = tsvg.append('g');
let series = [];
function seriesFor(members, L) {   // each year's equal-weight mean, the value a card shows for that year
  return d3.range(NY).map(y => { let a = 0, k = 0; for (let c = 0; c < NC; c++) { if (members && !members.has(c)) continue; const v = shareOf(c, y, L); if (!Number.isNaN(v)) { a += v; k++; } } return k ? a / k : null; });
}
function drawTrend() {
  const L = state.lens, title = L === ALL ? t('trendTitleAll') : t('trendTitle', {l: lensName(L)});
  $('trendTitle').textContent = title; tsvg.attr('aria-label', title);
  $('trendHint').innerHTML = esc(t('trendHint')) + apxNote(L); wireApx($('trendHint'));
  TW = Math.max(300, Math.round($('trend').clientWidth || 640)); TM.r = TW < 480 ? 80 : 96;
  tsvg.attr('viewBox', `0 0 ${TW} ${TH}`); tx.range([TM.l, TW - TM.r]);
  gGrid.selectAll('*').remove(); gAx.selectAll('*').remove(); gLines.selectAll('*').remove(); gMark.selectAll('*').remove();
  series = active().map(({s, o}) => ({name: optShort(o), col: slotCol(s), v: seriesFor(o.members, L)}));
  series.push({name: t('world'), col: css('--world'), v: seriesFor(null, L), dash: '4 3'});
  const mx = d3.max(series, s => d3.max(s.v)) || 0.01;
  ty.domain([0, mx * 1.08]).nice(4);
  const muted = css('--muted');
  gGrid.selectAll('line').data(ty.ticks(4)).join('line').attr('x1', TM.l).attr('x2', TW - TM.r).attr('y1', d => ty(d)).attr('y2', d => ty(d)).attr('stroke', css('--line-2'));
  const yt = ty.ticks(4), yf = new Intl.NumberFormat(lang, {style: 'percent', maximumFractionDigits: yt[1] - yt[0] < 0.01 ? 1 : 0});   // decimals when the step is under 1%
  gAx.selectAll('text.y').data(yt).join('text').attr('class', 'y').attr('x', TM.l - 6).attr('y', d => ty(d)).attr('dy', '0.32em').attr('text-anchor', 'end').attr('fill', muted).attr('font-size', 11).text(d => yf.format(d));
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
const quoteHTML = (q, colVar) => `<div class="quote" style="--c:${colVar}"><div class="meta">${esc(cname(q.c, q.y))} · ${q.y}${q.ls.map(l => `<span class="ln">${icon(lensIcon(l))}${esc(LENSES[l][lang])}</span>`).join('')}<small>EN</small></div><p>“${esc(q.x)}”</p></div>`;
function candidates(data, members) {   // the members' excerpts in the period, most probable first, then most recent
  const out = [];
  for (const c of members) {
    const byYear = data[M.countries[c].iso3]; if (!byYear) continue;
    for (const y of yearsInP()) for (const [ls, p, x] of byYear[y] || []) out.push({c, y, l: ls[0], ls, p, x});
  }
  return out.sort((a, b) => b.p - a.p || b.y - a.y);
}
function drawQuotes() {
  const box = $('quotes'), act = active();
  if (!act.length) return box.innerHTML = `<div class="empty">${t('pickSel')}</div>`;
  const file = `excerpts/${lensFile(state.lens)}.json`, data = want(file);
  if (!data) return box.innerHTML = `<div class="empty">${waitMsg(file)}</div>`;
  const pools = act.map(({s, o}) => candidates(data, o.members).map(q => ({...q, slot: s})));
  const out = [], used = new Set(), key = q => `${q.c}|${q.y}|${q.x}`;   // each selection's most probable, in turns
  for (let round = 0; out.length < 3 && round < 3; round++) for (const pool of pools) {
    if (out.length >= 3) break;
    const q = pool.find(x => !used.has(key(x))); if (q) { used.add(key(q)); out.push(q); }
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

// ---------------- technical annex (meta.method) ----------------
function drawAnnex() {
  const A = M.method, box = $('annex');
  if (!A) return box.innerHTML = `<div class="empty">${esc(t('anxNone'))}</div>`;   // a build without the final fit
  const nf = new Intl.NumberFormat(lang), n = v => v == null ? '–' : nf.format(v);
  const pc = v => v == null ? '–' : Math.round(v * 100) + (lang === 'es' ? '\u00a0%' : '%');
  // a text whose values are set in bold
  const tb = (k, v = {}) => esc(I18N[lang][k] ?? k).replace(/\{(\w+)\}/g, (_, x) => v[x] == null ? '' : `<b>${esc(v[x])}</b>`);
  const lf = type => new Intl.ListFormat(lang, {type});
  const steps = [
    ['s1', {speeches: n(M.build.n_speeches), first: Y0, last: Y1, countries: n(NC)}],
    ['s2', {all: n(A.fragments_all), ceremonial: n(A.ceremonial), fragments: n(M.build.n_fragments)}],
    ['s3', {}],
    ['s4', {labelled: n(A.labelled), read: A.lenses.length + A.reference.length, unodc: A.lenses.length,
            ref: lf('conjunction').format(A.reference.map(r => inSentence(r[lang]))), checked: n(A.read_twice)}],
    ['s5', {models: A.lenses.length}],
    ['s6', {folds: A.folds, rest: A.folds - 1}],
    ['s7', {general: TOPICS.filter(x => x.kind === 'general').length}],
  ].map(([k, v], i) => `<li><span class="n">${i + 1}</span><div><h3>${esc(t(k + 't'))}</h3><p>${tb(k, v)}</p></div></li>`).join('');
  const st = l => l.pass === false ? 'apx' : 'ok';
  const bar = v => `<td class="pr"><span class="pv">${pc(v)}</span><span class="pb" aria-hidden="true"><b style="width:${(100 * Math.min(1, v ?? 0)).toFixed(1)}%"></b><i style="left:${100 * A.bar}%"></i></span></td>`;
  const chip = l => `<span class="st st-${st(l)}">${esc(t('st_' + st(l)))}</span>`;   // on phones, under the name
  const rows = A.lenses.map(l => `<tr class="${st(l)}"><th scope="row"><span class="tn">${icon(l.icon)}${esc(l[lang])}</span>${chip(l)}</th>
    <td class="num">${n(l.examples)}</td><td class="num">${pc(l.precision)}</td><td class="num">${pc(l.recall)}</td>${bar(l.f1)}<td>${chip(l)}</td></tr>`).join('');
  const states = [['ok', {bar: pc(A.bar)}], ['apx', {}]]
    .map(([k, v]) => `<li><span class="st st-${k}">${esc(t('st_' + k))}</span><span>${tb('st_' + k + 'D', v)}</span></li>`).join('');
  const th = (k, cls = '') => `<th scope="col"${cls && ` class="${cls}"`}>${esc(t(k))}</th>`;
  const subs = A.lenses.filter(l => l.parent), top = subs.length && A.lenses.find(l => l.id === subs[0].parent);
  const use = [tb('use1'), tb('use2'), top ? esc(t('use3', {subs: lf('disjunction').format(subs.map(l => inSentence(l[lang]))), p: inSentence(top[lang])})) : '', tb('use4')]
    .filter(Boolean).map(x => `<li>${x}</li>`).join('');
  box.innerHTML = `<section class="panel"><h2>${esc(t('anxTitle'))}</h2><p class="hint">${esc(t('anxIntro'))}</p><ol class="steps">${steps}</ol></section>
  <section class="panel" id="anxAcc"><h2>${esc(t('accTitle'))}</h2><p class="hint">${tb('accHint', {labelled: n(A.labelled)})}</p>
    <dl class="defs">${[['accEx', 'accExD'], ['accPrecT', 'accPrec'], ['accRecT', 'accRec'], ['accF1T', 'accF1']].map(([a, b]) => `<div><dt>${esc(t(a))}</dt><dd>${esc(t(b))}</dd></div>`).join('')}</dl>
    <div class="tscroll"><table class="acc main"><thead><tr>${th('accTopic')}${th('accEx', 'num')}${th('accPrecT', 'num')}${th('accRecT', 'num')}${th('accF1T')}${th('accSite')}</tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">${tb('accBarNote', {bar: pc(A.bar), min: A.min_period})}</p>
    <ul class="states">${states}</ul>
  </section>
  <div class="bottom"><section class="panel" id="anxUse"><h2>${esc(t('useT'))}</h2><ul class="plain">${use}</ul></section>
    <section class="panel"><h2>${esc(t('limT'))}</h2><ul class="plain">${['lim1', 'lim2', 'lim3', 'lim4'].map(k => `<li>${esc(t(k))}</li>`).join('')}</ul></section></div>`;
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
  // a development build; or a build whose lenses have no pass-bar result (pass: null), or a preliminary
  // publication (scripts/publish_site.sh --preliminary asks search engines not to index it)
  const prelimCopy = !!document.querySelector('meta[name="robots"][content~="noindex"]');
  const badge = $('badge'), dev = M.build.placeholder, prelim = !dev && (prelimCopy || LENSES.some(l => l.pass == null));
  badge.hidden = !dev && !prelim; badge.textContent = t(dev ? 'devBadge' : 'prelimBadge');
  badge.title = prelim ? t('prelimTip') : ''; badge.classList.toggle('dev', dev);
  fillSelects(); update(); cardAgain?.();
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
  if (state.layer === 'speech') want('speeches.json');   // its entries say which card a speech point opens
  if (state.tab === 'reg') { drawStrip(); regMap.draw(); drawWorld(); drawTrend(); drawWords(); drawQuotes(); }
  else if (state.tab === 'cty') { drawCountry(); ctyMap.draw(); }
  else drawAnnex();
}
addEventListener('hashchange', () => { if (applyHash()) { fillSelects(); setTab(state.tab); } });
applyHash();
$('boot').remove(); $('controls').hidden = false;
setFormats(); applyLang(); setTab(state.tab);
const redraw = () => { regMap.invalidate(); ctyMap.invalidate(); update(); };
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redraw);
new MutationObserver(redraw).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
document.fonts?.ready.then(() => { regMap.draw(); ctyMap.draw(); });
})();
