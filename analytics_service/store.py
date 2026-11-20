"""
In-memory listening history.

Loads play_history once into pandas (read-only), folds identities that the
database splits, and reloads only when the sync job has actually added or
removed plays. Analytics in analytics.py run against a Store snapshot.
"""

import re
import sqlite3
import threading
import time
import unicodedata

import numpy as np
import pandas as pd

RELOAD_CHECK_SECONDS = 15
SESSION_GAP = pd.Timedelta(minutes=30)
WARMUP = pd.Timedelta(days=182)  # first-listens this close to the start of history aren't real discoveries


def fold(s):
    """Case/Unicode/apostrophe-insensitive name key."""
    s = unicodedata.normalize('NFKC', s or '').casefold().replace('’', "'")
    return ' '.join(s.split())


def song_key(title):
    """Title key that merges versions of one song: (feat. ...), [Remaster], ' - Live', punctuation."""
    s = fold(title)
    s = re.sub(r'\s*[\(\[].*?[\)\]]', '', s)
    s = re.sub(r'\s+-\s+.*$', '', s)
    return re.sub(r'[^\w]+', '', s) or fold(title)


def _map_unique(series, fn):
    """Apply a string function once per distinct value."""
    return series.map({v: fn(v) for v in series.unique()})


def _top_variant(raw, group, column):
    """Display name for each folded group: the variant with the most plays."""
    n = raw.groupby([group, column]).size().rename('n').reset_index()
    return n.sort_values('n', ascending=False, kind='stable').drop_duplicates(group).set_index(group)[column].sort_index()


class Store:
    """An immutable snapshot of the listening history."""

    def __init__(self, con):
        raw = pd.read_sql_query(
            "SELECT p.id, p.played_at, p.track_id, t.name AS title, t.album_id, "
            "a.id AS artist_id, a.name AS artist, al.name AS album "
            "FROM play_history p JOIN tracks t ON t.id = p.track_id "
            "JOIN artists a ON a.id = t.artist_id LEFT JOIN albums al ON al.id = t.album_id", con)
        self.signature = signature(con)
        self.loaded_at = time.time()
        self.cache = {}

        ts = pd.to_datetime(raw['played_at'].str.slice(0, 19), format='%Y-%m-%d %H:%M:%S')
        raw = raw.assign(ts=ts).sort_values('ts', kind='stable').reset_index(drop=True)

        # Artists: fold case variants; URL id = smallest artist id in the group
        raw['artist_key'] = _map_unique(raw['artist'], fold)
        a_code, a_keys = pd.factorize(raw['artist_key'])
        raw['a'] = a_code
        self.artists = pd.DataFrame({
            'name': _top_variant(raw, 'a', 'artist'),
            'id': raw.groupby('a')['artist_id'].min(),
        })
        self.artist_by_id = {int(aid): int(a) for aid, a in
                             raw[['artist_id', 'a']].drop_duplicates().itertuples(index=False)}

        # Songs: one per (artist, normalised title); URL id = smallest track id in the group
        raw['song_key'] = raw['artist_key'] + '\x00' + _map_unique(raw['title'], song_key)
        s_code, _ = pd.factorize(raw['song_key'])
        raw['s'] = s_code
        self.songs = pd.DataFrame({
            'title': _top_variant(raw, 's', 'title'),
            'a': raw.groupby('s')['a'].first(),
            'id': raw.groupby('s')['track_id'].min(),
        })
        self.song_by_track = {int(t): int(s) for t, s in
                              raw[['track_id', 's']].drop_duplicates().itertuples(index=False)}

        # Albums: (artist, folded album name)
        album_key = raw['artist_key'] + '\x00' + _map_unique(raw['album'].fillna(''), fold)
        al_code, _ = pd.factorize(album_key)
        raw['al'] = np.where(raw['album'].isna(), -1, al_code)
        has = raw[raw['al'] >= 0]
        self.albums = pd.DataFrame({
            'name': _top_variant(has, 'al', 'album'),
            'a': has.groupby('al')['a'].first(),
        })

        # Sessions: a new session starts after a 30-minute silence
        gap = raw['ts'].diff()
        raw['session'] = (gap.isna() | (gap > SESSION_GAP)).cumsum() - 1

        self.plays = pd.DataFrame({
            'ts': raw['ts'],
            'day': raw['ts'].dt.normalize(),
            'a': raw['a'].astype(np.int32),
            's': raw['s'].astype(np.int32),
            'al': raw['al'].astype(np.int32),
            'hour': raw['ts'].dt.hour.astype(np.int8),
            'dow': raw['ts'].dt.dayofweek.astype(np.int8),
            'year': raw['ts'].dt.year.astype(np.int16),
            'session': raw['session'].astype(np.int32),
        })
        self.first = self.plays['ts'].iloc[0]
        self.last = self.plays['ts'].iloc[-1]
        self.warmup_end = self.first + WARMUP

        # First listen of every artist and song (used by discovery analytics)
        self.artist_first = self.plays.groupby('a')['ts'].min()
        self.artist_last = self.plays.groupby('a')['ts'].max()
        self.artist_total = self.plays.groupby('a').size()
        self.song_total = self.plays.groupby('s').size()

        # Search index
        self.artist_search = self.artists['name'].map(fold)
        self.song_search = self.songs['title'].map(fold)

    def between(self, start=None, end=None):
        """Plays with start <= day <= end (dates inclusive)."""
        p = self.plays
        if start is None and end is None:
            return p
        lo = p['ts'].searchsorted(pd.Timestamp(start)) if start is not None else 0
        hi = p['ts'].searchsorted(pd.Timestamp(end) + pd.Timedelta(days=1)) if end is not None else len(p)
        return p.iloc[lo:hi]

    def cached(self, key, fn):
        if key not in self.cache:
            if len(self.cache) > 5000:  # arbitrary brushed ranges add up; start over rather than grow forever
                self.cache.clear()
            self.cache[key] = fn()
        return self.cache[key]

    def artist_ref(self, a):
        return {'id': int(self.artists.at[a, 'id']), 'name': self.artists.at[a, 'name']}

    def song_ref(self, s):
        a = int(self.songs.at[s, 'a'])
        return {'id': int(self.songs.at[s, 'id']), 'title': self.songs.at[s, 'title'], 'artist': self.artist_ref(a)}


def signature(con):
    """Changes only when plays are added or removed (not on every sync tick)."""
    return con.execute("SELECT count(*), max(id) FROM play_history").fetchone()


class StoreManager:
    """Thread-safe holder that swaps in a fresh Store when the database changes."""

    def __init__(self, db_path, prepare=None):
        self.db_path = db_path
        self.prepare = prepare or (lambda store: None)  # warms caches before a snapshot goes live
        self.lock = threading.Lock()
        self.con = self._connect()
        self.store = Store(self.con)
        self.prepare(self.store)
        self.data_version = self._data_version()
        self.checked = time.time()
        self.reloading = False

    def _connect(self):
        return sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True, check_same_thread=False, timeout=30)

    def _data_version(self):
        return self.con.execute('PRAGMA data_version').fetchone()[0]

    def get(self):
        if time.time() - self.checked < RELOAD_CHECK_SECONDS:
            return self.store
        with self.lock:
            if time.time() - self.checked >= RELOAD_CHECK_SECONDS:
                self.checked = time.time()
                version = self._data_version()
                if version != self.data_version and not self.reloading:
                    self.data_version = version
                    if signature(self.con) != self.store.signature:
                        self.reloading = True
                        threading.Thread(target=self._reload, daemon=True).start()
        return self.store

    def _reload(self):
        """Build the new snapshot off the request path, then swap it in atomically."""
        try:
            fresh = Store(self._connect())
            self.prepare(fresh)
            self.store = fresh
        finally:
            self.reloading = False
