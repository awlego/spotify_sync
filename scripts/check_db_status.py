#!/usr/bin/env python3
"""
Check database status and find sync gaps
"""

import sys
import os
from datetime import datetime
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import DatabaseManager
from src.core.models import PlayHistory, Track, Artist


def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")
    
    db = DatabaseManager()
    
    with db.session_scope() as session:
        # Get total counts
        total_plays = session.query(PlayHistory).count()
        lastfm_plays = session.query(PlayHistory).filter_by(source='lastfm').count()
        spotify_plays = session.query(PlayHistory).filter_by(source='spotify').count()
        
        logger.info(f"Total plays in database: {total_plays:,}")
        logger.info(f"  - Last.fm plays: {lastfm_plays:,}")
        # Note: Spotify plays may exist from before the change to Last.fm-only syncing
        if spotify_plays > 0:
            logger.info(f"  - Spotify plays (legacy): {spotify_plays:,}")
        
        # Get date range
        oldest = session.query(PlayHistory).order_by(PlayHistory.played_at.asc()).first()
        newest = session.query(PlayHistory).order_by(PlayHistory.played_at.desc()).first()
        
        if oldest and newest:
            logger.info(f"\nDate range:")
            logger.info(f"  Oldest play: {oldest.played_at} ({oldest.track.artist.name} - {oldest.track.name})")
            logger.info(f"  Newest play: {newest.played_at} ({newest.track.artist.name} - {newest.track.name})")
            
            # Calculate days covered
            days_covered = (newest.played_at - oldest.played_at).days
            logger.info(f"  Days covered: {days_covered:,}")
            
        # Check for gaps
        from sqlalchemy import func
        daily_counts = session.query(
            func.date(PlayHistory.played_at).label('date'),
            func.count(PlayHistory.id).label('count')
        ).group_by('date').all()
        
        if daily_counts:
            dates = [datetime.strptime(str(dc.date), '%Y-%m-%d').date() for dc in daily_counts]
            min_date = min(dates)
            max_date = max(dates)
            
            expected_days = (max_date - min_date).days + 1
            actual_days = len(dates)
            
            logger.info(f"\nData completeness:")
            logger.info(f"  Days with data: {actual_days:,}")
            logger.info(f"  Expected days: {expected_days:,}")
            logger.info(f"  Missing days: {expected_days - actual_days:,}")
            
        # Show sync status
        sync_status = db.get_sync_status(session, 'lastfm')
        if sync_status.last_successful_sync:
            logger.info(f"\nLast successful sync: {sync_status.last_successful_sync}")
            logger.info(f"Total tracks synced: {sync_status.tracks_synced:,}")


if __name__ == "__main__":
    main()