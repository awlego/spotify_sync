#!/usr/bin/env python3
"""
Bulk update Spotify IDs using improved search strategies
"""
import sys
from pathlib import Path
from loguru import logger
import os

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))

# Set environment variable to prevent browser opening
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://localhost:6006/callback'

from shared import DatabaseManager, Track
from api.spotify_client import SpotifyClient
from api.spotify_search_improvements import ImprovedSpotifySearch
from time import sleep
from sqlalchemy import and_


def bulk_update_spotify_ids():
    """Run bulk Spotify ID update with proper client reuse"""
    db = DatabaseManager()
    
    # Create single instances to reuse
    spotify = SpotifyClient()
    search_helper = ImprovedSpotifySearch()
    
    # Ensure we're authenticated once
    if not spotify.ensure_authenticated():
        logger.error("Failed to authenticate with Spotify")
        return
    
    logger.info("Starting bulk Spotify ID update...")
    
    total_updated = 0
    total_skipped = 0
    iterations = 0
    max_iterations = 50  # Process up to 10,000 tracks (200 per iteration)
    
    while iterations < max_iterations:
        logger.info(f"Iteration {iterations + 1}/{max_iterations}")
        
        updated = 0
        skipped = 0
        
        with db.session_scope() as session:
            # Get tracks without Spotify IDs
            tracks = session.query(Track).filter(
                Track.spotify_id == None
            ).limit(200).all()
            
            if not tracks:
                logger.info("No more tracks to update")
                break
            
            for track in tracks:
                try:
                    # Try improved search first
                    spotify_track = search_helper.search_track_flexible(
                        spotify._sp,
                        track.name,
                        track.artist.name,
                        track.album.name if track.album else None
                    )
                    
                    # If no match, try finding alternative versions
                    if not spotify_track:
                        spotify_track = search_helper.find_alternative_versions(
                            spotify._sp,
                            track.name,
                            track.artist.name
                        )
                    
                    # Final fallback to original search
                    if not spotify_track:
                        spotify_track = spotify.search_track(
                            track.name,
                            track.artist.name,
                            track.album.name if track.album else None
                        )
                    
                    if spotify_track:
                        spotify_id = spotify_track['id']
                        
                        # Check if another track already has this Spotify ID
                        existing = session.query(Track).filter(
                            and_(
                                Track.spotify_id == spotify_id,
                                Track.id != track.id
                            )
                        ).first()
                        
                        if existing:
                            # Skip this track - it's a duplicate
                            skipped += 1
                            logger.debug(f"Skipping duplicate: '{track.name}' by {track.artist.name} - "
                                       f"Spotify ID already assigned to '{existing.name}'")
                            continue
                        
                        # Update the track
                        track.spotify_id = spotify_id
                        track.duration_ms = spotify_track['duration_ms']
                        track.popularity = spotify_track['popularity']
                        
                        # Update artist Spotify ID if needed
                        if not track.artist.spotify_id and spotify_track['artists']:
                            track.artist.spotify_id = spotify_track['artists'][0]['id']
                        
                        # Commit this individual update to avoid constraint errors
                        session.commit()
                        updated += 1
                            
                except Exception as e:
                    logger.error(f"Error updating track '{track.name}' by {track.artist.name}: {e}")
                    session.rollback()  # Rollback the failed transaction
                    continue
        
        total_updated += updated
        total_skipped += skipped
        iterations += 1
        
        logger.info(f"Updated {updated} tracks, skipped {skipped} duplicates in this batch. Total updated: {total_updated}")
        
        # Small delay to avoid rate limiting
        if iterations % 5 == 0:
            logger.info("Pausing for 2 seconds to avoid rate limiting...")
            sleep(2)
        else:
            sleep(0.1)  # Small delay between batches
    
    logger.success(f"Bulk update complete! Total tracks updated: {total_updated}, Total skipped: {total_skipped}")


if __name__ == "__main__":
    bulk_update_spotify_ids()