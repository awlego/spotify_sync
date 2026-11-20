"""
Listening analytics. Every function takes a Store snapshot and returns plain
JSON-ready data. Results are cached on the snapshot, so they are recomputed
only after the history changes.
"""

import numpy as np
import pandas as pd

from store import fold

DAY = pd.Timedelta(days=1)


def _date(ts):
    return pd.Timestamp(ts).strftime('%Y-%m-%d')


def _years(store):
    return list(range(store.first.year, store.last.year + 1))


def _partial(store, year):
    """True when the history doesn't cover the whole calendar year."""
    return (store.first > pd.Timestamp(year, 1, 1) + pd.Timedelta(days=14) or
            store.last < pd.Timestamp(year, 12, 31) - pd.Timedelta(days=14))


def _entropy_effective(counts):
    """exp(Shannon entropy): how many equally-played artists this mix is worth."""
    p = counts / counts.sum()
    return float(np.exp(-(p * np.log(p)).sum())) if len(p) else 0.0


# ---------------------------------------------------------------- overview

def meta(store):
    def build():
        per_year = store.plays.groupby('year').size()
        return {
            'first': _date(store.first), 'last': _date(store.last),
            'plays': int(len(store.plays)), 'artists': int(len(store.artists)), 'songs': int(len(store.songs)),
            'years': [{'year': int(y), 'plays': int(per_year.get(y, 0)), 'partial': _partial(store, y)}
                      for y in _years(store)],
        }
    return store.cached(('meta',), build)


def timeline(store):
    """Weekly plays across the whole history, plus the artist that defined each year."""
    def build():
        p = store.plays
        week = p['day'] - pd.to_timedelta(p['day'].dt.dayofweek, unit='D')
        weekly = p.groupby(week).size()
        full = pd.date_range(weekly.index.min(), weekly.index.max(), freq='7D')
        weekly = weekly.reindex(full, fill_value=0)
        eras = []
        for year, g in p.groupby('year'):
            top = g.groupby('a').size().sort_values(ascending=False)
            a = int(top.index[0])
            peak = g[g['a'] == a]
            eras.append({'year': int(year), 'artist': store.artist_ref(a), 'share': float(top.iloc[0] / len(g)),
                         'peak': _date(peak['day'].iloc[len(peak) // 2])})
        return {'weeks': [{'w': _date(w), 'n': int(n)} for w, n in weekly.items()], 'eras': eras}
    return store.cached(('timeline',), build)


def summary(store, start=None, end=None):
    def build():
        p = store.between(start, end)
        if p.empty:
            return {'plays': 0}
        per_artist = p.groupby('a').size().sort_values(ascending=False)
        per_day = p.groupby('day').size()
        lo, hi = p['ts'].iloc[0], p['ts'].iloc[-1]
        first = store.artist_first
        new = first[(first >= max(lo, store.warmup_end)) & (first <= hi)]
        busiest = per_day.idxmax()
        return {
            'start': _date(lo), 'end': _date(hi),
            'plays': int(len(p)), 'artists': int(len(per_artist)), 'songs': int(p['s'].nunique()),
            'days_active': int(len(per_day)), 'days': int((hi.normalize() - lo.normalize()) / DAY) + 1,
            'new_artists': int(len(new)),
            'new_artists_counted_from': _date(store.warmup_end),
            'effective_artists': round(_entropy_effective(per_artist), 1),
            'top10_share': float(per_artist.head(10).sum() / len(p)),
            'top_artist': {**store.artist_ref(int(per_artist.index[0])), 'plays': int(per_artist.iloc[0])},
            'busiest_day': {'date': _date(busiest), 'plays': int(per_day.max())},
        }
    return store.cached(('summary', start, end), build)


def top(store, kind, start=None, end=None, limit=25):
    def build():
        p = store.between(start, end)
        if kind == 'artists':
            n = p.groupby('a').size().nlargest(limit)
            return [{**store.artist_ref(int(a)), 'plays': int(c)} for a, c in n.items()]
        if kind == 'songs':
            n = p.groupby('s').size().nlargest(limit)
            return [{**store.song_ref(int(s)), 'plays': int(c)} for s, c in n.items()]
        if kind == 'albums':
            p = p[p['al'] >= 0]
            n = p.groupby('al').size().nlargest(limit)
            return [{'name': store.albums.at[al, 'name'], 'artist': store.artist_ref(int(store.albums.at[al, 'a'])),
                     'plays': int(c)} for al, c in n.items()]
        raise ValueError(kind)
    return store.cached(('top', kind, start, end, limit), build)


def clock(store, start=None, end=None, a=None):
    """Plays by weekday (Mon=0) x hour."""
    def build():
        p = store.between(start, end)
        if a is not None:
            p = p[p['a'] == a]
        grid = np.zeros((7, 24), dtype=int)
        counts = p.groupby(['dow', 'hour']).size()
        for (d, h), n in counts.items():
            grid[d, h] = n
        return grid.tolist()
    return store.cached(('clock', start, end, a), build)


def on_this_day(store, month, day):
    """What you played on this calendar date in each past year."""
    def build():
        p = store.plays
        hit = p[(p['ts'].dt.month == month) & (p['ts'].dt.day == day)]
        out = []
        for year, g in hit.groupby('year'):
            songs = g.groupby('s').size().sort_values(ascending=False)
            out.append({'year': int(year), 'plays': int(len(g)),
                        'songs': [{**store.song_ref(int(s)), 'plays': int(n)} for s, n in songs.head(3).items()]})
        return sorted(out, key=lambda r: -r['year'])
    return store.cached(('otd', month, day), build)


def calendar(store, year):
    def build():
        p = store.plays[store.plays['year'] == year]
        per_day = p.groupby('day').size()
        return [{'d': _date(d), 'n': int(n)} for d, n in per_day.items()]
    return store.cached(('calendar', year), build)


# ---------------------------------------------------------------- patterns

def obsessions(store, limit=15, window_days=7):
    """Songs with the most plays inside any 7-day window: your heaviest rotations."""
    def build():
        p = store.plays[['s', 'ts']]
        busy = store.song_total[store.song_total >= 8].index
        p = p[p['s'].isin(busy)].sort_values(['s', 'ts'])
        secs = p['ts'].astype('int64').to_numpy() // 10**9
        song = p['s'].to_numpy().astype(np.int64)
        key = song * 10**10 + secs  # sort key that keeps each song's plays contiguous
        within = np.searchsorted(key, key + window_days * 86400, side='left') - np.arange(len(key))
        df = pd.DataFrame({'s': song, 'ts': p['ts'].to_numpy(), 'n': within})
        best = df.sort_values('n', ascending=False).drop_duplicates('s').head(limit)
        return [{**store.song_ref(int(r.s)), 'plays': int(r.n), 'week_of': _date(r.ts),
                 'total': int(store.song_total[r.s])} for r in best.itertuples()]
    return store.cached(('obsessions', limit, window_days), build)


def _yearly(store):
    return store.cached(('artist_yearly',), lambda: store.plays.groupby(['a', 'year']).size().unstack(fill_value=0))


def artist_arcs(store, limit=12):
    """Slow burns, evergreens, lost loves and comebacks: the long shapes of your listening."""
    def build():
        yearly = _yearly(store)
        years = list(yearly.columns)
        full_years = [y for y in years if not _partial(store, y)]
        total = store.artist_total
        first, last = store.artist_first, store.artist_last

        def row(a, **extra):
            return {**store.artist_ref(int(a)), 'plays': int(total[a]),
                    'by_year': [int(yearly.at[a, y]) for y in years], **extra}

        # Slow burns: discovered after warm-up, peak year came 3+ years later
        cand = total[total >= 60].index
        cand = [a for a in cand if first[a] >= store.warmup_end]
        slow = []
        for a in cand:
            peak = int(yearly.loc[a].idxmax())
            gap = peak - first[a].year
            if gap >= 3:
                slow.append((gap * yearly.at[a, peak], row(a, first=_date(first[a]), peak_year=peak, years_to_peak=gap)))
        slow = [r for _, r in sorted(slow, key=lambda t: -t[0])[:limit]]

        # Evergreens: played meaningfully (10+ plays) in the most full calendar years
        steady = (yearly[full_years] >= 10).sum(axis=1)
        ever = steady[steady >= 4].index
        ever = sorted(ever, key=lambda a: (-steady[a], -total[a]))[:limit]
        evergreens = [row(a, years_active=int(steady[a]), of_years=len(full_years)) for a in ever]

        # Lost loves: big totals, nothing in the last two years
        cutoff = store.last - pd.Timedelta(days=730)
        lost = total[(total >= 80) & (last < cutoff)].sort_values(ascending=False).head(limit)
        lost_loves = [row(a, last=_date(last[a])) for a in lost.index]

        # Comebacks: a silence of 2+ years, then 20+ plays after returning
        p = store.plays[['a', 'ts']].sort_values(['a', 'ts'], kind='stable')
        p = p.assign(gap=p.groupby('a')['ts'].diff(), pos=p.groupby('a').cumcount())
        big = p[p['gap'] > pd.Timedelta(days=730)]
        back = []
        for r in big.sort_values('gap', ascending=False).drop_duplicates('a').itertuples():
            after = int(total[r.a] - r.pos)
            if after >= 20:
                back.append(row(r.a, silence_years=round(r.gap / pd.Timedelta(days=365.25), 1),
                                returned=_date(r.ts), plays_since=after))
        back = sorted(back, key=lambda r: -r['plays_since'])[:limit]

        return {'years': [int(y) for y in years], 'slow_burns': slow, 'evergreens': evergreens,
                'lost_loves': lost_loves, 'comebacks': back}
    return store.cached(('arcs', limit), build)


def diversity(store):
    """Per year: breadth of listening, concentration, and how much was new."""
    def build():
        p = store.plays
        first_year = store.artist_first.dt.year
        counted = store.artist_first >= store.warmup_end
        out = []
        for year, g in p.groupby('year'):
            per_artist = g.groupby('a').size()
            new = first_year[(first_year == year) & counted].index
            out.append({
                'year': int(year), 'partial': _partial(store, year), 'plays': int(len(g)),
                'artists': int(len(per_artist)),
                'effective_artists': round(_entropy_effective(per_artist), 1),
                'top10_share': float(per_artist.nlargest(10).sum() / len(g)),
                'new_artists': int(len(new)) if year >= store.warmup_end.year else None,
                'new_share': float(per_artist.reindex(new).fillna(0).sum() / len(g)) if year >= store.warmup_end.year else None,
            })
        return out
    return store.cached(('diversity',), build)


def sessions(store, start=None, end=None, limit=10):
    """Listening sessions (a new one starts after 30 quiet minutes)."""
    def build():
        p = store.between(start, end)
        if p.empty:
            return {'count': 0}
        g = p.groupby('session')
        size = g.size()
        span = (g['ts'].max() - g['ts'].min()).dt.total_seconds() / 60
        sizes = size.to_numpy()
        buckets = [(1, 1), (2, 5), (6, 10), (11, 20), (21, 40), (41, 10**9)]
        dist = [{'label': f'{a}' if a == b else (f'{a}+' if b > 10**8 else f'{a}–{b}'),
                 'sessions': int(((sizes >= a) & (sizes <= b)).sum()),
                 'plays': int(sizes[(sizes >= a) & (sizes <= b)].sum())} for a, b in buckets]
        longest = []
        for sid in size.nlargest(limit).index:
            q = p[p['session'] == sid]
            ta = q.groupby('a').size().sort_values(ascending=False)
            longest.append({'start': q['ts'].iloc[0].strftime('%Y-%m-%d %H:%M'), 'plays': int(len(q)),
                            'minutes': int(span[sid]), 'artists': int(len(ta)),
                            'top_artist': store.artist_ref(int(ta.index[0]))})
        return {'count': int(len(size)), 'median_plays': float(np.median(sizes)),
                'median_minutes': float(np.median(span)), 'distribution': dist, 'longest': longest}
    return store.cached(('sessions', start, end, limit), build)


# ---------------------------------------------------------------- entities

def _monthly(p, first_month, last_month):
    m = p['ts'].dt.to_period('M')
    counts = m.value_counts()
    idx = pd.period_range(first_month, last_month, freq='M')
    return [{'m': str(k), 'n': int(counts.get(k, 0))} for k in idx]


def artist(store, a):
    def build():
        p = store.plays
        mine = p[p['a'] == a]
        total = int(len(mine))
        rank = int((store.artist_total > total).sum()) + 1
        start = store.first.to_period('M')
        end = store.last.to_period('M')
        songs = mine.groupby('s').size().sort_values(ascending=False)
        first_play = mine.iloc[0]
        months = _monthly(mine, start, end)
        peak = max(months, key=lambda r: r['n'])
        # Hour-of-day profile vs. everything else you play
        mine_h = np.bincount(mine['hour'], minlength=24) / max(total, 1)
        all_h = np.bincount(p['hour'], minlength=24) / len(p)
        return {
            **store.artist_ref(a), 'plays': total, 'rank': rank, 'of': int(len(store.artists)),
            'first': _date(first_play['ts']), 'last': _date(mine['ts'].iloc[-1]),
            'first_song': store.song_ref(int(first_play['s'])),
            'discovered': bool(first_play['ts'] >= store.warmup_end),
            'songs_played': int(len(songs)), 'days_played': int(mine['day'].nunique()),
            'peak_month': peak, 'monthly': months,
            'top_songs': [{**store.song_ref(int(s)), 'plays': int(n),
                           'first': _date(mine.loc[mine['s'] == s, 'ts'].iloc[0])} for s, n in songs.head(20).items()],
            'hours': {'artist': mine_h.round(4).tolist(), 'everyone': all_h.round(4).tolist()},
            'co_listened': co_listened(store, a),
        }
    return store.cached(('artist', a), build)


def co_listened(store, a, limit=12):
    """Artists that turn up in the same sessions far more often than chance (lift, with a support floor)."""
    pairs = store.cached(('session_artists',),
                         lambda: store.plays[['session', 'a']].drop_duplicates())
    n_sessions = store.plays['session'].nunique()
    mine = pairs.loc[pairs['a'] == a, 'session']
    if len(mine) < 5:
        return []
    with_me = pairs[pairs['session'].isin(mine) & (pairs['a'] != a)].groupby('a').size()
    base = store.cached(('artist_sessions',), lambda: pairs.groupby('a').size())
    support = max(5, int(0.04 * len(mine)))
    with_me = with_me[with_me >= support]
    lift = (with_me / len(mine)) / (base.reindex(with_me.index) / n_sessions)
    best = lift.sort_values(ascending=False).head(limit).index  # the support floor keeps rare flukes out
    return [{**store.artist_ref(int(b)), 'together': int(with_me[b]), 'lift': round(float(lift[b]), 1)} for b in best]


def song(store, s):
    def build():
        mine = store.plays[store.plays['s'] == s]
        days = mine.groupby('day').size()
        return {**store.song_ref(s), 'plays': int(len(mine)),
                'first': _date(mine['ts'].iloc[0]), 'last': _date(mine['ts'].iloc[-1]),
                'best_day': {'date': _date(days.idxmax()), 'plays': int(days.max())},
                'monthly': _monthly(mine, store.first.to_period('M'), store.last.to_period('M'))}
    return store.cached(('song', s), build)


def year_review(store, year):
    def build():
        p = store.plays[store.plays['year'] == year]
        if p.empty:
            return None
        start, end = f'{year}-01-01', f'{year}-12-31'
        first = store.artist_first
        counted = first >= store.warmup_end
        new = first[(first.dt.year == year) & counted].index
        per_artist = p.groupby('a').size()
        new_top = per_artist.reindex(new).dropna().sort_values(ascending=False).head(10)
        months = []
        for m, g in p.groupby(p['ts'].dt.month):
            t = g.groupby('a').size().sort_values(ascending=False)
            ts = g.groupby('s').size().sort_values(ascending=False)
            months.append({'month': int(m), 'plays': int(len(g)), 'artist': store.artist_ref(int(t.index[0])),
                           'song': store.song_ref(int(ts.index[0]))})
        prev = store.plays[store.plays['year'] == year - 1]
        return {
            'year': year, 'partial': _partial(store, year),
            'summary': summary(store, start, end),
            'previous_plays': int(len(prev)) if len(prev) else None,
            'top_artists': top(store, 'artists', start, end, 10),
            'top_songs': top(store, 'songs', start, end, 10),
            'top_albums': top(store, 'albums', start, end, 5),
            'new_artists': [{**store.artist_ref(int(a)), 'plays': int(n), 'first': _date(first[a])}
                            for a, n in new_top.items()] if year >= store.warmup_end.year else None,
            'months': months,
            'calendar': calendar(store, year),
        }
    return store.cached(('year', year), build)


def warm(store):
    """Precompute the views everyone opens first, so no request pays for them."""
    meta(store)
    timeline(store)
    summary(store)
    for kind, n in (('artists', 15), ('songs', 15), ('albums', 10)):
        top(store, kind, None, None, n)
    clock(store)
    sessions(store, None, None, 5)
    obsessions(store)
    artist_arcs(store)
    diversity(store)


def search(store, q, limit=8):
    q = fold(q)
    if not q:
        return {'artists': [], 'songs': []}
    am = store.artist_search.str.contains(q, regex=False)
    arts = store.artist_total.reindex(am[am].index).sort_values(ascending=False).head(limit)
    sm = store.song_search.str.contains(q, regex=False)
    songs = store.song_total.reindex(sm[sm].index).sort_values(ascending=False).head(limit)
    return {'artists': [{**store.artist_ref(int(a)), 'plays': int(n)} for a, n in arts.items()],
            'songs': [{**store.song_ref(int(s)), 'plays': int(n)} for s, n in songs.items()]}
