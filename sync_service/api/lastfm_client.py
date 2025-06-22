import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from config import get_config


class LastFMClient:
    """Client for interacting with Last.fm API"""
    
    def __init__(self):
        self.config = get_config()
        self.api_key = self.config.lastfm.api_key
        self.username = self.config.lastfm.username
        self.base_url = 'https://ws.audioscrobbler.com/2.0/'
        self.session = requests.Session()
        self.rate_limit_delay = 0.2  # Initial delay between requests
        self.max_retries = 3
        
    def _make_request(self, method: str, params: Dict[str, Any], retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Make a request to Last.fm API with retry logic"""
        params.update({
            'api_key': self.api_key,
            'method': method,
            'format': 'json'
        })
        
        try:
            # Rate limiting delay
            time.sleep(self.rate_limit_delay)
            
            response = self.session.get(self.base_url, params=params, timeout=30)
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self._make_request(method, params, retry_count)
            
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors
            if 'error' in data:
                error_code = data.get('error')
                error_msg = data.get('message', 'Unknown error')
                
                # Handle specific error codes
                if error_code == 29:  # Rate limit exceeded
                    self.rate_limit_delay = min(self.rate_limit_delay * 2, 5)  # Exponential backoff
                    logger.warning(f"Rate limit error. Increasing delay to {self.rate_limit_delay}s")
                    time.sleep(5)
                    return self._make_request(method, params, retry_count)
                
                logger.error(f"Last.fm API error {error_code}: {error_msg}")
                return None
            
            # Success - reduce rate limit delay slightly
            self.rate_limit_delay = max(self.rate_limit_delay * 0.9, 0.2)
            return data
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout on {method}")
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(wait_time)
                return self._make_request(method, params, retry_count + 1)
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {method}: {e}")
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                logger.info(f"Retrying in {wait_time} seconds... (attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(wait_time)
                return self._make_request(method, params, retry_count + 1)
            return None
    
    def get_recent_tracks(self, limit: int = 200, page: int = 1, 
                         from_timestamp: Optional[int] = None,
                         to_timestamp: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent tracks from Last.fm
        
        Args:
            limit: Number of tracks per page (max 200)
            page: Page number
            from_timestamp: Unix timestamp to fetch tracks after
            to_timestamp: Unix timestamp to fetch tracks before
            
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
        if to_timestamp:
            params['to'] = to_timestamp
        
        data = self._make_request('user.getRecentTracks', params)
        
        if not data or 'recenttracks' not in data:
            return []
        
        tracks = data['recenttracks'].get('track', [])
        
        # Filter out currently playing tracks (they don't have a date)
        return [track for track in tracks if 'date' in track]
    
    def get_recent_tracks_with_info(self, limit: int = 200, page: int = 1,
                                   from_timestamp: Optional[int] = None,
                                   to_timestamp: Optional[int] = None) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Get recent tracks with pagination info
        
        Returns:
            Tuple of (tracks, info) where info contains total pages, total tracks, etc.
        """
        params = {
            'user': self.username,
            'limit': min(limit, 200),
            'page': page
        }
        
        if from_timestamp:
            params['from'] = from_timestamp
        if to_timestamp:
            params['to'] = to_timestamp
        
        data = self._make_request('user.getRecentTracks', params)
        
        if not data or 'recenttracks' not in data:
            return [], {}
        
        tracks_data = data['recenttracks']
        tracks = tracks_data.get('track', [])
        
        # Filter out currently playing tracks
        valid_tracks = [track for track in tracks if 'date' in track]
        
        # Extract pagination info
        info = {
            'page': int(tracks_data.get('@attr', {}).get('page', 1)),
            'perPage': int(tracks_data.get('@attr', {}).get('perPage', 200)),
            'totalPages': int(tracks_data.get('@attr', {}).get('totalPages', 1)),
            'total': int(tracks_data.get('@attr', {}).get('total', 0))
        }
        
        return valid_tracks, info
    
    def get_all_recent_tracks(self, from_timestamp: Optional[int] = None,
                             to_timestamp: Optional[int] = None, 
                             max_pages: int = 10) -> List[Dict[str, Any]]:
        """Get all recent tracks, handling pagination
        
        Args:
            from_timestamp: Unix timestamp to fetch tracks after
            to_timestamp: Unix timestamp to fetch tracks before
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of all track dictionaries
        """
        all_tracks = []
        page = 1
        
        while page <= max_pages:
            logger.info(f"Fetching Last.fm page {page}")
            tracks, info = self.get_recent_tracks_with_info(
                page=page, 
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp
            )
            
            if not tracks:
                break
            
            all_tracks.extend(tracks)
            
            # Check if we've reached the last page
            if page >= info.get('totalPages', 1):
                break
                
            page += 1
        
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
        
        # Handle album
        album = track_data.get('album', {})
        if isinstance(album, dict):
            album_name = album.get('#text', '')
        else:
            album_name = str(album) if album else ''
        
        # Get timestamp
        date_info = track_data.get('date', {})
        if isinstance(date_info, dict):
            timestamp = int(date_info.get('uts', 0))
        else:
            timestamp = int(date_info) if date_info else 0
        
        played_at = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
        
        return {
            'artist': artist_name,
            'album': album_name,
            'track': track_data.get('name', 'Unknown Track'),
            'played_at': played_at,
            'mbid': track_data.get('mbid', ''),
            'url': track_data.get('url', '')
        }
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get user information from Last.fm"""
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
    
    def test_connection(self) -> bool:
        """Test connection to Last.fm API"""
        try:
            user_info = self.get_user_info()
            if user_info:
                logger.info(f"Connected to Last.fm as: {user_info.get('name', 'Unknown')}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Last.fm: {e}")
            return False