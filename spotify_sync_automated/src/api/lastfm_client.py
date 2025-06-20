import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import requests
from loguru import logger

from ..core.config import get_config


class LastFMClient:
    def __init__(self):
        self.config = get_config().lastfm
        self.base_url = "https://ws.audioscrobbler.com/2.0/"
        self.api_key = self.config.api_key
        self.username = self.config.username
        
        if not self.api_key:
            logger.warning("Last.fm API key not configured")
    
    def _make_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a request to the Last.fm API"""
        params = {
            **params,
            'method': method,
            'api_key': self.api_key,
            'format': 'json'
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Last.fm API request failed: {e}")
            return None
        except ValueError as e:
            logger.error(f"Failed to parse Last.fm response: {e}")
            return None
    
    def get_recent_tracks(self, limit: int = 200, page: int = 1, 
                         from_timestamp: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent tracks from Last.fm
        
        Args:
            limit: Number of tracks per page (max 200)
            page: Page number
            from_timestamp: Unix timestamp to fetch tracks after
            
        Returns:
            List of track dictionaries
        """
        params = {
            'user': self.username,
            'limit': min(limit, 200),
            'page': page
        }
        
        if from_timestamp:
            params['from'] = from_timestamp
        
        data = self._make_request('user.getRecentTracks', params)
        
        if not data or 'recenttracks' not in data:
            return []
        
        tracks = data['recenttracks'].get('track', [])
        
        # Filter out currently playing tracks (they don't have a date)
        return [track for track in tracks if 'date' in track]
    
    def get_all_recent_tracks(self, from_timestamp: Optional[int] = None, 
                             max_pages: int = 10) -> List[Dict[str, Any]]:
        """Get all recent tracks, handling pagination
        
        Args:
            from_timestamp: Unix timestamp to fetch tracks after
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of all track dictionaries
        """
        all_tracks = []
        page = 1
        
        while page <= max_pages:
            logger.info(f"Fetching Last.fm page {page}")
            tracks = self.get_recent_tracks(page=page, from_timestamp=from_timestamp)
            
            if not tracks:
                break
            
            all_tracks.extend(tracks)
            page += 1
            
            # Be nice to the API
            time.sleep(0.5)
        
        logger.info(f"Fetched {len(all_tracks)} tracks from Last.fm")
        return all_tracks
    
    def parse_track(self, track_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Last.fm track data into a standardized format"""
        # Handle both string and dict format for artist
        artist = track_data.get('artist', {})
        if isinstance(artist, dict):
            artist_name = artist.get('#text', 'Unknown Artist')
        else:
            artist_name = str(artist)
        
        # Parse timestamp
        date_info = track_data.get('date', {})
        timestamp = int(date_info.get('uts', 0))
        played_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        
        return {
            'artist': artist_name,
            'album': track_data.get('album', {}).get('#text', ''),
            'track': track_data.get('name', 'Unknown Track'),
            'played_at': played_at,
            'mbid': track_data.get('mbid', ''),  # MusicBrainz ID
            'url': track_data.get('url', '')
        }
    
    def get_track_info(self, artist: str, track: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a track"""
        params = {
            'artist': artist,
            'track': track,
            'user': self.username
        }
        
        data = self._make_request('track.getInfo', params)
        
        if not data or 'track' not in data:
            return None
        
        return data['track']
    
    def get_artist_info(self, artist: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an artist"""
        params = {
            'artist': artist
        }
        
        data = self._make_request('artist.getInfo', params)
        
        if not data or 'artist' not in data:
            return None
        
        return data['artist']
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get user information"""
        params = {
            'user': self.username
        }
        
        data = self._make_request('user.getInfo', params)
        
        if not data or 'user' not in data:
            return None
        
        return data['user']
    
    def get_top_artists(self, period: str = 'overall', limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's top artists
        
        Args:
            period: Time period ('overall', '7day', '1month', '3month', '6month', '12month')
            limit: Number of artists to return
        """
        params = {
            'user': self.username,
            'period': period,
            'limit': limit
        }
        
        data = self._make_request('user.getTopArtists', params)
        
        if not data or 'topartists' not in data:
            return []
        
        return data['topartists'].get('artist', [])
    
    def get_top_tracks(self, period: str = 'overall', limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's top tracks
        
        Args:
            period: Time period ('overall', '7day', '1month', '3month', '6month', '12month')
            limit: Number of tracks to return
        """
        params = {
            'user': self.username,
            'period': period,
            'limit': limit
        }
        
        data = self._make_request('user.getTopTracks', params)
        
        if not data or 'toptracks' not in data:
            return []
        
        return data['toptracks'].get('track', [])
    
    def get_listening_history_since(self, since_datetime: datetime) -> List[Dict[str, Any]]:
        """Get all tracks played since a specific datetime"""
        timestamp = int(since_datetime.timestamp())
        tracks = self.get_all_recent_tracks(from_timestamp=timestamp)
        
        # Parse all tracks to standardized format
        return [self.parse_track(track) for track in tracks]