#!/usr/bin/env python3
"""Authenticate with Spotify and save the token cache"""

import os
import sys
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.spotify_client import SpotifyClient

def main():
    logger.info("Spotify Authentication Helper")
    logger.info("="*50)
    
    # Initialize Spotify client
    spotify = SpotifyClient()
    
    # Check if already authenticated
    if spotify.ensure_authenticated():
        logger.info("✅ Already authenticated with Spotify!")
        return
    
    logger.info("Need to authenticate with Spotify...")
    logger.info("\nThis will open a browser window for authentication.")
    logger.info("After logging in and authorizing the app, you'll be redirected.")
    logger.info("The redirect URL will start with: http://localhost:6006/callback")
    logger.info("Copy the ENTIRE URL from the browser and paste it here.")
    
    try:
        # Get the auth URL
        auth_url = spotify.get_auth_url()
        logger.info(f"\nOpen this URL in your browser:\n{auth_url}")
        
        # Wait for user to paste the callback URL
        logger.info("\nAfter authorizing, paste the ENTIRE redirect URL here:")
        logger.info("(It should start with http://localhost:6006/callback?code=...)")
        redirect_url = input().strip()
        
        # Extract the code from the URL
        if 'code=' in redirect_url:
            code = redirect_url.split('code=')[1].split('&')[0]
            logger.info(f"Extracted authorization code: {code[:10]}...")
            
            # Process the auth code
            if spotify.process_auth_code(code):
                logger.info("✅ Authentication successful! Token saved.")
                logger.info("You can now run sync_spotify_ids.py")
            else:
                logger.error("❌ Failed to process authorization code")
        else:
            logger.error("❌ No authorization code found in the URL")
            logger.info("Make sure you copied the ENTIRE URL including the '?code=...' part")
            
    except KeyboardInterrupt:
        logger.info("\nAuthentication cancelled.")
    except Exception as e:
        logger.error(f"Authentication error: {e}")

if __name__ == "__main__":
    main()