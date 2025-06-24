"""
Genre mapping and spatial positioning for the Genre Galaxy Explorer
"""
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler
from collections import defaultdict
import json
from loguru import logger
import sys
from pathlib import Path

# Import shared components
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared import DatabaseManager, Track, Artist, PlayHistory


class GenreMapper:
    """Maps genres and artists to 3D space for galaxy visualization"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.genre_hierarchy = self._build_genre_hierarchy()
        
    def _build_genre_hierarchy(self) -> Dict[str, List[str]]:
        """Build a hierarchy of genre relationships"""
        # This is a simplified hierarchy - in production, this would be
        # built from Spotify's genre data or a music ontology
        return {
            "rock": ["indie rock", "alternative rock", "classic rock", "hard rock", "punk rock"],
            "pop": ["indie pop", "synth-pop", "dance pop", "pop rock", "electropop"],
            "electronic": ["house", "techno", "ambient", "edm", "dubstep"],
            "hip hop": ["trap", "rap", "underground hip hop", "old school hip hop"],
            "jazz": ["smooth jazz", "jazz fusion", "bebop", "swing"],
            "classical": ["baroque", "romantic", "modern classical", "opera"],
            "folk": ["indie folk", "folk rock", "traditional folk", "americana"],
            "metal": ["heavy metal", "death metal", "black metal", "power metal"],
            "country": ["country rock", "outlaw country", "country pop", "bluegrass"],
            "r&b": ["soul", "funk", "neo soul", "contemporary r&b"],
            "latin": ["reggaeton", "salsa", "bossa nova", "latin pop"],
            "world": ["afrobeat", "k-pop", "j-pop", "celtic"]
        }
    
    def get_genre_positions(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate 3D positions for genres based on their relationships
        Returns positions, sizes, and colors for visualization
        """
        with self.db.session_scope() as session:
            # Get all genres with play counts
            genre_plays = self._get_genre_play_counts(session, user_id)
            
            if not genre_plays:
                return {"genres": [], "connections": []}
            
            # Create feature vectors for genres (simplified for now)
            genres = list(genre_plays.keys())
            features = self._create_genre_features(genres)
            
            # Use t-SNE to position genres in 3D space
            if len(genres) > 3:
                tsne = TSNE(n_components=3, perplexity=min(30, len(genres)-1), 
                           random_state=42)
                positions_3d = tsne.fit_transform(features)
            else:
                # For small datasets, use simple positioning
                positions_3d = features[:, :3] if features.shape[1] >= 3 else \
                              np.pad(features, ((0, 0), (0, 3 - features.shape[1])))
            
            # Scale positions to reasonable range
            scaler = StandardScaler()
            positions_3d = scaler.fit_transform(positions_3d) * 100
            
            # Build genre data
            genre_data = []
            max_plays = max(genre_plays.values()) if genre_plays else 1
            
            for i, genre in enumerate(genres):
                genre_data.append({
                    "id": genre,
                    "name": genre.title(),
                    "position": {
                        "x": float(positions_3d[i, 0]),
                        "y": float(positions_3d[i, 1]),
                        "z": float(positions_3d[i, 2])
                    },
                    "size": max(5, (genre_plays[genre] / max_plays) * 50),
                    "play_count": genre_plays[genre],
                    "color": self._get_genre_color(genre),
                    "parent": self._find_parent_genre(genre)
                })
            
            # Build connections between related genres
            connections = self._build_genre_connections(genres)
            
            return {
                "genres": genre_data,
                "connections": connections
            }
    
    def _get_genre_play_counts(self, session, user_id: Optional[int]) -> Dict[str, int]:
        """Get play counts for each genre"""
        # For now, we'll aggregate by artist since we don't have genre data yet
        # In production, this would use actual genre data from Spotify
        query = session.query(
            Artist.name,
            func.count(PlayHistory.id).label('play_count')
        ).select_from(PlayHistory).join(Track).join(Artist)
        
        if user_id:
            query = query.filter(PlayHistory.user_id == user_id)
        
        results = query.group_by(Artist.id).all()
        
        # Simulate genre assignment (in production, use Spotify API)
        genre_plays = defaultdict(int)
        genre_assignments = {
            "Taylor Swift": "pop",
            "The Beatles": "rock",
            "Daft Punk": "electronic",
            "Miles Davis": "jazz",
            "Johnny Cash": "country",
            "Bob Dylan": "folk"
        }
        
        for artist_name, play_count in results:
            # Assign genre based on artist (simplified)
            genre = genre_assignments.get(artist_name, "other")
            genre_plays[genre] += play_count
        
        return dict(genre_plays)
    
    def _create_genre_features(self, genres: List[str]) -> np.ndarray:
        """Create feature vectors for genres"""
        # In production, this would use audio features from Spotify
        # For now, create random features with some structure
        np.random.seed(42)
        n_features = 10
        features = np.random.randn(len(genres), n_features)
        
        # Add some structure based on genre hierarchy
        for i, genre in enumerate(genres):
            parent = self._find_parent_genre(genre)
            if parent:
                # Similar genres should be closer
                parent_idx = genres.index(parent) if parent in genres else -1
                if parent_idx >= 0:
                    features[i] = features[parent_idx] + np.random.randn(n_features) * 0.3
        
        return features
    
    def _get_genre_color(self, genre: str) -> str:
        """Get color for genre visualization"""
        color_map = {
            "rock": "#FF6B6B",
            "pop": "#4ECDC4",
            "electronic": "#45B7D1",
            "hip hop": "#96CEB4",
            "jazz": "#DDA0DD",
            "classical": "#FFD93D",
            "folk": "#95E1D3",
            "metal": "#2C2C2C",
            "country": "#F4A460",
            "r&b": "#DA70D6",
            "latin": "#FF7F50",
            "world": "#20B2AA",
            "other": "#A8A8A8"
        }
        
        # Check parent genres
        for parent, children in self.genre_hierarchy.items():
            if genre in children:
                return color_map.get(parent, color_map["other"])
        
        return color_map.get(genre, color_map["other"])
    
    def _find_parent_genre(self, genre: str) -> Optional[str]:
        """Find parent genre in hierarchy"""
        for parent, children in self.genre_hierarchy.items():
            if genre in children:
                return parent
        return None
    
    def _build_genre_connections(self, genres: List[str]) -> List[Dict[str, Any]]:
        """Build connections between related genres"""
        connections = []
        
        # Connect parent-child genres
        for parent, children in self.genre_hierarchy.items():
            if parent in genres:
                for child in children:
                    if child in genres:
                        connections.append({
                            "source": parent,
                            "target": child,
                            "strength": 0.8,
                            "type": "hierarchy"
                        })
        
        # Add some cross-genre connections (simplified)
        cross_connections = [
            ("pop", "rock", 0.5),
            ("rock", "folk", 0.4),
            ("electronic", "pop", 0.6),
            ("jazz", "r&b", 0.5)
        ]
        
        for source, target, strength in cross_connections:
            if source in genres and target in genres:
                connections.append({
                    "source": source,
                    "target": target,
                    "strength": strength,
                    "type": "similarity"
                })
        
        return connections
    
    def get_user_journey(self, user_id: Optional[int] = None, 
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get user's journey through genres over time"""
        with self.db.session_scope() as session:
            query = session.query(
                PlayHistory.played_at,
                Artist.name,
                Track.name.label('track_name')
            ).select_from(PlayHistory).join(Track).join(Artist)
            
            if user_id:
                query = query.filter(PlayHistory.user_id == user_id)
            
            if start_date:
                query = query.filter(PlayHistory.played_at >= start_date)
            
            if end_date:
                query = query.filter(PlayHistory.played_at <= end_date)
            
            plays = query.order_by(PlayHistory.played_at).all()
            
            # Build journey data
            journey = []
            prev_genre = None
            
            for play in plays:
                # Simulate genre (in production, use real data)
                genre = self._get_artist_genre(play[1])
                
                if genre != prev_genre and prev_genre is not None:
                    journey.append({
                        "timestamp": play[0].isoformat(),
                        "from_genre": prev_genre,
                        "to_genre": genre,
                        "artist": play[1],
                        "track": play[2]
                    })
                
                prev_genre = genre
            
            return journey
    
    def _get_artist_genre(self, artist_name: str) -> str:
        """Get genre for artist (simplified for demo)"""
        # In production, this would use Spotify API data
        genre_map = {
            "Taylor Swift": "pop",
            "The Beatles": "rock",
            "Daft Punk": "electronic",
            "Miles Davis": "jazz",
            "Johnny Cash": "country",
            "Bob Dylan": "folk"
        }
        return genre_map.get(artist_name, "other")


# Add missing import
from sqlalchemy import func