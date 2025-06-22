import time
from typing import Optional, List, Dict, Any
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from loguru import logger

from ..core.config import get_config


class SpotifyClient:
    def __init__(self):
        self.config = get_config().spotify
        self._sp = None
        self._auth_manager = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Spotify client with OAuth"""
        self._auth_manager = SpotifyOAuth(
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            redirect_uri=self.config.redirect_uri,
            scope=self.config.scope,
            username=self.config.username,
            cache_path="data/cache/.spotify_cache"
        )
        
        self._sp = spotipy.Spotify(auth_manager=self._auth_manager)
        logger.info("Spotify client initialized")
    
    def get_auth_url(self) -> str:
        """Get OAuth authorization URL"""
        return self._auth_manager.get_authorize_url()
    
    def process_auth_code(self, code: str) -> bool:
        """Process authorization code from OAuth callback"""
        try:
            self._auth_manager.get_access_token(code, as_dict=False)
            return True
        except Exception as e:
            logger.error(f"Failed to process auth code: {e}")
            return False
    
    def ensure_authenticated(self) -> bool:
        """Ensure client is authenticated, refresh token if needed"""
        try:
            # Try to get current user to test authentication
            self._sp.current_user()
            return True
        except Exception as e:
            logger.warning(f"Authentication check failed: {e}")
            # Try to refresh token
            try:
                token_info = self._auth_manager.get_cached_token()
                if token_info and self._auth_manager.is_token_expired(token_info):
                    logger.info("Refreshing expired token")
                    self._auth_manager.refresh_access_token(token_info['refresh_token'])
                    self._init_client()
                return True
            except Exception as refresh_error:
                logger.error(f"Token refresh failed: {refresh_error}")
                return False
    
    # Track operations
    def search_track(self, track_name: str, artist_name: str, 
                    album_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Search for a track on Spotify"""
        try:
            query = f'track:{track_name} artist:{artist_name}'
            if album_name:
                query += f' album:{album_name}'
            
            results = self._sp.search(q=query, type='track', limit=1)
            
            if results['tracks']['items']:
                return results['tracks']['items'][0]
            
            # Try with less specific search if no results
            query = f'{track_name} {artist_name}'
            results = self._sp.search(q=query, type='track', limit=1)
            
            if results['tracks']['items']:
                track = results['tracks']['items'][0]
                # Verify artist match
                track_artists = [a['name'].lower() for a in track['artists']]
                if artist_name.lower() in ' '.join(track_artists):
                    return track
            
            return None
            
        except Exception as e:
            logger.error(f"Track search failed: {e}")
            return None
    
    def get_track_by_id(self, track_id: str) -> Optional[Dict[str, Any]]:
        """Get track information by Spotify ID"""
        try:
            return self._sp.track(track_id)
        except Exception as e:
            logger.error(f"Failed to get track {track_id}: {e}")
            return None
    
    # Recently played operations
    # NOTE: This method should NOT be used for syncing listening history
    # Last.fm is the only source of truth for listening history
    def get_recently_played(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently played tracks (DEPRECATED for syncing - use Last.fm instead)"""
        try:
            results = self._sp.current_user_recently_played(limit=limit)
            return results['items']
        except Exception as e:
            logger.error(f"Failed to get recently played: {e}")
            return []
    
    # Playlist operations
    def create_playlist(self, name: str, description: str = "", public: bool = False) -> Optional[str]:
        """Create a new playlist and return its ID"""
        try:
            user_id = self._sp.current_user()['id']
            playlist = self._sp.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description
            )
            logger.info(f"Created playlist '{name}' with ID: {playlist['id']}")
            return playlist['id']
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            return None
    
    def get_playlist(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Get playlist information"""
        try:
            return self._sp.playlist(playlist_id)
        except Exception as e:
            logger.error(f"Failed to get playlist {playlist_id}: {e}")
            return None
    
    def get_playlist_tracks(self, playlist_id: str) -> List[str]:
        """Get all track IDs from a playlist"""
        try:
            tracks = []
            results = self._sp.playlist_tracks(playlist_id)
            
            while results:
                tracks.extend([item['track']['id'] for item in results['items'] if item['track']])
                results = self._sp.next(results) if results['next'] else None
            
            return tracks
        except Exception as e:
            logger.error(f"Failed to get playlist tracks: {e}")
            return []
    
    def update_playlist_tracks(self, playlist_id: str, track_ids: List[str]) -> bool:
        """Replace all tracks in a playlist"""
        try:
            # Spotify limits playlist updates to 100 tracks at a time
            self._sp.playlist_replace_items(playlist_id, track_ids[:100])
            
            # Add remaining tracks if playlist is larger than 100
            for i in range(100, len(track_ids), 100):
                self._sp.playlist_add_items(playlist_id, track_ids[i:i+100])
            
            logger.info(f"Updated playlist {playlist_id} with {len(track_ids)} tracks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update playlist: {e}")
            return False
    
    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        """Add tracks to a playlist"""
        try:
            # Add in batches of 100
            for i in range(0, len(track_ids), 100):
                self._sp.playlist_add_items(playlist_id, track_ids[i:i+100])
            
            logger.info(f"Added {len(track_ids)} tracks to playlist {playlist_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add tracks to playlist: {e}")
            return False
    
    # User library operations
    def get_saved_tracks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's saved tracks"""
        try:
            tracks = []
            results = self._sp.current_user_saved_tracks(limit=limit)
            
            while results and len(tracks) < limit:
                tracks.extend(results['items'])
                results = self._sp.next(results) if results['next'] else None
            
            return tracks[:limit]
        except Exception as e:
            logger.error(f"Failed to get saved tracks: {e}")
            return []
    
    # Artist operations
    def get_artist(self, artist_id: str) -> Optional[Dict[str, Any]]:
        """Get artist information"""
        try:
            return self._sp.artist(artist_id)
        except Exception as e:
            logger.error(f"Failed to get artist {artist_id}: {e}")
            return None
    
    def search_artist(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Search for an artist"""
        try:
            results = self._sp.search(q=artist_name, type='artist', limit=1)
            if results['artists']['items']:
                return results['artists']['items'][0]
            return None
        except Exception as e:
            logger.error(f"Artist search failed: {e}")
            return None