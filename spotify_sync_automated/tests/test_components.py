#!/usr/bin/env python3
"""
Component tests for Spotify Sync
"""

import sys
import os
import unittest
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.config import get_config
from core.database import DatabaseManager
from api.lastfm_client import LastFMClient


class TestConfig(unittest.TestCase):
    """Test configuration loading"""
    
    def test_config_loads(self):
        """Test that configuration loads successfully"""
        config = get_config()
        self.assertIsNotNone(config)
        self.assertIsNotNone(config.lastfm.username)
        self.assertIsNotNone(config.spotify.username)
        
    def test_playlist_configs(self):
        """Test playlist configurations"""
        config = get_config()
        self.assertIn('most_listened', config.playlists)
        self.assertIn('recent_favorites', config.playlists)
        self.assertIn('binged_songs', config.playlists)


class TestDatabase(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        self.db = DatabaseManager('test_spotify_sync.db')
        
    def tearDown(self):
        # Clean up test database
        if os.path.exists('test_spotify_sync.db'):
            os.remove('test_spotify_sync.db')
    
    def test_create_track(self):
        """Test creating a track"""
        with self.db.session_scope() as session:
            track = self.db.get_or_create_track(
                session,
                name="Test Song",
                artist_name="Test Artist",
                album_name="Test Album"
            )
            self.assertEqual(track.name, "Test Song")
            self.assertEqual(track.artist.name, "Test Artist")
            self.assertEqual(track.album.name, "Test Album")
    
    def test_add_play(self):
        """Test adding a play"""
        with self.db.session_scope() as session:
            track = self.db.get_or_create_track(
                session,
                name="Test Song",
                artist_name="Test Artist"
            )
            
            play_time = datetime.now()
            play = self.db.add_play(session, track, play_time)
            
            self.assertIsNotNone(play)
            self.assertEqual(play.track_id, track.id)
            self.assertEqual(play.played_at, play_time)
    
    def test_duplicate_play(self):
        """Test that duplicate plays are not added"""
        with self.db.session_scope() as session:
            track = self.db.get_or_create_track(
                session,
                name="Test Song",
                artist_name="Test Artist"
            )
            
            play_time = datetime.now()
            play1 = self.db.add_play(session, track, play_time)
            play2 = self.db.add_play(session, track, play_time)
            
            self.assertIsNotNone(play1)
            self.assertIsNone(play2)  # Should be None for duplicate
    
    def test_play_counts(self):
        """Test play count calculations"""
        with self.db.session_scope() as session:
            # Create track with multiple plays
            track = self.db.get_or_create_track(
                session,
                name="Popular Song",
                artist_name="Popular Artist"
            )
            
            # Add plays at different times
            for i in range(5):
                play_time = datetime.now() - timedelta(hours=i)
                self.db.add_play(session, track, play_time)
        
        # Test play counts
        with self.db.session_scope() as session:
            counts = self.db.get_play_counts(session)
            self.assertEqual(len(counts), 1)
            track, count = counts[0]
            self.assertEqual(count, 5)


class TestLastFMClient(unittest.TestCase):
    """Test Last.fm API client"""
    
    def setUp(self):
        self.client = LastFMClient()
    
    def test_parse_track(self):
        """Test track parsing"""
        # Mock Last.fm track data
        track_data = {
            'artist': {'#text': 'Test Artist'},
            'album': {'#text': 'Test Album'},
            'name': 'Test Track',
            'date': {'uts': '1234567890'},
            'mbid': 'test-mbid',
            'url': 'http://test.url'
        }
        
        parsed = self.client.parse_track(track_data)
        
        self.assertEqual(parsed['artist'], 'Test Artist')
        self.assertEqual(parsed['album'], 'Test Album')
        self.assertEqual(parsed['track'], 'Test Track')
        self.assertEqual(parsed['played_at'].timestamp(), 1234567890)
    
    def test_connection(self):
        """Test Last.fm API connection"""
        user_info = self.client.get_user_info()
        self.assertIsNotNone(user_info)
        self.assertIn('name', user_info)


def run_component_tests():
    """Run specific component tests"""
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add specific tests
    suite.addTest(TestConfig('test_config_loads'))
    suite.addTest(TestDatabase('test_create_track'))
    suite.addTest(TestDatabase('test_add_play'))
    suite.addTest(TestLastFMClient('test_parse_track'))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    # Run all tests
    unittest.main()