// D3 charts. Colors come from CSS classes/variables so themes switch without re-rendering.
import { compact, fmt, isoDay, longDay, monthYear, parseDay, tip } from './ui.js';

const d3 = window.d3;
const DAY = 864e5;

function svgIn(el, width, height) {
  return d3.select(el).append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('width', width).attr('height', height)
    .attr('aria-hidden', 'true');
}

function yGrid(g, y, width, ticks = 3, format = compact) {
  const t = y.ticks(ticks);
  g.append('g').attr('class', 'grid').selectAll('line').data(t).join('line')
    .attr('x1', 0).attr('x2', width).attr('y1', y).attr('y2', y);
  g.append('g').selectAll('text').data(t).join('text')
    .attr('x', -8).attr('y', y).attr('dy', '0.32em').attr('text-anchor', 'end').text(format);
}

/** Fit text into maxWidth, adding an ellipsis if needed. */
function fitText(sel, maxWidth) {
  sel.each(function () {
    const node = this;
    let s = node.textContent;
    if (node.getComputedTextLength() <= maxWidth) return;
    while (s.length > 1 && node.getComputedTextLength() > maxWidth) {
      s = s.slice(0, -1);
      node.textContent = `${s.trimEnd()}…`;
    }
  });
}

/* --------------------------------------------------------------- the river */

/**
 * Weekly plays across the whole history, the artist that defined each year,
 * and a brush to pick a range. onBrush([startISO, endISO] | null) fires on brush end.
 */
export function river(el, { weeks, eras, range, onBrush }) {
  const width = Math.max(320, el.clientWidth);
  const narrow = width < 640;
  const m = { top: narrow ? 10 : 46, right: 8, bottom: 26, left: 40 };  // era labels only fit when wide
  const height = narrow ? 190 : 250;
  const w = width - m.left - m.right, ht = height - m.top - m.bottom;
  // Bin weeks so there's roughly one point per 3px; plot the average plays per week in each bin
  const per = Math.max(1, Math.round((3 * weeks.length) / w));
  const data = d3.range(0, weeks.length, per).map((i) => {
    const chunk = weeks.slice(i, i + per);
    return { date: parseDay(chunk[0].w), end: parseDay(chunk[chunk.length - 1].w), n: d3.mean(chunk, (d) => d.n), weeks: chunk.length };
  });
  const x = d3.scaleUtc([data[0].date, new Date(+parseDay(weeks[weeks.length - 1].w) + 7 * DAY)], [0, w]);
  const y = d3.scaleLinear([0, d3.max(data, (d) => d.n)], [ht, 0]).nice();

  const svg = svgIn(el, width, height);
  const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
  yGrid(g, y, w);

  const area = d3.area().x((d) => x(d.date)).y0(ht).y1((d) => y(d.n)).curve(d3.curveMonotoneX);
  const line = d3.line().x((d) => x(d.date)).y((d) => y(d.n)).curve(d3.curveMonotoneX);
  g.append('path').attr('class', 'area').attr('d', area(data));
  g.append('path').attr('class', 'line').attr('d', line(data));

  // Year axis
  const ax = g.append('g').attr('class', 'axis').attr('transform', `translate(0,${ht})`)
    .call(d3.axisBottom(x).ticks(narrow ? d3.utcYear.every(3) : d3.utcYear.every(1)).tickSizeOuter(0)
      .tickFormat(narrow ? d3.utcFormat('%Y') : d3.utcFormat("'%y")));
  ax.selectAll('.tick line').attr('y2', 4);

  // Era labels: the artist that defined each year, staggered on two rows
  if (!narrow) {
    const lab = g.append('g').attr('class', 'era');
    const yearW = x(new Date(Date.UTC(2001, 0, 1))) - x(new Date(Date.UTC(2000, 0, 1)));
    eras.forEach((e, i) => {
      const cx = Math.max(0, Math.min(w, x(parseDay(e.peak))));
      const row = i % 2;
      const yy = row ? -12 : -30;
      lab.append('line').attr('x1', cx).attr('x2', cx).attr('y1', yy + 4).attr('y2', 0);
      const t = lab.append('text').attr('x', cx).attr('y', yy).attr('text-anchor', 'middle').text(e.artist.name);
      fitText(t, Math.max(40, yearW * 2 - 10));
    });
  }

  // Dim outside the selected range
  const dimL = g.append('rect').attr('class', 'dim').attr('y', 0).attr('height', ht);
  const dimR = g.append('rect').attr('class', 'dim').attr('y', 0).attr('height', ht);
  const dim = (sel) => {
    const [a, b] = sel || [0, w];
    dimL.attr('x', 0).attr('width', Math.max(0, a));
    dimR.attr('x', b).attr('width', Math.max(0, w - b));
  };

  const brush = d3.brushX().extent([[0, 0], [w, ht]])
    .on('brush', ({ selection }) => dim(selection))
    .on('end', ({ selection, sourceEvent }) => {
      if (!sourceEvent) return;  // programmatic moves don't refetch
      if (!selection) { dim(null); onBrush(null); return; }
      const s = d3.utcMonday.floor(x.invert(selection[0]));
      const e = new Date(+d3.utcMonday.ceil(x.invert(selection[1])) - DAY);
      bg.call(brush.move, [x(s), x(new Date(+e + DAY))]);
      dim([x(s), x(new Date(+e + DAY))]);
      onBrush([isoDay(s), isoDay(e)]);
    });
  const bg = g.append('g').attr('class', 'brush').call(brush);
  if (range) {
    const sel = [x(parseDay(range[0])), x(new Date(+parseDay(range[1]) + DAY))];
    bg.call(brush.move, sel);
    dim(sel);
  } else dim(null);

  // Crosshair readout on the week under the pointer
  const bisect = d3.bisector((d) => d.date).left;
  const cross = g.append('line').attr('class', 'crosshair').attr('y1', 0).attr('y2', ht).attr('opacity', 0);
  const dot = g.append('circle').attr('class', 'dot s1').attr('r', 4).attr('opacity', 0);
  svg.on('pointermove', (event) => {
    const [px] = d3.pointer(event, g.node());
    if (px < 0 || px > w) return;
    const i = Math.max(0, Math.min(data.length - 1, bisect(data, x.invert(px)) - 1));
    const d = data[i];
    cross.attr('x1', x(d.date)).attr('x2', x(d.date)).attr('opacity', 1);
    dot.attr('cx', x(d.date)).attr('cy', y(d.n)).attr('opacity', 1);
    if (d.weeks === 1) tip.show(event, [{ v: fmt(d.n), l: d.n === 1 ? 'play' : 'plays' }], `Week of ${longDay(d.date)}`);
    else tip.show(event, [{ v: fmt(Math.round(d.n)), l: 'plays a week' }], `${d.weeks} weeks from ${longDay(d.date)}`);
  }).on('pointerleave', () => { cross.attr('opacity', 0); dot.attr('opacity', 0); tip.hide(); });
}

/* --------------------------------------------------------------- columns */

/**
 * Columns over an ordered band. data: [{key, n, partial?}]
 * opts: {height, label(d) -> tooltip title, value(d) -> tooltip value, tickEvery, tickFormat, yFormat, onClick, current}
 */
export function columns(el, data, opts = {}) {
  const width = Math.max(280, el.clientWidth);
  const height = opts.height ?? 180;
  const m = { top: 8, right: 4, bottom: 24, left: opts.yFormat === null ? 4 : 40 };
  const w = width - m.left - m.right, ht = height - m.top - m.bottom;
  const x = d3.scaleBand(data.map((d) => d.key), [0, w]).paddingInner(data.length > 60 ? 0.15 : 0.2).paddingOuter(0.05);
  const y = d3.scaleLinear([0, d3.max(data, (d) => d.n) || 1], [ht, 0]).nice();
  const svg = svgIn(el, width, height);
  const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
  if (opts.yFormat !== null) yGrid(g, y, w, 3, opts.yFormat ?? compact);
  else g.append('line').attr('class', 'grid').attr('x1', 0).attr('x2', w).attr('y1', ht).attr('y2', ht).style('stroke', 'var(--grid)');

  const bw = Math.min(24, x.bandwidth());
  const r = Math.min(4, bw / 2);
  // Column path: rounded data-end (top), square at the baseline
  const col = (d) => {
    const x0 = x(d.key) + (x.bandwidth() - bw) / 2, y0 = y(d.n), hgt = ht - y0;
    if (hgt <= 0) return '';
    const rr = Math.min(r, hgt);
    return `M${x0},${ht}V${y0 + rr}Q${x0},${y0} ${x0 + rr},${y0}H${x0 + bw - rr}Q${x0 + bw},${y0} ${x0 + bw},${y0 + rr}V${ht}Z`;
  };
  g.selectAll('path.col').data(data).join('path')
    .attr('class', (d) => `col${d.partial ? ' partial' : ''}${opts.current !== undefined && d.key === opts.current ? ' current' : ''}`)
    .attr('d', col);
  // Hit targets: the full band, taller than the mark
  g.selectAll('rect.hit').data(data).join('rect').attr('class', 'hit')
    .attr('x', (d) => x(d.key)).attr('width', x.step()).attr('y', 0).attr('height', ht)
    .attr('fill', 'transparent').style('cursor', opts.onClick ? 'pointer' : null)
    .on('pointerenter pointermove', (event, d) => {
      g.selectAll('path.col').classed('hover', (c) => c === d);
      tip.show(event, [{ v: opts.value ? opts.value(d) : fmt(d.n), l: opts.unit ?? 'plays' }], opts.label ? opts.label(d) : d.key);
    })
    .on('pointerleave', () => { g.selectAll('path.col').classed('hover', false); tip.hide(); })
    .on('click', (event, d) => opts.onClick && opts.onClick(d));

  const every = opts.tickEvery ?? Math.ceil(data.length / Math.max(2, Math.floor(w / 46)));
  const ticks = data.filter((d, i) => (opts.tickFilter ? opts.tickFilter(d, i) : i % every === 0));
  g.append('g').selectAll('text').data(ticks).join('text')
    .attr('class', (d) => (opts.current !== undefined && d.key === opts.current ? 'current' : null))
    .attr('x', (d) => x(d.key) + x.bandwidth() / 2).attr('y', ht + 17).attr('text-anchor', 'middle')
    .text(opts.tickFormat ?? ((d) => d.key));
  return svg;
}

/** Monthly plays over the full history (artist and song pages). */
export function monthly(el, months, opts = {}) {
  const parse = d3.utcParse('%Y-%m');
  const data = months.map((d) => ({ key: d.m, n: d.n, date: parse(d.m) }));
  const span = data.length;
  const step = span > 120 ? 2 : 1;
  return columns(el, data, {
    height: opts.height ?? 200,
    label: (d) => monthYear(d.date),
    tickFilter: (d) => d.date.getUTCMonth() === 0 && d.date.getUTCFullYear() % step === 0,
    tickFormat: (d) => (step > 1 ? d3.utcFormat('%Y')(d.date) : d3.utcFormat("'%y")(d.date)),
  });
}

/* --------------------------------------------------------------- heatmaps */

function binner(values) {
  const nz = values.filter((v) => v > 0).sort(d3.ascending);
  if (!nz.length) return () => 0;
  const q = d3.scaleQuantile(nz, [1, 2, 3, 4, 5, 6, 7]);
  return (v) => (v > 0 ? q(v) : 0);
}

const DOWS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const DOWS_LONG = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
export const hourLabel = (hr) => (hr === 0 ? '12 am' : hr < 12 ? `${hr} am` : hr === 12 ? '12 pm' : `${hr - 12} pm`);

/** Weekday x hour heatmap of plays. grid[7][24]. */
export function clock(el, grid) {
  const width = Math.max(300, el.clientWidth);
  const m = { top: 4, right: 0, bottom: 22, left: 36 };
  const cw = Math.min(30, (width - m.left - m.right) / 24);
  const chH = Math.min(26, cw);
  const height = m.top + m.bottom + chH * 7;
  const svg = svgIn(el, width, height);
  const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
  const bin = binner(grid.flat());
  const cells = grid.flatMap((row, d) => row.map((n, hr) => ({ d, hr, n })));
  g.selectAll('rect').data(cells).join('rect')
    .attr('class', (c) => `cell q${bin(c.n)}`)
    .attr('x', (c) => c.hr * cw + 1).attr('y', (c) => c.d * chH + 1)
    .attr('width', cw - 2).attr('height', chH - 2).attr('rx', 2)
    .on('pointerenter pointermove', (event, c) =>
      tip.show(event, [{ v: fmt(c.n), l: c.n === 1 ? 'play' : 'plays' }], `${DOWS_LONG[c.d]}, ${hourLabel(c.hr)}`))
    .on('pointerleave', () => tip.hide());
  g.selectAll('text.d').data(DOWS).join('text').attr('class', 'd')
    .attr('x', -8).attr('y', (d, i) => i * chH + chH / 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((d) => d);
  g.selectAll('text.h').data([0, 3, 6, 9, 12, 15, 18, 21]).join('text').attr('class', 'h')
    .attr('x', (hr) => hr * cw + cw / 2).attr('y', 7 * chH + 15).attr('text-anchor', 'middle').text(hourLabel);
}

export const clockTable = (grid) => ({
  head: ['Day', ...Array.from({ length: 24 }, (_, i) => hourLabel(i))],
  rows: grid.map((row, d) => [DOWS[d], ...row.map(fmt)]),
  numeric: Array.from({ length: 24 }, (_, i) => i + 1),
});

/** GitHub-style calendar for one year. days: [{d, n}] */
export function calendar(el, days, year, { onClick } = {}) {
  const width = Math.max(300, el.clientWidth);
  const m = { top: 18, right: 0, bottom: 4, left: 30 };
  const start = new Date(Date.UTC(year, 0, 1));
  const weekOf = (date) => d3.utcMonday.count(d3.utcMonday.floor(start), date);
  const cw = Math.min(18, (width - m.left - m.right) / 54);
  const height = m.top + m.bottom + cw * 7;
  const byDay = new Map(days.map((d) => [d.d, d.n]));
  const all = d3.utcDays(start, new Date(Date.UTC(year + 1, 0, 1))).map((date) => ({ date, n: byDay.get(isoDay(date)) || 0 }));
  const bin = binner(all.map((d) => d.n));
  const svg = svgIn(el, width, height);
  const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
  const dow = (date) => (date.getUTCDay() + 6) % 7;
  g.selectAll('rect').data(all).join('rect')
    .attr('class', (d) => `cell q${bin(d.n)}`)
    .attr('x', (d) => weekOf(d.date) * cw + 1).attr('y', (d) => dow(d.date) * cw + 1)
    .attr('width', cw - 2).attr('height', cw - 2).attr('rx', 2)
    .style('cursor', onClick ? 'pointer' : null)
    .on('pointerenter pointermove', (event, d) =>
      tip.show(event, [{ v: fmt(d.n), l: d.n === 1 ? 'play' : 'plays' }], d3.utcFormat('%A, %b %-d, %Y')(d.date)))
    .on('pointerleave', () => tip.hide())
    .on('click', (event, d) => onClick && onClick(d));
  g.selectAll('text.m').data(d3.utcMonths(start, new Date(Date.UTC(year + 1, 0, 1)))).join('text').attr('class', 'm')
    .attr('x', (d) => weekOf(d) * cw + 1).attr('y', -6).text(d3.utcFormat('%b'));
  g.selectAll('text.d').data([0, 2, 4]).join('text').attr('class', 'd')
    .attr('x', -6).attr('y', (i) => i * cw + cw / 2).attr('dy', '0.32em').attr('text-anchor', 'end').text((i) => DOWS[i]);
}

/* --------------------------------------------------------------- lines */

/**
 * Two-or-more series over the same categories, one y-axis.
 * series: [{name, key: 's1'|'s2', values: [..]}]; labels: category names.
 */
export function lines(el, series, labels, { height = 200, yFormat = d3.format('.0%'), title = (i) => labels[i] } = {}) {
  const width = Math.max(280, el.clientWidth);
  const m = { top: 10, right: 12, bottom: 24, left: 40 };
  const w = width - m.left - m.right, ht = height - m.top - m.bottom;
  const x = d3.scalePoint(labels.map((_, i) => i), [0, w]);
  const y = d3.scaleLinear([0, d3.max(series, (s) => d3.max(s.values))], [ht, 0]).nice();
  const svg = svgIn(el, width, height);
  const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
  yGrid(g, y, w, 3, yFormat);
  const line = d3.line().x((d, i) => x(i)).y((d) => y(d)).curve(d3.curveMonotoneX);
  series.forEach((s) => g.append('path').attr('class', `line ${s.key}`).attr('d', line(s.values)));
  const every = Math.ceil(labels.length / Math.max(2, Math.floor(w / 50)));
  g.append('g').selectAll('text').data(labels.map((l, i) => i).filter((i) => i % every === 0)).join('text')
    .attr('x', (i) => x(i)).attr('y', ht + 17).attr('text-anchor', 'middle').text((i) => labels[i]);

  const cross = g.append('line').attr('class', 'crosshair').attr('y1', 0).attr('y2', ht).attr('opacity', 0);
  const dots = series.map((s) => g.append('circle').attr('class', `dot ${s.key}`).attr('r', 4).attr('opacity', 0));
  g.append('rect').attr('width', w).attr('height', ht).attr('fill', 'transparent')
    .on('pointermove', (event) => {
      const [px] = d3.pointer(event);
      const i = Math.max(0, Math.min(labels.length - 1, Math.round(px / x.step())));
      cross.attr('x1', x(i)).attr('x2', x(i)).attr('opacity', 1);
      series.forEach((s, k) => dots[k].attr('cx', x(i)).attr('cy', y(s.values[i])).attr('opacity', 1));
      tip.show(event, series.map((s) => ({ v: yFormat(s.values[i]), l: s.name, key: s.key })), title(i));
    })
    .on('pointerleave', () => { cross.attr('opacity', 0); dots.forEach((d) => d.attr('opacity', 0)); tip.hide(); });
}

/* --------------------------------------------------------------- sparkline */

/** Tiny per-year columns for list rows. Returns an <svg>. */
export function spark(values, years) {
  const W = 132, H = 28;
  const max = Math.max(1, ...values);
  const bw = W / values.length;
  const svg = d3.create('svg').attr('class', 'spark').attr('viewBox', `0 0 ${W} ${H}`).attr('aria-hidden', 'true');
  svg.selectAll('rect').data(values).join('rect')
    .attr('class', (v) => (v ? null : 'z'))
    .attr('x', (v, i) => i * bw + 0.5).attr('width', Math.max(1, bw - 1.5))
    .attr('y', (v) => (v ? H - Math.max(2, (H * v) / max) : H - 1))
    .attr('height', (v) => (v ? Math.max(2, (H * v) / max) : 1)).attr('rx', 1)
    .append('title').text((v, i) => `${years[i]}: ${fmt(v)} plays`);
  return svg.node();
}
