"""
Configuration for Wrapped Service
"""
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# Import shared config
import sys
sys.path.append(str(Path(__file__).parent.parent))
from shared.config import SharedConfig, get_shared_config


@dataclass
class WrappedServiceConfig(SharedConfig):
    """Configuration specific to wrapped service"""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__(config_path)
        
        # Wrapped service specific settings
        self.web_port = 5002  # Wrapped service port
        self.enable_caching = True
        self.cache_ttl = 3600  # 1 hour cache for visualizations


# Global config instance
_config = None

def get_config() -> WrappedServiceConfig:
    """Get global wrapped service configuration instance"""
    global _config
    if _config is None:
        _config = WrappedServiceConfig()
    return _config