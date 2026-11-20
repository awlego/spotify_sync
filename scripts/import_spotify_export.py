#!/usr/bin/env python3
"""
Reconcile a Spotify "Extended Streaming History" export with play_history.

Steps:
  1. Fix UTC-stored rows: the initial import (lastfm rows with no lastfm_url,
     ids <= 9571) and the early Spotify-API rows were stored in UTC, while the
     rest of play_history is naive *local* start-of-play time. Rows that have a
     local-time twin are deleted; the rest are shifted to local time.
  2. Match every export play (>= 30s, music only) against play_history.
  3. Insert unmatched export plays with source='spotify_export' (fills the
     Last.fm gap, prehistory before Last.fm, and plays Last.fm never scrobbled).
  4. Write a discrepancy report.

Dry run by default; pass --apply to write. Back up the DB before --apply.

Usage:
  env3.10/bin/python -I scripts/import_spotify_export.py ~/Downloads/Spotify\\ Extended\\ Streaming\\ History
"""

import argparse
import bisect
import collections
import csv
import datetime as dt
import difflib
import glob
import json
import os
import re
import sqlite3
import unicodedata

SOURCE = 'spotify_export'
MIN_MS = 30000
INITIAL_UTC_IMPORT_MAX_ID = 9571  # ids 1..9571: first import, stored in UTC, no lastfm_url
TIGHT = dt.timedelta(seconds=90)
LOOSE = dt.timedelta(minutes=30)  # pauses make ts - ms_played a late estimate of start
FMT = '%Y-%m-%d %H:%M:%S.%f'
GAP_DAYS = 30  # report-only: a scrobble-free stretch this long counts as a Last.fm gap


def light(s):
    """Case/Unicode-insensitive name key, used to resolve existing artists/tracks."""
    return ' '.join(unicodedata.normalize('NFKC', s or '').casefold().split())


def norm(s):
    """Aggressive title key for play matching: drops (feat. ...), [Remaster], ' - Live' etc."""
    s = light(s)
    s = re.sub(r'\s*[\(\[].*?[\)\]]', '', s)
    s = re.sub(r'\s+-\s+.*$', '', s)
    return re.sub(r'[^\w]+', '', s)


def utc_to_local(utc):
    return utc.replace(tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)


def parse_db_time(s):
    return dt.datetime.fromisoformat(s[:26] if '.' in s else s)


def load_export(path):
    plays = []
    for f in sorted(glob.glob(os.path.join(path, 'Streaming_History_Audio_*.json'))):
        with open(f) as fh:
            for r in json.load(fh):
                uri = r.get('spotify_track_uri')
                if not uri or r['ms_played'] < MIN_MS or not r.get('master_metadata_track_name'):
                    continue
                end = dt.datetime.strptime(r['ts'], '%Y-%m-%dT%H:%M:%SZ')
                start = utc_to_local(end - dt.timedelta(milliseconds=r['ms_played'])).replace(microsecond=0)
                plays.append(dict(
                    start=start, ms=r['ms_played'], uri=uri, spotify_id=uri.rsplit(':', 1)[1],
                    track=r['master_metadata_track_name'], artist=r['master_metadata_album_artist_name'],
                    album=r['master_metadata_album_album_name'], platform=r['platform'],
                    incognito=r['incognito_mode'], n=norm(r['master_metadata_track_name']),
                    na=norm(r['master_metadata_album_artist_name'])))
    plays.sort(key=lambda p: p['start'])
    return plays


def load_db_plays(con):
    rows = con.execute(
        "SELECT p.id, p.played_at, p.source, p.lastfm_url, t.id, t.name, a.name, t.duration_ms "
        "FROM play_history p JOIN tracks t ON t.id = p.track_id JOIN artists a ON a.id = p.artist_id")
    return [dict(id=i, t=parse_db_time(pa), source=src, url=url, track_id=tid, track=tn, artist=an,
                 duration_ms=dur, n=norm(tn), na=norm(an))
            for i, pa, src, url, tid, tn, an, dur in rows]


def find_utc_rows(db_plays):
    """Return (delete, shift): UTC-stored rows with a local twin, and those without one."""
    by_n = collections.defaultdict(list)
    for p in db_plays:
        by_n[p['n']].append(p)
    suspects = [p for p in db_plays if
                (p['source'] == 'lastfm' and p['url'] is None and p['id'] <= INITIAL_UTC_IMPORT_MAX_ID)
                or p['source'] == 'spotify']
    suspect_ids = {p['id'] for p in suspects}
    delete, shift = [], []
    for p in suspects:
        local = utc_to_local(p['t'])
        if p['source'] == 'spotify':
            # Spotify API played_at is the *end* of the track; the scrobble is at the start
            lo, hi = local - dt.timedelta(minutes=15), local
        else:
            lo, hi = local - dt.timedelta(seconds=2), local + dt.timedelta(seconds=2)
        twin = next((q for q in by_n[p['n']] if q['id'] not in suspect_ids and lo <= q['t'] <= hi), None)
        if twin:
            delete.append((p, twin))
        else:
            shift.append((p, local))
    return delete, shift


def match(export, db_plays):
    """One-to-one matching of export plays to DB plays. Returns {export_idx: db_play}."""
    db_plays = sorted(db_plays, key=lambda p: p['t'])
    times = [p['t'] for p in db_plays]
    used, result = set(), {}

    def same_song(e, d, loose_names):
        if e['n'] == d['n']:
            return True
        return loose_names and (e['na'] == d['na'] or
                                difflib.SequenceMatcher(None, e['n'], d['n']).ratio() >= 0.6)

    for window, loose_names in ((TIGHT, False), (TIGHT, True), (LOOSE, False)):
        for ei, e in enumerate(export):
            if ei in result:
                continue
            i = bisect.bisect_left(times, e['start'] - window)
            best = None
            while i < len(times) and times[i] <= e['start'] + window:
                d = db_plays[i]
                if d['id'] not in used and same_song(e, d, loose_names):
                    gap = abs((times[i] - e['start']).total_seconds())
                    if best is None or gap < best[0]:
                        best = (gap, d)
                i += 1
            if best:
                used.add(best[1]['id'])
                result[ei] = best[1]

    # Same play recorded under a clock off by whole hours (travel/device clock): exact title, +-10s of N hours
    for ei, e in enumerate(export):
        if ei in result:
            continue
        for h in sorted(range(-14, 15), key=abs):
            if h == 0:
                continue
            target = e['start'] + dt.timedelta(hours=h)
            i = bisect.bisect_left(times, target - dt.timedelta(seconds=10))
            while i < len(times) and times[i] <= target + dt.timedelta(seconds=10):
                d = db_plays[i]
                if d['id'] not in used and e['n'] == d['n']:
                    used.add(d['id'])
                    result[ei] = d
                    break
                i += 1
            if ei in result:
                break
    return result


class Resolver:
    """Map export plays to track/artist rows, reusing existing rows case-insensitively."""

    def __init__(self, con):
        self.con = con
        self.by_spotify_id = dict(con.execute("SELECT spotify_id, id FROM tracks WHERE spotify_id IS NOT NULL"))
        self.artists = {}
        for aid, name in con.execute("SELECT id, name FROM artists ORDER BY id"):
            self.artists.setdefault(light(name), aid)
        self.albums = {}
        for alid, name, aid in con.execute("SELECT id, name, artist_id FROM albums ORDER BY id"):
            self.albums.setdefault((light(name), aid), alid)
        self.tracks = collections.defaultdict(list)  # (light title, artist_id) -> [(track_id, album_id, spotify_id)]
        for tid, name, aid, alid, sid in con.execute(
                "SELECT id, name, artist_id, album_id, spotify_id FROM tracks ORDER BY id"):
            self.tracks[(light(name), aid)].append([tid, alid, sid])
        self.track_artist = dict(con.execute("SELECT id, artist_id FROM tracks"))
        self.created = collections.Counter()

    def _artist(self, name):
        key = light(name)
        if key not in self.artists:
            self.artists[key] = self.con.execute("INSERT INTO artists (name) VALUES (?)", (name,)).lastrowid
            self.created['artists'] += 1
        return self.artists[key]

    def _album(self, name, artist_id):
        if not name:
            return None
        key = (light(name), artist_id)
        if key not in self.albums:
            self.albums[key] = self.con.execute(
                "INSERT INTO albums (name, artist_id) VALUES (?, ?)", (name, artist_id)).lastrowid
            self.created['albums'] += 1
        return self.albums[key]

    def track(self, e):
        """Return (track_id, artist_id) for an export play."""
        tid = self.by_spotify_id.get(e['spotify_id'])
        if tid:
            return tid, self.track_artist[tid]
        artist_id = self._artist(e['artist'])
        album_id = self._album(e['album'], artist_id)
        candidates = self.tracks[(light(e['track']), artist_id)]
        if candidates:
            cand = next((c for c in candidates if c[1] == album_id), candidates[0])
            if cand[2] is None:  # adopt this spotify_id; it's not used by any other track
                self.con.execute("UPDATE tracks SET spotify_id = ? WHERE id = ?", (e['spotify_id'], cand[0]))
                cand[2] = e['spotify_id']
                self.by_spotify_id[e['spotify_id']] = cand[0]
                self.created['spotify_ids_filled'] += 1
            return cand[0], artist_id
        tid = self.con.execute(
            "INSERT INTO tracks (name, artist_id, album_id, spotify_id) VALUES (?, ?, ?, ?)",
            (e['track'], artist_id, album_id, e['spotify_id'])).lastrowid
        self.created['tracks'] += 1
        self.tracks[(light(e['track']), artist_id)].append([tid, album_id, e['spotify_id']])
        self.by_spotify_id[e['spotify_id']] = tid
        self.track_artist[tid] = artist_id
        return tid, artist_id


def write_csv(path, header, rows):
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('export_dir')
    ap.add_argument('--db', default='data/db/spotify_sync.db')
    ap.add_argument('--report-dir', default='data/reports/spotify_export')
    ap.add_argument('--apply', action='store_true', help='write changes (default: dry run)')
    args = ap.parse_args()

    con = sqlite3.connect(args.db, timeout=60)
    if con.execute("SELECT count(*) FROM play_history WHERE source = ?", (SOURCE,)).fetchone()[0]:
        raise SystemExit(f"play_history already has source='{SOURCE}' rows; refusing to import twice")

    export = load_export(args.export_dir)
    export_end = export[-1]['start']
    db_plays = load_db_plays(con)
    first_lastfm = min(p['t'] for p in db_plays if p['source'] == 'lastfm')

    # 1. UTC-stored rows
    delete, shift = find_utc_rows(db_plays)
    dead = {p['id'] for p, _ in delete}
    shifted = {p['id']: local for p, local in shift}
    live = []
    for p in db_plays:
        if p['id'] in dead:
            continue
        if p['id'] in shifted:
            p = dict(p, t=shifted[p['id']])
        live.append(p)

    # 2. Match
    matched = match(export, live)
    to_insert = [e for i, e in enumerate(export) if i not in matched]
    matched_db_ids = {d['id'] for d in matched.values()}
    db_only = [p for p in live if p['t'] <= export_end and p['id'] not in matched_db_ids]

    # Stretches of >= GAP_DAYS with no scrobbles: Last.fm stopped scrobbling
    lastfm_times = sorted(p['t'] for p in live if p['source'] == 'lastfm')
    gaps = [(a, b) for a, b in zip(lastfm_times, lastfm_times[1:]) if b - a >= dt.timedelta(days=GAP_DAYS)]

    def category(e):
        if e['start'] < first_lastfm:
            return 'prehistory (before Last.fm)'
        if any(a < e['start'] < b for a, b in gaps):
            return 'gap (Last.fm stopped scrobbling)'
        return 'overlap (never scrobbled)'

    cats = collections.Counter(category(e) for e in to_insert)

    # Report
    os.makedirs(args.report_dir, exist_ok=True)
    write_csv(os.path.join(args.report_dir, 'utc_duplicates_deleted.csv'),
              ['id', 'source', 'played_at_utc_as_stored', 'track', 'artist', 'kept_twin_id', 'kept_twin_played_at'],
              [(p['id'], p['source'], p['t'], p['track'], p['artist'], t['id'], t['t']) for p, t in delete])
    write_csv(os.path.join(args.report_dir, 'utc_rows_shifted_to_local.csv'),
              ['id', 'source', 'played_at_old', 'played_at_new', 'track', 'artist'],
              [(p['id'], p['source'], p['t'], local, p['track'], p['artist']) for p, local in shift])
    write_csv(os.path.join(args.report_dir, 'spotify_plays_inserted.csv'),
              ['played_at_local', 'category', 'ms_played', 'track', 'artist', 'album', 'platform', 'incognito', 'uri'],
              [(e['start'], category(e), e['ms'], e['track'], e['artist'], e['album'], e['platform'],
                e['incognito'], e['uri']) for e in to_insert])
    write_csv(os.path.join(args.report_dir, 'db_plays_without_spotify_match.csv'),
              ['id', 'played_at_local', 'source', 'track', 'artist'],
              [(p['id'], p['t'], p['source'], p['track'], p['artist'])
               for p in sorted(db_only, key=lambda p: p['t'])])

    per_month = collections.defaultdict(lambda: [0, 0, 0])  # export plays, matched, inserted
    for i, e in enumerate(export):
        m = per_month[e['start'].strftime('%Y-%m')]
        m[0] += 1
        m[1 if i in matched else 2] += 1
    db_only_month = collections.Counter(p['t'].strftime('%Y-%m') for p in db_only)
    write_csv(os.path.join(args.report_dir, 'monthly_comparison.csv'),
              ['month', 'spotify_plays_30s', 'matched_in_db', 'inserted', 'db_plays_without_spotify'],
              [(k, *v, db_only_month.get(k, 0)) for k, v in sorted(per_month.items())])

    print(f"export plays >= {MIN_MS // 1000}s: {len(export):,}  ({export[0]['start']} .. {export_end})")
    print(f"UTC rows: delete {len(delete):,} with local twin, shift {len(shift):,} to local "
          f"({collections.Counter(p['source'] for p, _ in shift)})")
    print(f"matched to DB: {len(matched):,}")
    print(f"to insert: {len(to_insert):,}  {dict(cats)}")
    print(f"DB plays (<= export end) with no Spotify match: {len(db_only):,}")
    print(f"reports: {args.report_dir}/")

    if not args.apply:
        print('dry run; pass --apply to write')
        return

    with con:  # one transaction
        con.executemany("DELETE FROM play_history WHERE id = ?", [(i,) for i in dead])
        con.executemany("UPDATE play_history SET played_at = ? WHERE id = ?",
                        [(local.strftime(FMT), i) for i, local in shifted.items()])
        resolver = Resolver(con)
        inserted = 0
        for e in to_insert:
            tid, aid = resolver.track(e)
            inserted += con.execute(
                "INSERT OR IGNORE INTO play_history (track_id, artist_id, played_at, source) VALUES (?, ?, ?, ?)",
                (tid, aid, e['start'].strftime(FMT), SOURCE)).rowcount
    print(f"applied: deleted {len(dead):,}, shifted {len(shifted):,}, inserted {inserted:,} plays; "
          f"created {dict(resolver.created)}")


if __name__ == '__main__':
    main()
