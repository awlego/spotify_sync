#!/usr/bin/env python3
"""
One-time script to catch up on missed Last.fm sync data
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sync_service import SyncService
from shared import DatabaseManager

def main():
    """Run a catch-up sync for the last 24 hours"""
    logger.info("Starting catch-up sync for missed Last.fm data")
    
    # Initialize services
    sync_service = SyncService()
    db = DatabaseManager()
    
    # Get current sync status
    with db.session_scope() as session:
        sync_status = db.get_sync_status(session, 'lastfm')
        current_last_sync = sync_status.last_successful_sync
        logger.info(f"Current last_successful_sync: {current_last_sync}")
    
    # Force sync from 24 hours ago to catch any missed data
    logger.info("Running sync for the last 24 hours of Last.fm data...")
    try:
        # Temporarily set last_successful_sync to 24 hours ago
        with db.session_scope() as session:
            sync_status = db.get_sync_status(session, 'lastfm')
            sync_status.last_successful_sync = datetime.utcnow() - timedelta(hours=24)
            session.commit()
        
        # Run the sync
        tracks_synced = sync_service.sync_lastfm(
            progress_callback=lambda msg, level='info': logger.info(msg)
        )
        
        logger.success(f"Catch-up sync completed! Synced {tracks_synced} tracks")
        
    except Exception as e:
        logger.error(f"Catch-up sync failed: {e}")
        # Restore original timestamp on failure
        with db.session_scope() as session:
            sync_status = db.get_sync_status(session, 'lastfm')
            sync_status.last_successful_sync = current_last_sync
            session.commit()
        raise

if __name__ == "__main__":
    main()