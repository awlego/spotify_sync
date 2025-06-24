#!/usr/bin/env python3
"""
Create 'Most Recently Played' playlist on Spotify
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))

from api.spotify_client import SpotifyClient

def main():
    spotify = SpotifyClient()
    
    # Create playlist
    playlist_name = "Most Recently Played"
    description = "The last 50 songs I've listened to, in reverse chronological order. Auto-updated by spotify_sync."
    
    playlist_id = spotify.create_playlist(playlist_name, description, public=False)
    
    if playlist_id:
        print(f"Successfully created playlist: {playlist_name}")
        print(f"Playlist ID: {playlist_id}")
        print(f"\nAdd this to your .env file:")
        print(f"MOST_RECENTLY_PLAYED_ID='{playlist_id}'")
    else:
        print("Failed to create playlist")
        sys.exit(1)

if __name__ == "__main__":
    main()