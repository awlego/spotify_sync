"""
Shared configuration for both sync and wrapped services
"""
import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass
class DatabaseConfig:
    """Shared database configuration"""
    path: str = "data/db/spotify_sync.db"
    backup_path: str = "backups/"


@dataclass
class SharedConfig:
    """Configuration shared between services"""
    def __init__(self, config_path: Optional[str] = None):
        # Load environment variables
        load_dotenv()
        
        # Default config path (looks for config.yaml in project root)
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        self.config_path = Path(config_path)
        self._raw_config = self._load_config()
        
        # Initialize shared components
        self.database = self._load_database_config()
    
    def _load_config(self) -> dict:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            return {}
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Replace environment variables
        return self._replace_env_vars(config)
    
    def _replace_env_vars(self, config: any) -> any:
        """Recursively replace ${ENV_VAR} patterns with environment variables"""
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            env_var = config[2:-1]
            return os.getenv(env_var, config)
        return config
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration"""
        db = self._raw_config.get('database', {})
        # Convert to absolute path
        db_path = db.get('path', 'data/db/spotify_sync.db')
        if not os.path.isabs(db_path):
            # Make path relative to project root (parent of shared directory)
            project_root = Path(__file__).parent.parent
            db_path = str(project_root / db_path)
        
        backup_path = db.get('backup_path', 'backups/')
        if not os.path.isabs(backup_path):
            project_root = Path(__file__).parent.parent
            backup_path = str(project_root / backup_path)
            
        return DatabaseConfig(
            path=db_path,
            backup_path=backup_path
        )


# Global config instance
_config = None

def get_shared_config() -> SharedConfig:
    """Get global shared configuration instance"""
    global _config
    if _config is None:
        _config = SharedConfig()
    return _config