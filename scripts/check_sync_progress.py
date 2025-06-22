#!/usr/bin/env python3
"""
Check sync progress status
"""

import sys
import os
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import DatabaseManager


def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")
    
    db = DatabaseManager()
    
    with db.session_scope() as session:
        progress = db.get_sync_progress(session, 'lastfm_full')
        
        logger.info("=== Last.fm Full Sync Progress ===")
        logger.info(f"Status: {progress.status}")
        logger.info(f"Current chunk: {progress.current_chunk}")
        logger.info(f"Last page: {progress.last_page}")
        logger.info(f"Chunks completed: {progress.total_chunks_completed}/76")
        logger.info(f"Total tracks synced: {progress.total_tracks_synced:,}")
        logger.info(f"API calls made: {progress.api_calls_made:,}")
        logger.info(f"Started at: {progress.started_at}")
        logger.info(f"Last updated: {progress.updated_at}")
        
        if progress.error_count > 0:
            logger.warning(f"Error count: {progress.error_count}")
            logger.warning(f"Last error: {progress.last_error}")
        
        # Calculate progress percentage
        if progress.total_chunks_completed:
            percent = (progress.total_chunks_completed / 76) * 100
            logger.info(f"\nProgress: {percent:.1f}% complete")
            
            # Estimate completion
            if progress.status == 'running' and progress.started_at:
                elapsed = (progress.updated_at - progress.started_at).total_seconds()
                rate = progress.total_chunks_completed / (elapsed / 60)  # chunks per minute
                remaining = 76 - progress.total_chunks_completed
                eta_minutes = remaining / rate if rate > 0 else 0
                logger.info(f"Estimated time remaining: {int(eta_minutes)} minutes")


if __name__ == "__main__":
    main()