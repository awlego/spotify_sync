#!/usr/bin/env python3
"""
Test script for validating sync functionality
"""

import sys
import os
from datetime import datetime, timedelta
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.config import get_config
from src.core.database import DatabaseManager
from src.api.lastfm_client import LastFMClient
from src.api.spotify_client import SpotifyClient
from src.services.sync_service import SyncService


def setup_logging():
    """Configure logging for testing"""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )


def test_database_connection():
    """Test database connection and table creation"""
    logger.info("Testing database connection...")
    try:
        db = DatabaseManager()
        with db.session_scope() as session:
            # Test query
            from src.core.models import Track
            count = session.query(Track).count()
            logger.success(f"Database connected! Found {count} tracks")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def test_lastfm_connection():
    """Test Last.fm API connection"""
    logger.info("Testing Last.fm API connection...")
    try:
        lastfm = LastFMClient()
        user_info = lastfm.get_user_info()
        if user_info:
            logger.success(f"Last.fm connected! User: {user_info['name']}, Total plays: {user_info['playcount']}")
            return True
        else:
            logger.error("Failed to get Last.fm user info")
            return False
    except Exception as e:
        logger.error(f"Last.fm connection failed: {e}")
        return False


def test_spotify_connection():
    """Test Spotify API connection"""
    logger.info("Testing Spotify API connection...")
    try:
        spotify = SpotifyClient()
        if spotify.ensure_authenticated():
            logger.success("Spotify authenticated successfully!")
            return True
        else:
            logger.warning("Spotify authentication failed - you may need to authenticate via web UI")
            return False
    except Exception as e:
        logger.error(f"Spotify connection failed: {e}")
        return False


def sync_full_lastfm_history(days_back=None):
    """Sync entire Last.fm history"""
    logger.info("Starting full Last.fm history sync...")
    
    try:
        sync_service = SyncService()
        
        # If days_back not specified, sync everything (10 years)
        if days_back is None:
            days_back = 365 * 10
            
        logger.info(f"Syncing {days_back} days of history...")
        
        # Perform sync
        tracks_synced = sync_service.sync_lastfm(days_back=days_back)
        
        logger.success(f"Synced {tracks_synced} new tracks from Last.fm!")
        
        # Show some stats
        db = DatabaseManager()
        with db.session_scope() as session:
            from src.core.models import Track, PlayHistory, Artist
            
            total_tracks = session.query(Track).count()
            total_plays = session.query(PlayHistory).count()
            total_artists = session.query(Artist).count()
            
            logger.info(f"Database stats:")
            logger.info(f"  Total tracks: {total_tracks}")
            logger.info(f"  Total plays: {total_plays}")
            logger.info(f"  Total artists: {total_artists}")
            
            # Show recent plays
            recent_plays = session.query(PlayHistory).order_by(
                PlayHistory.played_at.desc()
            ).limit(5).all()
            
            logger.info("Most recent plays:")
            for play in recent_plays:
                logger.info(f"  {play.played_at}: {play.track.artist.name} - {play.track.name}")
                
        return True
        
    except Exception as e:
        logger.error(f"Full sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recent_sync():
    """Test syncing recent tracks only"""
    logger.info("Testing recent tracks sync (last 7 days)...")
    
    try:
        sync_service = SyncService()
        tracks_synced = sync_service.sync_lastfm(days_back=7)
        logger.success(f"Synced {tracks_synced} tracks from the last 7 days")
        return True
    except Exception as e:
        logger.error(f"Recent sync failed: {e}")
        return False


def show_top_tracks():
    """Show top tracks from database"""
    logger.info("Top 10 most played tracks:")
    
    db = DatabaseManager()
    with db.session_scope() as session:
        top_tracks = db.get_play_counts(session)[:10]
        
        for i, (track, count) in enumerate(top_tracks, 1):
            logger.info(f"  {i}. {track.artist.name} - {track.name} ({count} plays)")


def main():
    """Run all tests"""
    setup_logging()
    
    logger.info("=== Spotify Sync Testing Suite ===")
    
    # Test connections
    tests = [
        ("Database", test_database_connection),
        ("Last.fm API", test_lastfm_connection),
        ("Spotify API", test_spotify_connection),
    ]
    
    all_passed = True
    for name, test_func in tests:
        if not test_func():
            all_passed = False
            logger.warning(f"{name} test failed")
        print()  # Empty line between tests
    
    if not all_passed:
        logger.error("Some connection tests failed. Fix these before proceeding.")
        return
    
    # Ask user what to do
    print("\nWhat would you like to do?")
    print("1. Sync full Last.fm history (recommended for first run)")
    print("2. Sync recent tracks only (last 7 days)")
    print("3. Show current top tracks")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ")
    
    if choice == "1":
        sync_full_lastfm_history()
        show_top_tracks()
    elif choice == "2":
        test_recent_sync()
        show_top_tracks()
    elif choice == "3":
        show_top_tracks()
    elif choice == "4":
        logger.info("Exiting...")
    else:
        logger.warning("Invalid choice")


if __name__ == "__main__":
    main()