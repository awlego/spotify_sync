#!/usr/bin/env python3
"""
Monitor ongoing sync status with live updates
"""

import sys
import os
import time
from datetime import datetime
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import DatabaseManager
from src.api.lastfm_client import LastFMClient


def format_time(seconds):
    """Format seconds into human readable time"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def main():
    logger.remove()
    
    db = DatabaseManager()
    lastfm = LastFMClient()
    
    # Get Last.fm total
    user_info = lastfm.get_user_info()
    lastfm_total = int(user_info.get('playcount', 0)) if user_info else 0
    
    print("\033[2J\033[H")  # Clear screen
    print("=== Last.fm Sync Monitor ===")
    print("Press Ctrl+C to exit\n")
    
    try:
        while True:
            with db.session_scope() as session:
                from src.core.models import PlayHistory
                
                # Get progress
                progress = db.get_sync_progress(session, 'lastfm_full')
                db_plays = session.query(PlayHistory).filter_by(source='lastfm').count()
                
                # Clear and update display
                print("\033[5;0H")  # Move cursor to line 5
                print("\033[J")     # Clear from cursor to end
                
                print(f"Status: {progress.status}")
                print(f"Current chunk: {progress.current_chunk} (Month {progress.total_chunks_completed}/76)")
                print(f"Tracks synced: {progress.total_tracks_synced:,}")
                print(f"Database total: {db_plays:,}")
                print(f"Last.fm total: {lastfm_total:,}")
                print(f"Remaining: {lastfm_total - db_plays:,}")
                
                # Progress bar
                percent = (db_plays / lastfm_total * 100) if lastfm_total > 0 else 0
                bar_width = 50
                filled = int(bar_width * percent / 100)
                bar = '█' * filled + '░' * (bar_width - filled)
                print(f"\nProgress: [{bar}] {percent:.1f}%")
                
                # Time estimate
                if progress.status == 'running' and progress.started_at:
                    elapsed = (datetime.utcnow() - progress.started_at).total_seconds()
                    if progress.total_tracks_synced > 0:
                        rate = progress.total_tracks_synced / elapsed
                        remaining_tracks = lastfm_total - db_plays
                        eta_seconds = remaining_tracks / rate if rate > 0 else 0
                        
                        print(f"\nRate: {rate:.1f} tracks/second")
                        print(f"Elapsed: {format_time(elapsed)}")
                        print(f"ETA: {format_time(eta_seconds)}")
                
                print(f"\nLast updated: {datetime.now().strftime('%H:%M:%S')}")
                
                if progress.status == 'completed':
                    print("\n✅ Sync completed!")
                    break
                elif progress.status == 'error':
                    print(f"\n❌ Error: {progress.last_error}")
                    break
                
                time.sleep(5)  # Update every 5 seconds
                
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


if __name__ == "__main__":
    main()