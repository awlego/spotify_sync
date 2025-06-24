#!/usr/bin/env python3
"""
Optimized bulk update for Spotify IDs that deduplicates tracks first
"""
import sys
from pathlib import Path
from loguru import logger
import os
from collections import defaultdict

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))

# Set environment variable to prevent browser opening
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://localhost:6006/callback'

from shared import DatabaseManager, Track
from api.spotify_client import SpotifyClient
from api.spotify_search_improvements import ImprovedSpotifySearch
from time import sleep
from sqlalchemy import and_, func


def bulk_update_spotify_ids_optimized():
    """Run optimized bulk Spotify ID update that deduplicates tracks"""
    db = DatabaseManager()
    
    # Create single instances to reuse
    spotify = SpotifyClient()
    search_helper = ImprovedSpotifySearch()
    
    # Ensure we're authenticated once
    if not spotify.ensure_authenticated():
        logger.error("Failed to authenticate with Spotify")
        return
    
    logger.info("Starting optimized bulk Spotify ID update...")
    
    total_updated = 0
    total_searched = 0
    processed_combinations = set()  # Track what we've already searched
    
    batch_size = 200
    max_iterations = 50
    
    for iteration in range(max_iterations):
        logger.info(f"Iteration {iteration + 1}/{max_iterations}")
        
        with db.session_scope() as session:
            # Get tracks without Spotify IDs
            tracks = session.query(Track).filter(
                Track.spotify_id == None
            ).limit(batch_size).all()
            
            if not tracks:
                logger.info("No more tracks to update")
                break
            
            batch_updates = 0
            
            for track in tracks:
                # Create a unique key for this track/artist combination
                track_key = (track.name.lower(), track.artist.name.lower())
                
                # Skip if we've already searched for this combination
                if track_key in processed_combinations:
                    logger.debug(f"Already searched for '{track.name}' by {track.artist.name}, skipping")
                    continue
                
                processed_combinations.add(track_key)
                
                try:
                    # Search for the track
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
                    
                    total_searched += 1
                    
                    if spotify_track:
                        spotify_id = spotify_track['id']
                        
                        # Check if this Spotify ID is already used
                        existing = session.query(Track).filter(
                            Track.spotify_id == spotify_id
                        ).first()
                        
                        if existing:
                            logger.debug(f"Spotify ID for '{track.name}' already assigned to '{existing.name}'")
                            continue
                        
                        # Find ALL tracks with the same name and artist (including this one)
                        all_versions = session.query(Track).filter(
                            and_(
                                func.lower(Track.name) == track.name.lower(),
                                Track.artist_id == track.artist_id,
                                Track.spotify_id == None
                            )
                        ).all()
                        
                        # Update all versions
                        for version in all_versions:
                            version.spotify_id = spotify_id
                            version.duration_ms = spotify_track['duration_ms']
                            version.popularity = spotify_track['popularity']
                            
                            # Update artist Spotify ID if needed
                            if not version.artist.spotify_id and spotify_track['artists']:
                                artist_spotify_id = spotify_track['artists'][0]['id']
                                # Check if another artist already has this ID
                                from shared import Artist
                                existing_artist = session.query(Artist).filter(
                                    and_(
                                        Artist.spotify_id == artist_spotify_id,
                                        Artist.id != version.artist_id
                                    )
                                ).first()
                                if not existing_artist:
                                    version.artist.spotify_id = artist_spotify_id
                            
                            batch_updates += 1
                            total_updated += 1
                        
                        if len(all_versions) > 1:
                            logger.info(f"Updated {len(all_versions)} versions of '{track.name}' by {track.artist.name}")
                        
                        # Commit after each successful update to avoid constraint errors
                        session.commit()
                        
                except Exception as e:
                    logger.error(f"Error updating '{track.name}' by {track.artist.name}: {e}")
                    session.rollback()
                    continue
            
            logger.info(f"Batch complete: searched {total_searched} unique tracks, updated {batch_updates} track records")
        
        # Rate limiting
        if (iteration + 1) % 5 == 0:
            logger.info("Pausing for 2 seconds to avoid rate limiting...")
            sleep(2)
        else:
            sleep(0.1)
    
    logger.success(f"Optimized bulk update complete! Searched {total_searched} unique track/artist combinations, "
                  f"updated {total_updated} total track records")


if __name__ == "__main__":
    bulk_update_spotify_ids_optimized()