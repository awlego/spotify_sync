#!/usr/bin/env python3
"""
Check recent listening history from the database
"""

import sys
import os
from datetime import datetime, timedelta
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.database import DatabaseManager
from shared.models import PlayHistory, Track, Artist


def format_time_ago(timestamp):
    """Format timestamp as 'X minutes/hours/days ago'"""
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff < timedelta(minutes=1):
        return "just now"
    elif diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    else:
        days = diff.days
        return f"{days} day{'s' if days > 1 else ''} ago"


def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")
    
    db = DatabaseManager()
    
    with db.session_scope() as session:
        # Get the most recent plays
        recent_plays = db.get_recent_plays(session, limit=20)
        
        if not recent_plays:
            logger.warning("No plays found in the database")
            return
        
        # Show the most recent play
        most_recent = recent_plays[0]
        logger.info(f"Most recent play: {most_recent.played_at}")
        logger.info(f"  {most_recent.track.artist.name} - {most_recent.track.name}")
        logger.info(f"  {format_time_ago(most_recent.played_at)}")
        logger.info(f"  Source: {most_recent.source}")
        
        # Show recent listening history
        logger.info("\nRecent listening history:")
        logger.info("-" * 80)
        
        for play in recent_plays:
            time_str = play.played_at.strftime("%Y-%m-%d %H:%M:%S")
            time_ago = format_time_ago(play.played_at)
            artist = play.track.artist.name
            track = play.track.name
            album = play.track.album.name if play.track.album else "No Album"
            
            logger.info(f"{time_str} ({time_ago:>15})")
            logger.info(f"  {artist} - {track}")
            logger.info(f"  Album: {album}")
            logger.info("")
        
        # Check sync status
        sync_status = db.get_sync_status(session, 'lastfm')
        if sync_status.last_successful_sync:
            logger.info(f"Last successful sync: {sync_status.last_successful_sync}")
            logger.info(f"  {format_time_ago(sync_status.last_successful_sync)}")
            logger.info(f"  Status: {sync_status.status}")
            
            # Check if sync might be needed
            if most_recent.played_at < datetime.utcnow() - timedelta(hours=1):
                logger.warning(f"\n⚠️  Last play was {format_time_ago(most_recent.played_at)} - sync might be needed!")


if __name__ == "__main__":
    main()