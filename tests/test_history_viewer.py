#!/usr/bin/env python3
"""
Tests for the listening history viewer (analytics_service), on a small synthetic database.
"""

import os
import sqlite3
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'analytics_service'))

import analytics as A  # noqa: E402
import store as S  # noqa: E402
from app import create_app  # noqa: E402

SCHEMA = """
CREATE TABLE artists (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL UNIQUE, spotify_id VARCHAR, genres VARCHAR);
CREATE TABLE albums (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, artist_id INTEGER, spotify_id VARCHAR, release_date DATETIME);
CREATE TABLE tracks (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, artist_id INTEGER NOT NULL, album_id INTEGER,
                     spotify_id VARCHAR, duration_ms INTEGER, popularity INTEGER);
CREATE TABLE play_history (id INTEGER PRIMARY KEY, track_id INTEGER NOT NULL, artist_id INTEGER NOT NULL,
                           played_at DATETIME NOT NULL, source VARCHAR, lastfm_url TEXT);
"""

START = datetime(2015, 1, 5, 9, 0)  # a Monday


class Fixture:
    """Builds a tiny play history with known shapes."""

    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA)
        self.artists, self.tracks = {}, {}

    def artist(self, name):
        if name not in self.artists:
            self.artists[name] = self.con.execute("INSERT INTO artists (name) VALUES (?)", (name,)).lastrowid
        return self.artists[name]

    def track(self, title, artist, album='Album'):
        key = (title, artist, album)
        if key not in self.tracks:
            aid = self.artist(artist)
            al = self.con.execute("INSERT INTO albums (name, artist_id) VALUES (?, ?)", (album, aid)).lastrowid
            self.tracks[key] = self.con.execute(
                "INSERT INTO tracks (name, artist_id, album_id) VALUES (?, ?, ?)", (title, aid, al)).lastrowid
        return self.tracks[key]

    def play(self, title, artist, when, album='Album'):
        tid = self.track(title, artist, album)
        aid = self.con.execute("SELECT artist_id FROM tracks WHERE id = ?", (tid,)).fetchone()[0]
        self.con.execute("INSERT INTO play_history (track_id, artist_id, played_at, source) VALUES (?, ?, ?, 'lastfm')",
                         (tid, aid, when.strftime('%Y-%m-%d %H:%M:%S.%f')))

    def build(self):
        t = START
        # Warm-up period: Old Friend is already known when history starts
        for i in range(30):
            self.play('Classic', 'Old Friend', t + timedelta(days=i, minutes=0))
        # An obsession: 20 plays of one song in a week, across two album versions
        for i in range(20):
            title = 'Anthem' if i % 2 else 'Anthem - Remastered'
            album = 'Debut' if i % 2 else 'Debut (Deluxe)'
            self.play(title, 'Jerri', t + timedelta(days=200 + i % 7, minutes=4 * i), album)
        # Same artist under a different case
        for i in range(5):
            self.play('Second Song', 'jerri', t + timedelta(days=210, minutes=4 * i))
        # Slow burn: sticks in 2015 (5+ plays, after warm-up), peaks in 2019
        for i in range(6):
            self.play('Slow', 'Grower', datetime(2015, 9, 1, 20) + timedelta(days=i))
        for i in range(70):
            self.play('Slow', 'Grower', datetime(2019, 3, 1, 20) + timedelta(days=i))
        # Comeback: 25 plays in 2015, silence until 2019, then 25 more
        for i in range(25):
            self.play('Return', 'Boomerang', datetime(2015, 10, 1, 12) + timedelta(days=i % 20, hours=i // 20))
        for i in range(25):
            self.play('Return', 'Boomerang', datetime(2019, 5, 1, 12) + timedelta(days=i))
        # A stray early play, then real discovery years later: neither a comeback nor a slow burn
        self.play('Hit', 'Late Find', datetime(2015, 11, 1, 12))
        for i in range(80):
            self.play('Hit', 'Late Find', datetime(2019, 6, 1, 12) + timedelta(days=i))
        # Lost love: 90 plays in 2016, nothing since
        for i in range(90):
            self.play('Gone', 'Faded', datetime(2016, 2, 1, 18) + timedelta(days=i))
        # Recent listening keeps the history running to 2021
        for i in range(12):
            self.play('Now', 'Current', datetime(2021, 6, 1, 8) + timedelta(days=i))
        self.con.commit()


class ViewerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = os.path.join(cls.tmp.name, 'history.db')
        cls.fx = Fixture(cls.db)
        cls.fx.build()
        cls.manager = S.StoreManager(cls.db, prepare=A.warm)
        cls.store = cls.manager.store

    @classmethod
    def tearDownClass(cls):
        cls.manager.con.close()
        cls.fx.con.close()
        cls.tmp.cleanup()

    def artist_code(self, name):
        return int(self.store.artists.index[self.store.artists['name'].str.casefold() == name.casefold()][0])


class TestIdentity(ViewerTestCase):
    def test_artist_case_variants_fold(self):
        names = list(self.store.artists['name'])
        self.assertEqual(sum(n.casefold() == 'jerri' for n in names), 1)
        self.assertEqual(self.store.artist_total[self.artist_code('Jerri')], 25)
        # both raw ids resolve to the folded artist
        self.assertEqual(self.store.artist_by_id[self.fx.artists['Jerri']],
                         self.store.artist_by_id[self.fx.artists['jerri']])

    def test_song_versions_merge(self):
        songs = A.top(self.store, 'songs', limit=50)
        anthem = [s for s in songs if s['title'].startswith('Anthem')]
        self.assertEqual(len(anthem), 1)
        self.assertEqual(anthem[0]['plays'], 20)

    def test_song_key(self):
        self.assertEqual(S.song_key('Hello (feat. X) - 2011 Remaster'), S.song_key('hello'))
        self.assertEqual(S.song_key('Fool You’ve Landed'), S.song_key("Fool You've Landed"))
        self.assertNotEqual(S.song_key('22'), S.song_key('29'))


class TestAnalytics(ViewerTestCase):
    def test_summary_range_is_inclusive(self):
        s = A.summary(self.store, '2015-01-05', '2015-01-05')
        self.assertEqual(s['plays'], 1)
        self.assertEqual(A.summary(self.store, '2030-01-01', '2030-12-31'), {'plays': 0})

    def test_new_artists_exclude_warmup(self):
        s = A.summary(self.store)
        # Old Friend is first heard during the warm-up, so it isn't a discovery
        self.assertEqual(s['new_artists'], len(self.store.artists) - 1)

    def test_obsession_counts_plays_in_one_week(self):
        top = A.obsessions(self.store)[0]
        self.assertTrue(top['title'].startswith('Anthem'))
        self.assertEqual(top['plays'], 20)

    def test_arcs(self):
        arcs = A.artist_arcs(self.store)
        self.assertIn('Grower', [r['name'] for r in arcs['slow_burns']])
        self.assertIn('Faded', [r['name'] for r in arcs['lost_loves']])
        back = {r['name']: r for r in arcs['comebacks']}
        self.assertEqual(back['Boomerang']['plays_since'], 25)
        self.assertGreater(back['Boomerang']['silence_years'], 3)
        # One stray play before a gap is a late discovery, not a comeback or a slow burn
        self.assertNotIn('Late Find', back)
        self.assertNotIn('Late Find', [r['name'] for r in arcs['slow_burns']])

    def test_sessions_split_on_30_minute_gaps(self):
        ss = A.sessions(self.store, '2015-07-24', '2015-07-30')
        # 25 Jerri plays 4 minutes apart within each day form sessions; no session spans a gap > 30 min
        p = self.store.between('2015-07-24', '2015-07-30')
        for _, g in p.groupby('session'):
            self.assertTrue((g['ts'].diff().dropna() <= S.SESSION_GAP).all())
        self.assertEqual(sum(d['plays'] for d in ss['distribution']), len(p))

    def test_clock_totals(self):
        grid = A.clock(self.store)
        self.assertEqual(sum(map(sum, grid)), len(self.store.plays))

    def test_year_review_partial_and_discoveries(self):
        y = A.year_review(self.store, 2019)
        self.assertFalse(y['partial'])                                # history covers all of 2019
        self.assertTrue(A.year_review(self.store, 2021)['partial'])  # history ends in June 2021
        self.assertEqual(y['summary']['plays'], 175)
        self.assertEqual([a['name'] for a in y['new_artists']], [])  # everyone played in 2019 was first heard in 2015
        self.assertIsNone(A.year_review(self.store, 2030))

    def test_search_is_case_insensitive(self):
        r = A.search(self.store, 'JERR')
        self.assertEqual([a['name'] for a in r['artists']], ['Jerri'])


class TestApi(ViewerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = create_app(cls.db).test_client()

    def test_endpoints(self):
        jerri = self.fx.artists['Jerri']
        for path in ['/api/meta', '/api/timeline', '/api/overview', '/api/overview?start=2015-01-01&end=2015-12-31',
                     '/api/patterns', '/api/year/2015', f'/api/artist/{jerri}', '/api/song/1',
                     '/api/on-this-day?month=1&day=5', '/api/search?q=gro', '/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_errors(self):
        self.assertEqual(self.client.get('/api/artist/99999').status_code, 404)
        self.assertEqual(self.client.get('/api/year/1990').status_code, 404)
        r = self.client.get('/api/overview?start=2015-1-1')
        self.assertEqual(r.status_code, 400)
        self.assertIn('YYYY-MM-DD', r.get_json()['error'])


class TestReload(unittest.TestCase):
    def test_new_plays_swap_in_a_fresh_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, 'h.db')
            fx = Fixture(db)
            fx.play('One', 'A', datetime(2020, 1, 1, 10))
            fx.con.commit()
            manager = S.StoreManager(db)
            first = manager.store
            self.assertEqual(len(first.plays), 1)
            fx.play('Two', 'B', datetime(2020, 1, 2, 10))
            fx.con.commit()
            manager.checked = 0  # skip the 15-second throttle
            manager.get()
            for _ in range(100):
                if manager.store is not first:
                    break
                time.sleep(0.05)
            self.assertEqual(len(manager.store.plays), 2)
            self.assertEqual(len(first.plays), 1)  # old snapshot is untouched
            manager.con.close()
            fx.con.close()


if __name__ == '__main__':
    unittest.main()
