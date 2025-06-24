#!/usr/bin/env python3
"""
Test Last.fm API to see recent tracks
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sync_service.api.lastfm_client import LastFMClient

def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")
    
    client = LastFMClient()
    
    # Check the last 24 hours
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    from_timestamp = int(since.timestamp())
    
    logger.info(f"Fetching tracks since: {since} (timestamp: {from_timestamp})")
    
    # Get one page to see what's available
    try:
        response = client._make_request('user.getRecentTracks', {
            'from': from_timestamp,
            'limit': 10,
            'page': 1
        })
        
        if response and 'recenttracks' in response:
            tracks = response['recenttracks']['track']
            if isinstance(tracks, dict):
                tracks = [tracks]
            
            logger.info(f"Found {len(tracks)} tracks in the last 24 hours")
            
            for track in tracks[:5]:  # Show first 5
                # Handle currently playing track
                if '@attr' in track and 'nowplaying' in track['@attr']:
                    logger.info(f"NOW PLAYING: {track['artist']['#text']} - {track['name']}")
                else:
                    date_str = track.get('date', {}).get('#text', 'Unknown')
                    logger.info(f"{date_str}: {track['artist']['#text']} - {track['name']}")
            
            # Check total available
            total = response['recenttracks'].get('@attr', {}).get('total', 0)
            logger.info(f"\nTotal tracks available: {total}")
        else:
            logger.error("No tracks found in response")
            
    except Exception as e:
        logger.error(f"Error fetching tracks: {e}")

if __name__ == "__main__":
    main()