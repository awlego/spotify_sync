#!/usr/bin/env python3
"""Sync Spotify IDs for tracks imported from Last.fm"""

import os
import sys
import time
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.sync_service import SyncService
from src.core.database import DatabaseManager
from src.core.models import Track
from src.api.spotify_client import SpotifyClient

def main():
    logger.info("Starting Spotify ID sync...")
    
    # Check if we can authenticate with Spotify
    spotify = SpotifyClient()
    if not spotify.ensure_authenticated():
        logger.error("Spotify authentication required!")
        logger.info("\nTo authenticate with Spotify, run:")
        logger.info("  python auth_spotify.py")
        logger.info("\nThis will:")
        logger.info("1. Open a browser for Spotify login")
        logger.info("2. Save authentication token for future use")
        logger.info("3. Allow this script to access your Spotify account")
        return
    
    logger.info("Spotify authentication successful!")
    
    # Initialize services
    sync_service = SyncService()
    db = sync_service.db
    
    # Check how many tracks need Spotify IDs
    with db.session_scope() as session:
        total_without_ids = session.query(Track).filter(Track.spotify_id == None).count()
        total_tracks = session.query(Track).count()
        
    logger.info(f"Total tracks: {total_tracks}")
    logger.info(f"Tracks without Spotify IDs: {total_without_ids}")
    
    if total_without_ids == 0:
        logger.info("All tracks already have Spotify IDs!")
        return
    
    # Sync in batches
    batch_size = 100
    total_updated = 0
    batch_count = 0
    failed_batches = 0
    
    # Calculate estimated time
    estimated_batches = (total_without_ids + batch_size - 1) // batch_size
    logger.info(f"Estimated batches to process: {estimated_batches}")
    logger.info("Note: Spotify API has rate limits. This may take some time...")
    
    while True:
        batch_count += 1
        logger.info(f"\nProcessing batch {batch_count} (up to {batch_size} tracks)...")
        
        try:
            updated = sync_service.sync_spotify_ids(limit=batch_size)
            
            if updated == 0:
                # Check if we still have tracks without IDs
                with db.session_scope() as session:
                    remaining = session.query(Track).filter(Track.spotify_id == None).count()
                
                if remaining > 0:
                    logger.warning(f"No tracks updated but {remaining} still need IDs. May be rate limited.")
                    failed_batches += 1
                    
                    if failed_batches >= 3:
                        logger.error("Multiple failed batches. Spotify API may be rate limiting.")
                        logger.info("Try running this script again later.")
                        break
                    
                    # Wait a bit before retrying
                    logger.info("Waiting 30 seconds before retry...")
                    time.sleep(30)
                    continue
                else:
                    break
            
            failed_batches = 0  # Reset failed counter on success
            total_updated += updated
            
            # Progress update
            progress = (total_tracks - total_without_ids + total_updated) / total_tracks * 100
            logger.info(f"✓ Updated {updated} tracks in this batch")
            logger.info(f"Progress: {progress:.1f}% ({total_tracks - total_without_ids + total_updated}/{total_tracks} tracks have Spotify IDs)")
            
            # Check remaining
            with db.session_scope() as session:
                remaining = session.query(Track).filter(Track.spotify_id == None).count()
                
            if remaining == 0:
                break
                
            # Small delay to respect rate limits
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error in batch {batch_count}: {e}")
            failed_batches += 1
            
            if failed_batches >= 3:
                logger.error("Too many errors. Stopping sync.")
                break
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Spotify ID sync complete!")
    logger.info(f"Total tracks updated: {total_updated}")
    logger.info(f"Total batches processed: {batch_count}")
    
    if total_updated > 0:
        logger.info("\n✅ You can now update your Spotify playlists!")
        logger.info("Run: python run.py")
        logger.info("Then visit: http://localhost:6006")

if __name__ == "__main__":
    main()