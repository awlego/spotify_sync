import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class SpotifyConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    username: str
    scope: str = 'playlist-modify-private user-library-read user-read-recently-played'


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


@dataclass
class SyncConfig:
    interval_minutes: int = 5
    history_days: int = 30
    batch_size: int = 50


@dataclass
class DatabaseConfig:
    path: str = "spotify_sync.db"
    backup_path: str = "backups/"


class Config:
    def __init__(self, config_path: Optional[str] = None):
        # Load environment variables
        load_dotenv()
        
        # Default config path
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        
        self.config_path = Path(config_path)
        self._raw_config = self._load_config()
        
        # Initialize components
        self.spotify = self._load_spotify_config()
        self.lastfm = self._load_lastfm_config()
        self.playlists = self._load_playlist_configs()
        self.sync = self._load_sync_config()
        self.database = self._load_database_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            # Create default config if it doesn't exist
            self._create_default_config()
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Replace environment variables
        return self._replace_env_vars(config)
    
    def _replace_env_vars(self, config: Any) -> Any:
        """Recursively replace ${ENV_VAR} patterns with environment variables"""
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            env_var = config[2:-1]
            return os.getenv(env_var, config)
        return config
    
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
    
    def _load_playlist_configs(self) -> Dict[str, PlaylistConfig]:
        playlists_config = self._raw_config.get('playlists', {})
        playlists = {}
        
        # Load playlist configurations
        for name, config in playlists_config.items():
            playlists[name] = PlaylistConfig(
                id=config.get('id', os.getenv(f'{name.upper()}_ID', '')),
                size=config.get('size', 50),
                timeframe_days=config.get('timeframe_days'),
                min_daily_plays=config.get('min_daily_plays')
            )
            
        return playlists
    
    def _load_sync_config(self) -> SyncConfig:
        sync = self._raw_config.get('sync', {})
        return SyncConfig(
            interval_minutes=sync.get('interval_minutes', 5),
            history_days=sync.get('history_days', 30),
            batch_size=sync.get('batch_size', 50)
        )
    
    def _load_database_config(self) -> DatabaseConfig:
        db = self._raw_config.get('database', {})
        return DatabaseConfig(
            path=db.get('path', 'spotify_sync.db'),
            backup_path=db.get('backup_path', 'backups/')
        )
    
    def _create_default_config(self):
        """Create a default configuration file"""
        default_config = {
            'spotify': {
                'client_id': '${SPOTIPY_CLIENT_ID}',
                'client_secret': '${SPOTIPY_CLIENT_SECRET}',
                'redirect_uri': 'http://localhost:5001/callback',
                'username': '${SPOTIFY_USERNAME}'
            },
            'lastfm': {
                'api_key': '${LASTFM_API_KEY}',
                'api_secret': '${LASTFM_API_SECRET}',
                'username': '${LASTFM_USERNAME}'
            },
            'sync': {
                'interval_minutes': 5,
                'history_days': 30,
                'batch_size': 50
            },
            'playlists': {
                'most_listened': {
                    'id': '${MOST_LISTENED_TO_ID}',
                    'size': 50
                },
                'recent_favorites': {
                    'id': '${RECENT_FAVORITES_ID}',
                    'size': 25,
                    'timeframe_days': 30
                },
                'binged_songs': {
                    'id': '${BINGED_SONGS_ID}',
                    'size': 25,
                    'min_daily_plays': 3
                }
            },
            'database': {
                'path': 'spotify_sync.db',
                'backup_path': 'backups/'
            }
        }
        
        os.makedirs(self.config_path.parent, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)


# Global config instance
config = None

def get_config() -> Config:
    """Get global configuration instance"""
    global config
    if config is None:
        config = Config()
    return config