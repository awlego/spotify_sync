#!/usr/bin/env python3
"""
Script to sync entire Last.fm listening history
"""

import sys
import os
from datetime import datetime, timedelta
from loguru import logger
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.config import get_config
from src.core.database import DatabaseManager
from src.api.lastfm_client import LastFMClient


def setup_logging(verbose=False):
    """Configure logging"""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )


def sync_lastfm_batch(lastfm_client, db_manager, from_timestamp=None, to_timestamp=None):
    """Sync a batch of Last.fm tracks"""
    tracks_added = 0
    
    # Fetch tracks
    if from_timestamp:
        from_date = datetime.fromtimestamp(from_timestamp)
        logger.info(f"Fetching tracks from {from_date}")
    else:
        logger.info("Fetching all tracks")
        
    tracks = lastfm_client.get_all_recent_tracks(
        from_timestamp=from_timestamp,
        max_pages=1000  # Increase max pages for full history
    )
    
    logger.info(f"Fetched {len(tracks)} tracks from Last.fm")
    
    # Process tracks in batches
    batch_size = 1000
    for i in range(0, len(tracks), batch_size):
        batch = tracks[i:i + batch_size]
        
        with db_manager.session_scope() as session:
            for track_data in batch:
                try:
                    # Parse track data
                    parsed = lastfm_client.parse_track(track_data)
                    
                    # Get or create track
                    track = db_manager.get_or_create_track(
                        session,
                        name=parsed['track'],
                        artist_name=parsed['artist'],
                        album_name=parsed['album'] if parsed['album'] else None
                    )
                    
                    # Add play
                    play = db_manager.add_play(
                        session,
                        track,
                        parsed['played_at'],
                        source='lastfm'
                    )
                    
                    if play:
                        tracks_added += 1
                        
                except Exception as e:
                    logger.error(f"Error processing track: {e}")
                    continue
            
            # Commit batch
            session.commit()
            logger.info(f"Processed batch {i//batch_size + 1}, added {tracks_added} tracks so far")
    
    return tracks_added


def get_oldest_scrobble_time(lastfm_client):
    """Get the timestamp of the user's first scrobble"""
    user_info = lastfm_client.get_user_info()
    if user_info and 'registered' in user_info:
        # Get registration timestamp
        registered = user_info['registered']
        if isinstance(registered, dict) and '#text' in registered:
            return int(registered['#text'])
        elif isinstance(registered, (int, str)):
            return int(registered)
    return None


def main():
    parser = argparse.ArgumentParser(description='Sync Last.fm listening history')
    parser.add_argument('--days', type=int, help='Number of days to sync (default: all)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--show-stats', action='store_true', help='Show database statistics after sync')
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    logger.info("=== Last.fm History Sync ===")
    
    # Initialize clients
    config = get_config()
    lastfm = LastFMClient()
    db = DatabaseManager()
    
    # Test Last.fm connection
    user_info = lastfm.get_user_info()
    if not user_info:
        logger.error("Failed to connect to Last.fm API")
        return 1
    
    logger.info(f"Connected to Last.fm as: {user_info['name']}")
    logger.info(f"Total scrobbles on Last.fm: {user_info['playcount']}")
    
    # Check current database stats
    with db.session_scope() as session:
        from src.core.models import PlayHistory
        current_plays = session.query(PlayHistory).filter_by(source='lastfm').count()
        logger.info(f"Current plays in database: {current_plays}")
    
    # Determine sync range
    if args.days:
        from_timestamp = int((datetime.now() - timedelta(days=args.days)).timestamp())
        logger.info(f"Syncing last {args.days} days")
    else:
        # Try to get oldest scrobble time
        from_timestamp = get_oldest_scrobble_time(lastfm)
        if from_timestamp:
            from_date = datetime.fromtimestamp(from_timestamp)
            logger.info(f"Syncing from account registration: {from_date}")
        else:
            # Default to 10 years
            from_timestamp = int((datetime.now() - timedelta(days=365*10)).timestamp())
            logger.info("Syncing last 10 years (couldn't determine registration date)")
    
    # Perform sync
    try:
        tracks_added = sync_lastfm_batch(lastfm, db, from_timestamp=from_timestamp)
        logger.success(f"Sync complete! Added {tracks_added} new plays")
        
        # Update sync status
        with db.session_scope() as session:
            db.update_sync_status(session, 'lastfm', 'success', tracks_synced=tracks_added)
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        import traceback
        traceback.print_exc()
        
        with db.session_scope() as session:
            db.update_sync_status(session, 'lastfm', 'error', error_message=str(e))
        return 1
    
    # Show statistics if requested
    if args.show_stats:
        logger.info("\n=== Database Statistics ===")
        with db.session_scope() as session:
            from src.core.models import Track, PlayHistory, Artist
            
            total_tracks = session.query(Track).count()
            total_plays = session.query(PlayHistory).count()
            total_artists = session.query(Artist).count()
            lastfm_plays = session.query(PlayHistory).filter_by(source='lastfm').count()
            
            logger.info(f"Total tracks: {total_tracks:,}")
            logger.info(f"Total plays: {total_plays:,}")
            logger.info(f"Total artists: {total_artists:,}")
            logger.info(f"Last.fm plays: {lastfm_plays:,}")
            
            # Top artists
            top_artists = db.get_top_artists(session, limit=10)
            logger.info("\nTop 10 Artists:")
            for i, (artist, count) in enumerate(top_artists, 1):
                logger.info(f"  {i:2d}. {artist.name} ({count:,} plays)")
            
            # Top tracks
            top_tracks = db.get_play_counts(session)[:10]
            logger.info("\nTop 10 Tracks:")
            for i, (track, count) in enumerate(top_tracks, 1):
                logger.info(f"  {i:2d}. {track.artist.name} - {track.name} ({count:,} plays)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())