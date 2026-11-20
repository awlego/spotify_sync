// Small DOM + formatting helpers. Every name from the data goes in via textContent.
const d3 = window.d3;

export const fmt = d3.format(',');
export const pct = d3.format('.0%');
export const parseDay = d3.utcParse('%Y-%m-%d');
export const isoDay = d3.utcFormat('%Y-%m-%d');
export const longDay = d3.utcFormat('%b %-d, %Y');
export const monthYear = d3.utcFormat('%b %Y');
export const weekday = d3.utcFormat('%A');

export function compact(n) {
  return n >= 10000 ? d3.format('.3~s')(n).replace('G', 'B') : fmt(n);
}

export function ordinal(n) {
  const s = ['th', 'st', 'nd', 'rd'], v = n % 100;
  return fmt(n) + (s[(v - 20) % 10] || s[v] || s[0]);
}

export function plural(n, one, many = one + 's') {
  return `${fmt(n)} ${n === 1 ? one : many}`;
}

/** h('a', {href, class}, 'text', child, ...) — strings become text nodes, never HTML. */
export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? '' : v);
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

/** Build a paragraph from a template of strings and nodes: p`You played ${strong(n)} songs`. */
export function sentence(strings, ...values) {
  const out = [];
  strings.forEach((s, i) => {
    out.push(s);
    if (i < values.length) out.push(values[i]);
  });
  return out;
}

export const strong = (t) => h('strong', {}, t);

export const artistLink = (a) => h('a', { href: `#/artist/${a.id}` }, a.name);
export const songLink = (s) => h('a', { href: `#/song/${s.id}` }, s.title);

/* ------------------------------------------------------------- tooltip */

const tipEl = document.querySelector('.tip');

export const tip = {
  /** rows: [{v, l, key}] — value leads, label follows; key = 's1' | 's2' for a line key */
  show(event, rows, title) {
    tipEl.replaceChildren();
    if (title) tipEl.append(h('div', { class: 'l' }, title));
    for (const r of rows) {
      tipEl.append(h('div', { class: 'row' },
        r.key ? h('span', { class: `line-key ${r.key}` }) : null,
        h('span', { class: 'v' }, r.v),
        r.l ? h('span', { class: 'l' }, r.l) : null));
    }
    tipEl.hidden = false;
    let x, y;
    if (event.clientX !== undefined && event.type !== 'focus') { x = event.clientX; y = event.clientY; }
    else { const b = event.target.getBoundingClientRect(); x = b.right; y = b.top; }
    const w = tipEl.offsetWidth, ht = tipEl.offsetHeight;
    const left = x + 14 + w > window.innerWidth - 8 ? x - w - 14 : x + 14;
    const top = Math.max(8, Math.min(y - ht - 10, window.innerHeight - ht - 8));
    tipEl.style.left = `${Math.max(8, left)}px`;
    tipEl.style.top = `${top < 8 ? y + 16 : top}px`;
  },
  hide() { tipEl.hidden = true; },
};

/* ------------------------------------------------------------- figure */

/**
 * A chart with a "Show as table" twin. draw(chartEl) renders the chart;
 * table = {head: [...], rows: [[...]], numeric: [colIndexes]}.
 */
export function figure({ label, draw, table, legend }) {
  const chart = h('div', { class: 'chart', role: 'img', 'aria-label': label });
  const holder = h('div');
  let open = false;
  const toggle = h('button', { type: 'button', class: 'table-toggle', 'aria-expanded': 'false' }, 'Show as table');
  toggle.addEventListener('click', () => {
    open = !open;
    toggle.setAttribute('aria-expanded', String(open));
    toggle.textContent = open ? 'Hide table' : 'Show as table';
    holder.replaceChildren(open ? renderTable(table()) : '');
  });
  const wrap = h('div', { class: 'figure' }, chart,
    h('div', { class: 'chart-foot' }, legend || h('span'), table ? toggle : null), holder);
  wrap.draw = () => { chart.replaceChildren(); draw(chart); };
  return wrap;
}

function renderTable({ head, rows, numeric = [] }) {
  const isNum = (i) => numeric.includes(i);
  return h('div', { class: 'data-table' },
    h('table', {},
      h('thead', {}, h('tr', {}, head.map((c, i) => h('th', { class: isNum(i) ? 'n' : null, scope: 'col' }, c)))),
      h('tbody', {}, rows.map((r) => h('tr', {}, r.map((c, i) => h('td', { class: isNum(i) ? 'n' : null }, c)))))));
}

export function rampLegend(low = 'Fewer plays', high = 'More plays') {
  return h('div', { class: 'legend' },
    h('span', {}, low),
    h('span', { class: 'ramp', 'aria-hidden': 'true' },
      [0, 1, 2, 3, 4, 5, 6, 7].map((q) => h('i', { style: `background: var(${q ? `--q${q}` : '--empty'})` }))),
    h('span', {}, high));
}

/* ------------------------------------------------------------- ranked list */

/** items: [{href?, name, by?: Node|string, value, valueLabel?, note?}] */
export function rankList(items, { max, initial = 10, compactRows = false, numbered = true } = {}) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  const list = h(numbered ? 'ol' : 'ul', { class: `rank${compactRows ? ' compact' : ''}${numbered ? '' : ' plain'}` });
  const row = (it, i) => h('li', {},
    numbered ? h('span', { class: 'pos' }, String(i + 1)) : null,
    h('span', { class: 'what' },
      h('span', { class: 'name' }, it.href ? h('a', { href: it.href }, it.name) : it.name),
      it.by ? h('span', { class: 'by' }, it.by) : null),
    h('span', { class: 'val' }, it.valueLabel ?? fmt(it.value)),
    h('span', { class: 'meter', 'aria-hidden': 'true' }, h('i', { style: `width:${(100 * it.value / top).toFixed(1)}%` })));
  items.slice(0, initial).forEach((it, i) => list.append(row(it, i)));
  if (items.length <= initial) return list;
  const more = h('button', { type: 'button', class: 'more' }, `Show all ${items.length}`);
  more.addEventListener('click', () => {
    items.slice(initial).forEach((it, i) => list.append(row(it, i + initial)));
    more.remove();
  });
  return h('div', {}, list, more);
}
