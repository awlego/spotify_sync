#!/usr/bin/env python3
"""
Sync Last.fm history in chunks with better progress tracking
"""

import sys
import os
from datetime import datetime, timedelta
from loguru import logger
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import DatabaseManager
from src.api.lastfm_client import LastFMClient
from src.core.models import PlayHistory


def sync_year_chunk(lastfm_client, db_manager, year):
    """Sync one year of data"""
    start_date = datetime(year, 1, 1)
    end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    
    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())
    
    logger.info(f"\nSyncing year {year} ({start_date.date()} to {end_date.date()})")
    
    tracks_added = 0
    
    # Fetch tracks for this year
    tracks = lastfm_client.get_all_recent_tracks(
        from_timestamp=start_timestamp,
        max_pages=200  # Limit pages per year
    )
    
    if not tracks:
        logger.info(f"No tracks found for {year}")
        return 0
    
    logger.info(f"Fetched {len(tracks)} tracks for {year}")
    
    # Process in batches
    batch_size = 500
    for i in range(0, len(tracks), batch_size):
        batch = tracks[i:i + batch_size]
        
        with db_manager.session_scope() as session:
            for track_data in batch:
                try:
                    parsed = lastfm_client.parse_track(track_data)
                    
                    # Skip if outside our year range
                    if parsed['played_at'].year != year:
                        continue
                    
                    track = db_manager.get_or_create_track(
                        session,
                        name=parsed['track'],
                        artist_name=parsed['artist'],
                        album_name=parsed['album'] if parsed['album'] else None
                    )
                    
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
            
            session.commit()
            logger.info(f"  Processed batch {i//batch_size + 1}/{(len(tracks)-1)//batch_size + 1}, "
                       f"added {tracks_added} tracks so far for {year}")
    
    return tracks_added


def main():
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )
    
    logger.info("=== Last.fm History Sync (Chunked) ===")
    
    # Initialize clients
    lastfm = LastFMClient()
    db = DatabaseManager()
    
    # Get user info
    user_info = lastfm.get_user_info()
    if not user_info:
        logger.error("Failed to connect to Last.fm API")
        return 1
    
    logger.info(f"Connected to Last.fm as: {user_info['name']}")
    logger.info(f"Total scrobbles on Last.fm: {user_info['playcount']}")
    
    # Get current database status
    with db.session_scope() as session:
        current_plays = session.query(PlayHistory).filter_by(source='lastfm').count()
        logger.info(f"Current plays in database: {current_plays:,}")
        
        # Find date range in database
        oldest = session.query(PlayHistory).order_by(PlayHistory.played_at.asc()).first()
        newest = session.query(PlayHistory).order_by(PlayHistory.played_at.desc()).first()
        
        if oldest:
            logger.info(f"Database contains: {oldest.played_at.date()} to {newest.played_at.date()}")
    
    # Determine registration year
    registered = user_info.get('registered', {})
    if isinstance(registered, dict) and '#text' in registered:
        reg_timestamp = int(registered['#text'])
    else:
        reg_timestamp = int(time.mktime(datetime(2019, 1, 1).timetuple()))
    
    reg_date = datetime.fromtimestamp(reg_timestamp)
    start_year = reg_date.year
    current_year = datetime.now().year
    
    logger.info(f"Will sync from {start_year} to {current_year}")
    
    # Sync each year
    total_added = 0
    start_time = time.time()
    
    for year in range(start_year, current_year + 1):
        year_start = time.time()
        added = sync_year_chunk(lastfm, db, year)
        total_added += added
        
        year_time = time.time() - year_start
        logger.success(f"Year {year} complete: {added} tracks added in {year_time:.1f}s")
        
        # Update sync status
        with db.session_scope() as session:
            db.update_sync_status(session, 'lastfm', 'success', tracks_synced=added)
    
    # Final statistics
    total_time = time.time() - start_time
    logger.success(f"\nSync complete! Added {total_added:,} tracks in {total_time:.1f}s")
    
    with db.session_scope() as session:
        from src.core.models import Track, Artist
        
        total_tracks = session.query(Track).count()
        total_plays = session.query(PlayHistory).count()
        total_artists = session.query(Artist).count()
        
        logger.info(f"\nFinal database statistics:")
        logger.info(f"  Total tracks: {total_tracks:,}")
        logger.info(f"  Total plays: {total_plays:,}")
        logger.info(f"  Total artists: {total_artists:,}")
        logger.info(f"  Sync rate: {total_added/total_time:.1f} tracks/second")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())