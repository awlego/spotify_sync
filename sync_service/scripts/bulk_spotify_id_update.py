#!/usr/bin/env python3
"""
Bulk update Spotify IDs using improved search strategies
"""
import sys
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))

from services.sync_service import SyncService
from time import sleep


def main():
    """Run bulk Spotify ID update"""
    sync_service = SyncService()
    
    logger.info("Starting bulk Spotify ID update...")
    
    total_updated = 0
    iterations = 0
    max_iterations = 50  # Process up to 10,000 tracks (200 per iteration)
    
    while iterations < max_iterations:
        logger.info(f"Iteration {iterations + 1}/{max_iterations}")
        
        # Process 200 tracks at a time
        updated = sync_service.sync_spotify_ids(limit=200)
        
        if updated == 0:
            logger.info("No more tracks to update or all remaining tracks cannot be found")
            break
            
        total_updated += updated
        iterations += 1
        
        logger.info(f"Updated {updated} tracks in this batch. Total: {total_updated}")
        
        # Small delay to avoid rate limiting
        if iterations % 5 == 0:
            logger.info("Pausing for 2 seconds to avoid rate limiting...")
            sleep(2)
    
    logger.success(f"Bulk update complete! Total tracks updated: {total_updated}")


if __name__ == "__main__":
    main()