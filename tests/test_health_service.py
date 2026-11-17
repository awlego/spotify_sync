#!/usr/bin/env python3
"""
Tests for the sync service health checks
"""

import unittest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sync_service'))

import requests
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOauthError

from services.health_service import find_problems, spotify_auth_ok, HealthMonitor

NOW_UTC = datetime(2026, 11, 17, 1, 0)
NOW_LOCAL = datetime(2026, 11, 16, 17, 0)


def problems(last_sync=NOW_UTC - timedelta(minutes=5),
             latest_play=NOW_LOCAL - timedelta(hours=1),
             spotify_ok=True):
    return find_problems(NOW_UTC, NOW_LOCAL, last_sync, latest_play, spotify_ok)


class TestFindProblems(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(problems(), {})

    def test_sync_stuck(self):
        self.assertIn('sync_stuck', problems(last_sync=NOW_UTC - timedelta(hours=29)))
        self.assertIn('sync_stuck', problems(last_sync=None))

    def test_no_new_plays(self):
        self.assertIn('no_new_plays', problems(latest_play=NOW_LOCAL - timedelta(days=4)))
        self.assertNotIn('no_new_plays', problems(latest_play=NOW_LOCAL - timedelta(days=2)))

    def test_play_times_compared_as_local(self):
        # A play 2h ago local time must not look 6h+ old by being compared to UTC now
        self.assertNotIn('no_new_plays', problems(latest_play=NOW_LOCAL - timedelta(hours=2)))

    def test_spotify_auth(self):
        self.assertIn('spotify_auth', problems(spotify_ok=False))


class FakeSpotifyClient:
    def __init__(self, error=None):
        self.error = error
        self._sp = self

    def current_user(self):
        if self.error:
            raise self.error
        return {'id': 'me'}


class TestSpotifyAuthOk(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(spotify_auth_ok(FakeSpotifyClient()))

    def test_revoked_token(self):
        err = SpotifyOauthError('revoked', error='invalid_grant', error_description='Refresh token revoked')
        self.assertFalse(spotify_auth_ok(FakeSpotifyClient(err)))

    def test_unauthorized(self):
        self.assertFalse(spotify_auth_ok(FakeSpotifyClient(SpotifyException(401, -1, 'unauthorized'))))

    def test_network_error_is_not_auth_problem(self):
        self.assertTrue(spotify_auth_ok(FakeSpotifyClient(requests.exceptions.ConnectionError('aborted'))))
        self.assertTrue(spotify_auth_ok(FakeSpotifyClient(SpotifyException(503, -1, 'unavailable'))))


class TestAlerting(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.monitor = HealthMonitor(spotify_client=object(), db=object(),
                                     notify=lambda title, msg: self.sent.append(msg) or True)

    def test_needs_two_consecutive_checks(self):
        self.monitor.process({'spotify_auth': 'x'}, NOW_LOCAL)
        self.assertEqual(self.sent, [])
        self.monitor.process({'spotify_auth': 'x'}, NOW_LOCAL + timedelta(minutes=30))
        self.assertEqual(self.sent, ['x'])

    def test_blip_does_not_alert(self):
        self.monitor.process({'spotify_auth': 'x'}, NOW_LOCAL)
        self.monitor.process({}, NOW_LOCAL + timedelta(minutes=30))
        self.monitor.process({'spotify_auth': 'x'}, NOW_LOCAL + timedelta(minutes=60))
        self.assertEqual(self.sent, [])

    def test_realerts_daily_not_every_check(self):
        for i in range(48 * 2 + 1):  # every 30 min for 48h
            self.monitor.process({'sync_stuck': 'x'}, NOW_LOCAL + timedelta(minutes=30 * i))
        self.assertEqual(len(self.sent), 2)

    def test_failed_notification_is_retried(self):
        self.monitor.notify = lambda title, msg: False
        self.monitor.process({'sync_stuck': 'x'}, NOW_LOCAL)
        self.monitor.process({'sync_stuck': 'x'}, NOW_LOCAL + timedelta(minutes=30))
        self.monitor.notify = lambda title, msg: self.sent.append(msg) or True
        self.monitor.process({'sync_stuck': 'x'}, NOW_LOCAL + timedelta(minutes=60))
        self.assertEqual(self.sent, ['x'])


if __name__ == '__main__':
    unittest.main()
