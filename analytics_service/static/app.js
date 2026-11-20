import * as C from './charts.js';
import {
  artistLink, fmt, figure, h, isoDay, longDay, monthYear, ordinal, parseDay, pct, plural, rampLegend,
  rankList, sentence, songLink, strong, tip,
} from './ui.js';

const d3 = window.d3;
const main = document.getElementById('main');

/* ------------------------------------------------------------------ data */

const cache = new Map();
async function api(path) {
  if (cache.has(path)) return cache.get(path);
  const res = await fetch(path);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try { msg = (await res.json()).error || msg; } catch (e) { /* not JSON */ }
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  const data = await res.json();
  cache.set(path, data);
  return data;
}

const qs = (o) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : '';
};

/* ------------------------------------------------------------------ routing */

function parseRoute() {
  const raw = location.hash.replace(/^#/, '') || '/';
  const [path, query] = raw.split('?');
  const params = new URLSearchParams(query || '');
  const parts = path.split('/').filter(Boolean);
  return { parts, params, key: path };
}

let renderToken = 0;
let firstRender = true;
let lastKey = null;
let drawers = [];   // re-run on resize

async function route() {
  const { parts, params, key } = parseRoute();
  const token = ++renderToken;
  const pageChanged = key !== lastKey;
  lastKey = key;
  main.classList.add('loading');
  tip.hide();
  document.querySelectorAll('[data-nav]').forEach((a) => a.removeAttribute('aria-current'));
  try {
    let view;
    if (parts.length === 0) view = await overview(params);
    else if (parts[0] === 'patterns') view = await patterns();
    else if (parts[0] === 'years') { const m = await api('/api/meta'); location.replace(`#/year/${m.years.at(-1).year}`); return; }
    else if (parts[0] === 'year' && /^\d{4}$/.test(parts[1])) view = await yearView(+parts[1]);
    else if (parts[0] === 'artist' && /^\d+$/.test(parts[1])) view = await artistView(+parts[1]);
    else if (parts[0] === 'song' && /^\d+$/.test(parts[1])) view = await songView(+parts[1]);
    else throw Object.assign(new Error('There is no page at this address.'), { status: 404 });
    if (token !== renderToken) return;  // a newer navigation won
    const nav = { overview: parts.length === 0, patterns: parts[0] === 'patterns', years: parts[0] === 'year' };
    Object.entries(nav).forEach(([k, on]) => on && document.querySelector(`[data-nav="${k}"]`).setAttribute('aria-current', 'page'));
    document.title = view.title ? `${view.title} · Listening history` : 'Listening history';
    main.replaceChildren(...view.nodes);
    drawers = [...main.querySelectorAll('.figure')];
    drawers.forEach((f) => f.draw());
    // On in-app navigation, move focus to the new content; on first load, leave it at the top of the page
    if (pageChanged && !firstRender) { window.scrollTo(0, 0); main.focus({ preventScroll: true }); }
    firstRender = false;
  } catch (err) {
    if (token !== renderToken) return;
    main.replaceChildren(errorView(err));
  } finally {
    if (token === renderToken) main.classList.remove('loading');
  }
}

function errorView(err) {
  if (err.status === 404) {
    return h('div', { class: 'error' }, h('h1', {}, 'Nothing here'),
      h('p', {}, err.message, ' ', h('a', { href: '#/' }, 'Go to the overview'), '.'));
  }
  if (err instanceof TypeError) {
    return h('div', { class: 'error' }, h('h1', {}, 'The viewer’s server isn’t responding'),
      h('p', {}, 'Start it from the project root with env3.10/bin/python analytics_service/run.py, then reload this page.'));
  }
  return h('div', { class: 'error' }, h('h1', {}, 'This page couldn’t be built'), h('p', {}, err.message));
}

window.addEventListener('hashchange', route);
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => drawers.forEach((f) => f.isConnected && f.draw()), 150);
});

/* ------------------------------------------------------------------ shared bits */

function section(title, blurb, ...body) {
  return h('section', {}, h('header', {}, h('h2', {}, title), blurb ? h('p', {}, blurb) : null), ...body);
}

const artistItems = (rows) => rows.map((r) => ({ href: `#/artist/${r.id}`, name: r.name, value: r.plays }));
const songItems = (rows) => rows.map((r) => ({ href: `#/song/${r.id}`, name: r.title, by: artistLink(r.artist), value: r.plays }));
const albumItems = (rows) => rows.map((r) => ({ name: r.name, by: artistLink(r.artist), value: r.plays }));

function rangeTitle(start, end, allTime = false) {
  const s = parseDay(start), e = parseDay(end);
  if (allTime) return [monthYear(s), h('span', { class: 'to' }, ' – '), monthYear(e)];
  const wholeYear = s.getUTCMonth() === 0 && s.getUTCDate() === 1 && e.getUTCMonth() === 11 && e.getUTCDate() === 31
    && s.getUTCFullYear() === e.getUTCFullYear();
  if (wholeYear) return [String(s.getUTCFullYear())];
  const monthAligned = s.getUTCDate() === 1 && d3.utcDay.offset(e, 1).getUTCDate() === 1;
  const f = monthAligned ? monthYear : longDay;
  return [f(s), h('span', { class: 'to' }, ' – '), f(e)];
}

/* ------------------------------------------------------------------ overview */

async function overview(params) {
  const start = params.get('start'), end = params.get('end');
  const today = new Date();
  const [meta, tl, ov, otd] = await Promise.all([
    api('/api/meta'), api('/api/timeline'), api(`/api/overview${qs({ start, end })}`),
    api(`/api/on-this-day?month=${today.getMonth() + 1}&day=${today.getDate()}`),
  ]);
  const s = ov.summary;
  const go = (range) => { location.hash = range ? `#/?start=${range[0]}&end=${range[1]}` : '#/'; };

  // Filter row: presets, a year picker, and the brush on the timeline
  const last = parseDay(meta.last);
  const presets = [
    ['All time', null],
    ['Last 12 months', [isoDay(d3.utcDay.offset(d3.utcYear.offset(last, -1), 1)), meta.last]],
    ['Last 90 days', [isoDay(d3.utcDay.offset(last, -89)), meta.last]],
  ];
  const active = (r) => (r ? r[0] === start && r[1] === end : !start && !end);
  const yearSel = h('select', { 'aria-label': 'Show one year' },
    h('option', { value: '' }, 'A year…'),
    [...meta.years].reverse().map((y) => h('option', {
      value: y.year, selected: start === `${y.year}-01-01` && end === `${y.year}-12-31` ? true : null,
    }, String(y.year))));
  yearSel.addEventListener('change', () => yearSel.value && go([`${yearSel.value}-01-01`, `${yearSel.value}-12-31`]));
  const filters = h('div', { class: 'filters', role: 'group', 'aria-label': 'Date range' },
    presets.map(([label, r]) => h('button', {
      type: 'button', class: 'chip', 'aria-pressed': String(active(r)), onclick: () => go(r),
    }, label)),
    yearSel,
    h('span', { class: 'hint' }, 'or drag across the timeline'));

  const range = start && end ? [start, end] : null;
  const timeline = figure({
    label: `Weekly plays from ${meta.first} to ${meta.last}, with the artist that defined each year`,
    draw: (el) => C.river(el, { weeks: tl.weeks, eras: tl.eras, range, onBrush: go }),
    table: () => ({
      head: ['Year', 'Plays', 'Most played artist', 'Their share'],
      rows: tl.eras.map((e) => [String(e.year), fmt(meta.years.find((y) => y.year === e.year).plays), e.artist.name, pct(e.share)]),
      numeric: [1, 3],
    }),
  });

  const lede = s.plays ? h('p', { class: 'lede' }, sentence`${strong(fmt(s.plays))} plays across ${fmt(s.artists)} artists and ${fmt(s.songs)} songs. ${artistLink(s.top_artist)} led with ${fmt(s.top_artist.plays)} plays. You listened on ${fmt(s.days_active)} of ${fmt(s.days)} days${s.new_artists ? ` and found ${fmt(s.new_artists)} new artists` : ''}. Your busiest day was ${longDay(parseDay(s.busiest_day.date))}, with ${fmt(s.busiest_day.plays)} plays.`)
    : h('p', { class: 'lede' }, 'No plays in this range. Pick a wider range or drag across the timeline.');

  const nodes = [
    h('div', { class: 'hero' }, h('h1', {}, s.plays ? rangeTitle(s.start, s.end, !range) : rangeTitle(start, end)), lede),
    filters,
    timeline,
  ];
  if (!s.plays) return { title: 'Overview', nodes };

  nodes.push(
    section('Most played',
      `Your top ten artists took ${pct(s.top10_share)} of plays. Spread evenly, this mix would be ${fmt(Math.round(s.effective_artists))} artists wide.`,
      h('div', { class: 'cols cols-3' },
        h('div', {}, h('h3', {}, 'Artists'), rankList(artistItems(ov.artists))),
        h('div', {}, h('h3', {}, 'Songs'), rankList(songItems(ov.songs))),
        h('div', {}, h('h3', {}, 'Albums'), rankList(albumItems(ov.albums))))),
    section('When you listen', 'Plays by day of the week and hour of the day.',
      h('div', { class: 'cols cols-2-1' },
        figure({
          label: 'Heatmap of plays by weekday and hour', draw: (el) => C.clock(el, ov.clock),
          legend: rampLegend(), table: () => C.clockTable(ov.clock),
        }),
        sessionsBlock(ov.sessions))),
  );

  if (otd.length) {
    nodes.push(section(`On ${d3.timeFormat('%B %-d')(today)}`, 'What you played on this date in past years.',
      h('div', { class: 'otd' }, otd.map((y) => h('div', {},
        h('div', { class: 'year' }, h('a', { href: `#/year/${y.year}` }, String(y.year)), h('span', {}, plural(y.plays, 'play'))),
        h('ul', {}, y.songs.map((sg) => h('li', {}, songLink(sg), h('span', { class: 'by' }, ` by ${sg.artist.name}`)))))))));
  }
  return { title: 'Overview', nodes };
}

function sessionsBlock(ss) {
  if (!ss.count) return h('div');
  const longest = ss.longest[0];
  return h('div', {},
    h('h3', {}, 'Sessions'),
    h('p', { class: 'sub' }, sentence`You listened in ${strong(fmt(ss.count))} sessions; a new one starts after 30 quiet minutes. Half of them ran ${plural(ss.median_plays, 'song')} or fewer.`),
    rankList(ss.distribution.map((d) => ({ name: `${d.label} ${d.label === '1' ? 'song' : 'songs'}`, value: d.sessions, valueLabel: plural(d.sessions, 'session') })),
      { initial: 6, compactRows: true, numbered: false }),
    longest ? h('p', { class: 'sub', style: 'margin-top:14px' },
      sentence`The longest started ${longDay(new Date(longest.start.replace(' ', 'T') + 'Z'))}: ${fmt(longest.plays)} songs over ${(longest.minutes / 60).toFixed(1)} hours, mostly ${artistLink(longest.top_artist)}.`) : null);
}

/* ------------------------------------------------------------------ patterns */

async function patterns() {
  const [meta, p] = await Promise.all([api('/api/meta'), api('/api/patterns')]);
  const years = p.arcs.years;
  const yr = (d) => d.slice(0, 4);
  // Arc rows carry a sparkline instead of a meter
  const arcs = (rows, note) => {
    const list = h('ol', { class: 'rank arc' });
    rows.forEach((r) => list.append(h('li', {},
      h('span', { class: 'what' },
        h('span', { class: 'name' }, h('a', { href: `#/artist/${r.id}` }, r.name)),
        h('span', { class: 'note' }, note(r))),
      C.spark(r.by_year, years))));
    return list;
  };
  const div = p.diversity;
  const firstNew = div.find((d) => d.new_share !== null)?.year;
  const diversityTable = () => ({
    head: ['Year', 'Plays', 'Artists', 'Effective artists', 'Top ten share', 'New artists', 'Plays from new artists'],
    rows: div.map((d) => [`${d.year}${d.partial ? ' (partial)' : ''}`, fmt(d.plays), fmt(d.artists), fmt(Math.round(d.effective_artists)),
      pct(d.top10_share), d.new_artists === null ? '–' : fmt(d.new_artists), d.new_share === null ? '–' : pct(d.new_share)]),
    numeric: [1, 2, 3, 4, 5, 6],
  });
  const multiple = (label, value, fmtv, blurb, table) => figure({
    label, table,
    draw: (el) => C.columns(el, div.filter((d) => value(d) !== null).map((d) => ({ key: String(d.year), n: value(d), partial: d.partial })), {
      height: 170, value: (d) => fmtv(d.n), unit: '', yFormat: fmtv,
      tickFormat: (d) => `'${d.key.slice(2)}`, label: (d) => `${d.key}${d.partial ? ' (partial year)' : ''}`,
    }),
    legend: h('p', { class: 'sub', style: 'font-size:13px;margin-top:8px' }, blurb),
  });

  const nodes = [
    h('div', { class: 'hero' }, h('h1', {}, 'Patterns'),
      h('p', { class: 'lede' }, `The long shapes in ${meta.first.slice(0, 4)}–${meta.last.slice(0, 4)}: what you played on repeat, who grew on you, who you drifted from, and how wide your listening ran.`)),
    section('Heaviest rotations', 'Songs with the most plays inside a single week.',
      rankList(p.obsessions.map((o) => ({
        href: `#/song/${o.id}`, name: o.title,
        by: [artistLink(o.artist), `, week of ${longDay(parseDay(o.week_of))}`],
        value: o.plays, valueLabel: `${fmt(o.plays)} in a week`,
      })))),
    section('Long arcs', 'Plays per year for each artist, from your first year of history to now.',
      h('div', { class: 'cols cols-2' },
        h('div', {}, h('h3', {}, 'Grew on you'),
          h('p', { class: 'sub', style: 'margin:-6px 0 8px;font-size:13px' }, 'Their biggest year came at least three years after you found them.'),
          arcs(p.arcs.slow_burns, (r) => `First played ${yr(r.first)}, peaked ${r.peak_year}`)),
        h('div', {}, h('h3', {}, 'Evergreens'),
          h('p', { class: 'sub', style: 'margin:-6px 0 8px;font-size:13px' }, 'Ten or more plays in the most full calendar years.'),
          arcs(p.arcs.evergreens, (r) => `${r.years_active} of ${r.of_years} years`)),
        h('div', {}, h('h3', {}, 'Drifted away'),
          h('p', { class: 'sub', style: 'margin:-6px 0 8px;font-size:13px' }, 'Big totals, but nothing in the last two years.'),
          arcs(p.arcs.lost_loves, (r) => `${fmt(r.plays)} plays, last in ${monthYear(parseDay(r.last))}`)),
        h('div', {}, h('h3', {}, 'Came back'),
          h('p', { class: 'sub', style: 'margin:-6px 0 8px;font-size:13px' }, 'Silent for two years or more, then played again.'),
          arcs(p.arcs.comebacks, (r) => `Back in ${monthYear(parseDay(r.returned))} after ${r.silence_years} years, ${fmt(r.plays_since)} plays since`)))),
    section('How wide you listened', 'Each year on its own. Lighter columns are years the history only partly covers.',
      h('div', { class: 'cols cols-3' },
        h('div', {}, h('h3', {}, 'Breadth'), multiple('Effective number of artists per year', (d) => d.effective_artists, (v) => fmt(Math.round(v)),
          'How many artists your year was worth if each had been played equally.', diversityTable)),
        h('div', {}, h('h3', {}, 'Top ten’s share'), multiple('Share of plays from the year’s top ten artists', (d) => d.top10_share, pct,
          'Share of the year’s plays that went to its ten most played artists.')),
        h('div', {}, h('h3', {}, 'Plays from new artists'), multiple('Share of plays from artists first heard that year', (d) => d.new_share, pct,
          `Share of plays from artists you first heard that year. Starts in ${firstNew}, once a few months of history exist to tell new from familiar.`)))),
  ];
  return { title: 'Patterns', nodes };
}

/* ------------------------------------------------------------------ year */

async function yearView(year) {
  const [meta, y] = await Promise.all([api('/api/meta'), api(`/api/year/${year}`)]);
  const s = y.summary;
  const idx = meta.years.findIndex((r) => r.year === year);
  const prev = meta.years[idx - 1], next = meta.years[idx + 1];
  const change = y.previous_plays ? (s.plays - y.previous_plays) / y.previous_plays : null;

  const picker = figure({
    label: 'Plays per year; choose a year',
    draw: (el) => {
      C.columns(el, meta.years.map((r) => ({ key: String(r.year), n: r.plays, partial: r.partial })), {
        height: 110, yFormat: null, current: String(year), label: (d) => `${d.key}${d.partial ? ' (partial year)' : ''}`,
        tickFormat: (d) => `'${d.key.slice(2)}`, onClick: (d) => { location.hash = `#/year/${d.key}`; },
      });
      el.classList.add('years-nav');
    },
  });

  const lede = h('p', { class: 'lede' }, sentence`${strong(fmt(s.plays))} plays across ${fmt(s.artists)} artists${change !== null ? `, ${change >= 0 ? 'up' : 'down'} ${pct(Math.abs(change))} from ${year - 1}` : ''}. ${artistLink(s.top_artist)} led with ${fmt(s.top_artist.plays)} plays${y.new_artists ? `, and you found ${fmt(s.new_artists)} new artists` : ''}.${y.partial ? ' Your history only partly covers this year.' : ''}`);

  const nodes = [
    picker,
    h('div', { class: 'hero', style: 'margin-top:28px' }, h('h1', {}, String(year)), lede),
    section('Every day', `Your busiest day was ${longDay(parseDay(s.busiest_day.date))}, with ${fmt(s.busiest_day.plays)} plays.`,
      figure({
        label: `Calendar of daily plays in ${year}`, draw: (el) => C.calendar(el, y.calendar, year),
        legend: rampLegend(),
        table: () => ({ head: ['Date', 'Plays'], rows: y.calendar.map((d) => [d.d, fmt(d.n)]), numeric: [1] }),
      })),
    section('Month by month', 'The artist and song you played most each month.',
      h('div', { class: 'months' }, y.months.map((mo) => h('div', {},
        h('span', { class: 'm' }, d3.utcFormat('%B')(new Date(Date.UTC(year, mo.month - 1, 1)))),
        h('span', { class: 'a' }, artistLink(mo.artist)),
        h('span', { class: 's' }, songLink(mo.song)))))),
    section('Most played', null,
      h('div', { class: 'cols cols-3' },
        h('div', {}, h('h3', {}, 'Artists'), rankList(artistItems(y.top_artists))),
        h('div', {}, h('h3', {}, 'Songs'), rankList(songItems(y.top_songs))),
        h('div', {}, h('h3', {}, 'Albums'), rankList(albumItems(y.top_albums))))),
  ];
  if (y.new_artists && y.new_artists.length) {
    nodes.push(section(`Found in ${year}`, 'Artists you first played this year, by plays that year.',
      rankList(y.new_artists.map((a) => ({ href: `#/artist/${a.id}`, name: a.name, by: `First played ${longDay(parseDay(a.first))}`, value: a.plays })))));
  }
  nodes.push(h('nav', { class: 'pager', 'aria-label': 'Other years' },
    prev ? h('a', { href: `#/year/${prev.year}` }, `Previous: ${prev.year}`) : null,
    next ? h('a', { href: `#/year/${next.year}` }, `Next: ${next.year}`) : null));
  return { title: String(year), nodes };
}

/* ------------------------------------------------------------------ artist */

async function artistView(id) {
  const a = await api(`/api/artist/${id}`);
  const hours = Array.from({ length: 24 }, (_, i) => C.hourLabel(i));
  const firstLine = a.discovered
    ? sentence`You found them on ${longDay(parseDay(a.first))} with ${songLink(a.first_song)}`
    : sentence`They were already playing when your history begins; the first recorded play is ${songLink(a.first_song)} on ${longDay(parseDay(a.first))}`;
  const peak = d3.utcParse('%Y-%m')(a.peak_month.m);
  const nodes = [
    h('div', { class: 'hero' }, h('span', { class: 'crumb' }, 'Artist'), h('h1', {}, a.name),
      h('p', { class: 'lede' }, sentence`${strong(fmt(a.plays))} plays, ${a.rank === 1 ? 'more than any other' : `your ${ordinal(a.rank)} most played`} of ${fmt(a.of)} artists. `, ...firstLine,
        `, and last played them on ${longDay(parseDay(a.last))}. Their biggest month was ${monthYear(peak)}, with ${fmt(a.peak_month.n)} plays.`)),
    section('Over the years', 'Plays per month.',
      figure({
        label: `Monthly plays of ${a.name}`, draw: (el) => C.monthly(el, a.monthly),
        table: () => ({ head: ['Month', 'Plays'], rows: a.monthly.filter((m) => m.n).map((m) => [m.m, fmt(m.n)]), numeric: [1] }),
      })),
    h('div', { class: 'cols cols-2-1' },
      section('Songs', `${plural(a.songs_played, 'song')} played, on ${plural(a.days_played, 'day')}.`,
        rankList(a.top_songs.map((sg) => ({ href: `#/song/${sg.id}`, name: sg.title, by: `First played ${longDay(parseDay(sg.first))}`, value: sg.plays })))),
      section('Played alongside', 'Artists that show up in the same sessions far more than chance would predict.',
        a.co_listened.length
          ? rankList(a.co_listened.map((c) => ({ href: `#/artist/${c.id}`, name: c.name, by: `In ${plural(c.together, 'shared session')}`, value: c.lift, valueLabel: `${c.lift}×` })), { initial: 12 })
          : h('p', { class: 'sub' }, 'Not enough sessions with this artist to tell.'))),
    section('When you play them', 'Share of plays by hour, for this artist and for everything you play.',
      figure({
        label: `Hour-of-day profile of ${a.name} compared with all listening`,
        draw: (el) => C.lines(el, [
          { name: a.name, key: 's1', values: a.hours.artist },
          { name: 'Everything', key: 's2', values: a.hours.everyone },
        ], hours, { title: (i) => hours[i] }),
        legend: h('div', { class: 'legend' },
          h('span', { class: 'key' }, h('span', { class: 'line-key' }), a.name),
          h('span', { class: 'key' }, h('span', { class: 'line-key s2' }), 'Everything you play')),
        table: () => ({ head: ['Hour', a.name, 'Everything'], rows: hours.map((hr, i) => [hr, pct(a.hours.artist[i]), pct(a.hours.everyone[i])]), numeric: [1, 2] }),
      }),
      h('div', { style: 'margin-top:28px' }, figure({
        label: `Heatmap of ${a.name} plays by weekday and hour`, draw: (el) => C.clock(el, a.clock),
        legend: rampLegend(), table: () => C.clockTable(a.clock),
      }))),
  ];
  return { title: a.name, nodes };
}

/* ------------------------------------------------------------------ song */

async function songView(id) {
  const sg = await api(`/api/song/${id}`);
  const nodes = [
    h('div', { class: 'hero' }, h('span', { class: 'crumb' }, 'Song by ', artistLink(sg.artist)), h('h1', {}, sg.title),
      h('p', { class: 'lede' }, sentence`${strong(fmt(sg.plays))} plays between ${longDay(parseDay(sg.first))} and ${longDay(parseDay(sg.last))}. Your biggest day with it was ${longDay(parseDay(sg.best_day.date))}, with ${plural(sg.best_day.plays, 'play')}.`)),
    section('Over the years', 'Plays per month.',
      figure({
        label: `Monthly plays of ${sg.title}`, draw: (el) => C.monthly(el, sg.monthly),
        table: () => ({ head: ['Month', 'Plays'], rows: sg.monthly.filter((m) => m.n).map((m) => [m.m, fmt(m.n)]), numeric: [1] }),
      })),
  ];
  return { title: sg.title, nodes };
}

/* ------------------------------------------------------------------ search */

const dialog = document.querySelector('dialog.search');
const input = dialog.querySelector('input');
const results = dialog.querySelector('.search-results');
let searchTimer, searchSeq = 0, selected = -1;

function openSearch() {
  if (dialog.open) return;
  dialog.showModal();
  input.select();
  if (!input.value) results.replaceChildren(h('p', { class: 'empty' }, 'Type an artist or song name.'));
}
document.querySelector('.search-open').addEventListener('click', openSearch);
document.addEventListener('keydown', (e) => {
  const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement?.tagName);
  if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) { e.preventDefault(); openSearch(); }
});
dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });

input.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 120);
});
async function runSearch() {
  const q = input.value.trim();
  const seq = ++searchSeq;
  if (!q) { results.replaceChildren(h('p', { class: 'empty' }, 'Type an artist or song name.')); return; }
  const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
  if (seq !== searchSeq) return;
  const items = [];
  if (r.artists.length) items.push(h('div', { class: 'group' }, 'Artists'));
  r.artists.forEach((a) => items.push(h('a', { href: `#/artist/${a.id}`, role: 'option' }, h('span', {}, a.name), h('span', { class: 'muted num' }, plural(a.plays, 'play')))));
  if (r.songs.length) items.push(h('div', { class: 'group' }, 'Songs'));
  r.songs.forEach((sg) => items.push(h('a', { href: `#/song/${sg.id}`, role: 'option' },
    h('span', {}, sg.title, h('span', { class: 'by' }, sg.artist.name)), h('span', { class: 'muted num' }, plural(sg.plays, 'play')))));
  if (!items.length) items.push(h('p', { class: 'empty' }, `No artists or songs match “${q}”.`));
  results.replaceChildren(...items);
  selected = r.artists.length + r.songs.length ? 0 : -1;
  mark();
}
function options() { return [...results.querySelectorAll('a')]; }
function mark() {
  options().forEach((o, i) => o.setAttribute('aria-selected', String(i === selected)));
  options()[selected]?.scrollIntoView({ block: 'nearest' });
}
input.addEventListener('keydown', (e) => {
  const opts = options();
  if (e.key === 'ArrowDown') { e.preventDefault(); selected = Math.min(opts.length - 1, selected + 1); mark(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); selected = Math.max(0, selected - 1); mark(); }
  else if (e.key === 'Enter') {
    e.preventDefault();
    if (opts[selected]) { location.hash = opts[selected].getAttribute('href'); dialog.close(); }
  }
});
results.addEventListener('click', (e) => { if (e.target.closest('a')) dialog.close(); });

/* ------------------------------------------------------------------ theme */

const themeBtn = document.querySelector('.theme');
function isDark() {
  const t = document.documentElement.dataset.theme;
  return t ? t === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
}
function labelTheme() { themeBtn.setAttribute('aria-label', isDark() ? 'Switch to light theme' : 'Switch to dark theme'); }
themeBtn.addEventListener('click', () => {
  const next = isDark() ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('theme', next); } catch (e) { /* storage unavailable */ }
  labelTheme();
});
labelTheme();

route();
