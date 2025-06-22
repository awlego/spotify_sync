"""
Configuration for Sync Service
"""
import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# Import shared config
import sys
sys.path.append(str(Path(__file__).parent.parent))
from shared.config import SharedConfig, get_shared_config


@dataclass
class SpotifyConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    username: str
    scope: str = 'playlist-modify-private user-library-read'


@dataclass
class LastFmConfig:
    api_key: str
    api_secret: str
    username: str


@dataclass
class PlaylistConfig:
    id: str
    size: int
    timeframe_days: Optional[int] = None
    min_daily_plays: Optional[int] = None
    
    def validate(self) -> None:
        """Validate playlist configuration"""
        if not self.id or self.id.strip() == '':
            raise ValueError(f"Playlist ID cannot be empty")
        
        if self.size <= 0:
            raise ValueError(f"Playlist size must be positive, got {self.size}")


@dataclass
class SyncConfig:
    interval_minutes: int = 5
    history_days: int = 30
    batch_size: int = 50


class SyncServiceConfig(SharedConfig):
    """Configuration specific to sync service"""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__(config_path)
        
        # Initialize sync-specific components
        self.spotify = self._load_spotify_config()
        self.lastfm = self._load_lastfm_config()
        self.playlists = self._load_playlist_configs()
        self.sync = self._load_sync_config()
        self.web_port = 5001  # Sync service port
    
    def _load_spotify_config(self) -> SpotifyConfig:
        spotify = self._raw_config.get('spotify', {})
        return SpotifyConfig(
            client_id=spotify.get('client_id', os.getenv('SPOTIPY_CLIENT_ID', '')),
            client_secret=spotify.get('client_secret', os.getenv('SPOTIPY_CLIENT_SECRET', '')),
            redirect_uri=spotify.get('redirect_uri', os.getenv('SPOTIPY_REDIRECT_URI', 'http://localhost:5001/callback')),
            username=spotify.get('username', os.getenv('SPOTIFY_USERNAME', ''))
        )
    
    def _load_lastfm_config(self) -> LastFmConfig:
        lastfm = self._raw_config.get('lastfm', {})
        return LastFmConfig(
            api_key=lastfm.get('api_key', os.getenv('LASTFM_API_KEY', '')),
            api_secret=lastfm.get('api_secret', os.getenv('LASTFM_API_SECRET', '')),
            username=lastfm.get('username', os.getenv('LASTFM_USERNAME', ''))
        )
    
    def _load_playlist_configs(self) -> dict:
        playlists_config = self._raw_config.get('playlists', {})
        playlists = {}
        
        for name, config in playlists_config.items():
            playlist_config = PlaylistConfig(
                id=config.get('id', os.getenv(f'{name.upper()}_ID', '')),
                size=config.get('size', 50),
                timeframe_days=config.get('timeframe_days'),
                min_daily_plays=config.get('min_daily_plays')
            )
            
            try:
                playlist_config.validate()
                playlists[name] = playlist_config
            except ValueError as e:
                print(f"Invalid configuration for {name} playlist: {e}. Skipping.")
            
        return playlists
    
    def _load_sync_config(self) -> SyncConfig:
        sync = self._raw_config.get('sync', {})
        return SyncConfig(
            interval_minutes=sync.get('interval_minutes', 5),
            history_days=sync.get('history_days', 30),
            batch_size=sync.get('batch_size', 50)
        )


# Global config instance
_config = None

def get_config() -> SyncServiceConfig:
    """Get global sync service configuration instance"""
    global _config
    if _config is None:
        _config = SyncServiceConfig()
    return _config