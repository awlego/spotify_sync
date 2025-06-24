"""
Analyze correlations between weather conditions and music listening patterns
"""
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from datetime import datetime, timedelta
from collections import defaultdict
from loguru import logger
import sys
from pathlib import Path

# Import shared components
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared import DatabaseManager, Track, Artist, PlayHistory
from services.weather_service import WeatherService
from analytics.mood_analyzer import MoodAnalyzer
from sqlalchemy import func


class WeatherMusicCorrelation:
    """Analyzes relationships between weather and music choices"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.weather_service = WeatherService()
        self.mood_analyzer = MoodAnalyzer()
        
    def analyze_weather_correlations(self, user_id: Optional[int] = None,
                                   days: int = 90,
                                   location: Optional[Tuple[float, float]] = None) -> Dict[str, Any]:
        """
        Analyze correlations between weather and music patterns
        """
        # Get location
        if not location:
            location = self.weather_service.get_location_from_ip()
        
        lat, lon = location
        
        with self.db.session_scope() as session:
            # Get play history
            query = session.query(PlayHistory).join(Track).join(Artist)
            
            if user_id:
                query = query.filter(PlayHistory.user_id == user_id)
            
            start_date = datetime.now() - timedelta(days=days)
            plays = query.filter(PlayHistory.played_at >= start_date).all()
            
            if not plays:
                return self._empty_correlation_data()
            
            # Group plays by day and hour
            play_data = self._organize_play_data(plays)
            
            # Get weather data for the period
            weather_data = self._get_weather_for_plays(play_data, lat, lon)
            
            # Calculate correlations
            correlations = self._calculate_correlations(play_data, weather_data)
            
            # Analyze patterns
            patterns = self._analyze_weather_patterns(play_data, weather_data)
            
            # Generate predictions for current weather
            current_weather = self.weather_service.get_historical_weather(
                lat, lon, datetime.now()
            )
            predictions = self._generate_predictions(patterns, current_weather)
            
            # Build location data for map
            location_data = {
                'latitude': lat,
                'longitude': lon,
                'play_density': self._calculate_location_density(play_data)
            }
            
            return {
                'correlations': correlations,
                'patterns': patterns,
                'predictions': predictions,
                'location': location_data,
                'weather_summary': self._summarize_weather_preferences(patterns),
                'period_days': days,
                'total_plays': len(plays)
            }
    
    def _organize_play_data(self, plays: List[PlayHistory]) -> Dict[str, Any]:
        """Organize plays by date and extract features"""
        play_data = defaultdict(lambda: {
            'plays': [],
            'audio_features': defaultdict(list),
            'genres': defaultdict(int),
            'moods': defaultdict(int)
        })
        
        for play in plays:
            date_key = play.played_at.date().isoformat()
            
            # Get audio features (synthetic for demo)
            audio_features = self.mood_analyzer._get_audio_features(play.track)
            mood = self.mood_analyzer.analyze_track_mood(audio_features)
            
            play_info = {
                'track': play.track.name,
                'artist': play.track.artist.name,
                'played_at': play.played_at,
                'mood': mood['mood'],
                'valence': audio_features['valence'],
                'energy': audio_features['energy'],
                'tempo': audio_features['tempo']
            }
            
            play_data[date_key]['plays'].append(play_info)
            
            # Aggregate features
            for feature, value in audio_features.items():
                play_data[date_key]['audio_features'][feature].append(value)
            
            # Count moods and genres
            play_data[date_key]['moods'][mood['mood']] += 1
            genre = self._get_track_genre(play.track)
            play_data[date_key]['genres'][genre] += 1
        
        # Calculate daily averages
        for date_key, data in play_data.items():
            for feature, values in data['audio_features'].items():
                data['audio_features'][feature] = np.mean(values) if values else 0.5
        
        return dict(play_data)
    
    def _get_weather_for_plays(self, play_data: Dict[str, Any], 
                             lat: float, lon: float) -> Dict[str, Any]:
        """Get weather data for days with plays"""
        weather_data = {}
        
        for date_str in play_data.keys():
            date = datetime.fromisoformat(date_str)
            weather = self.weather_service.get_historical_weather(lat, lon, date)
            
            if weather:
                weather['category'] = self.weather_service.categorize_weather(weather)
                weather['features'] = self.weather_service.get_weather_features(weather)
                weather_data[date_str] = weather
        
        return weather_data
    
    def _calculate_correlations(self, play_data: Dict[str, Any],
                              weather_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate correlations between weather and audio features"""
        # Prepare data for correlation analysis
        dates = sorted(set(play_data.keys()) & set(weather_data.keys()))
        
        if len(dates) < 10:
            return {'error': 'Insufficient data for correlation analysis'}
        
        # Extract features
        weather_features = ['temperature', 'humidity', 'pressure', 'cloudiness']
        audio_features = ['valence', 'energy', 'danceability', 'tempo']
        
        correlations = {}
        
        for w_feature in weather_features:
            correlations[w_feature] = {}
            
            w_values = [weather_data[d]['features'][w_feature] for d in dates]
            
            for a_feature in audio_features:
                a_values = [play_data[d]['audio_features'].get(a_feature, 0.5) for d in dates]
                
                # Calculate Pearson correlation
                if len(set(w_values)) > 1 and len(set(a_values)) > 1:
                    corr, p_value = pearsonr(w_values, a_values)
                    correlations[w_feature][a_feature] = {
                        'correlation': round(corr, 3),
                        'p_value': round(p_value, 3),
                        'significant': p_value < 0.05
                    }
                else:
                    correlations[w_feature][a_feature] = {
                        'correlation': 0,
                        'p_value': 1,
                        'significant': False
                    }
        
        return correlations
    
    def _analyze_weather_patterns(self, play_data: Dict[str, Any],
                                weather_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze music patterns for different weather conditions"""
        patterns = defaultdict(lambda: {
            'play_count': 0,
            'avg_features': defaultdict(float),
            'top_moods': defaultdict(int),
            'top_genres': defaultdict(int),
            'example_tracks': []
        })
        
        for date_str in play_data.keys():
            if date_str not in weather_data:
                continue
            
            weather_category = weather_data[date_str]['category']
            day_data = play_data[date_str]
            
            patterns[weather_category]['play_count'] += len(day_data['plays'])
            
            # Aggregate audio features
            for feature, value in day_data['audio_features'].items():
                patterns[weather_category]['avg_features'][feature] += value
            
            # Aggregate moods and genres
            for mood, count in day_data['moods'].items():
                patterns[weather_category]['top_moods'][mood] += count
            
            for genre, count in day_data['genres'].items():
                patterns[weather_category]['top_genres'][genre] += count
            
            # Collect example tracks
            for play in day_data['plays'][:3]:  # Top 3 per day
                patterns[weather_category]['example_tracks'].append({
                    'track': play['track'],
                    'artist': play['artist'],
                    'mood': play['mood']
                })
        
        # Calculate averages and sort
        for weather, data in patterns.items():
            days_count = sum(1 for d in weather_data.values() if d['category'] == weather)
            
            if days_count > 0:
                for feature in data['avg_features']:
                    data['avg_features'][feature] /= days_count
            
            # Sort moods and genres by frequency
            data['top_moods'] = sorted(
                data['top_moods'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            data['top_genres'] = sorted(
                data['top_genres'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            # Limit example tracks
            data['example_tracks'] = data['example_tracks'][:10]
        
        return dict(patterns)
    
    def _generate_predictions(self, patterns: Dict[str, Any],
                            current_weather: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate music predictions based on current weather"""
        if not current_weather:
            return {'error': 'Unable to fetch current weather'}
        
        weather_category = self.weather_service.categorize_weather(current_weather)
        
        if weather_category not in patterns:
            return {
                'weather': weather_category,
                'temperature': current_weather['temperature']['current'],
                'suggestions': ['No data available for this weather type']
            }
        
        pattern = patterns[weather_category]
        
        # Generate suggestions based on patterns
        suggestions = []
        
        # Mood-based suggestions
        if pattern['top_moods']:
            top_mood = pattern['top_moods'][0][0]
            suggestions.append(f"Try some {top_mood} music - it's popular in {weather_category} weather")
        
        # Feature-based suggestions
        avg_features = pattern['avg_features']
        if avg_features.get('energy', 0) > 0.7:
            suggestions.append("High-energy tracks work well in this weather")
        elif avg_features.get('energy', 0) < 0.3:
            suggestions.append("Calm, relaxing music suits this weather")
        
        if avg_features.get('valence', 0) > 0.7:
            suggestions.append("Happy, upbeat songs match today's conditions")
        elif avg_features.get('valence', 0) < 0.3:
            suggestions.append("Melancholic tunes fit the current atmosphere")
        
        # Example tracks
        if pattern['example_tracks']:
            examples = pattern['example_tracks'][:3]
            suggestions.append("Recently played in similar weather:")
            for ex in examples:
                suggestions.append(f"  • {ex['track']} by {ex['artist']}")
        
        return {
            'weather': weather_category,
            'temperature': current_weather['temperature']['current'],
            'description': current_weather['weather']['description'],
            'suggestions': suggestions,
            'confidence': min(pattern['play_count'] / 100, 1.0)  # Based on data amount
        }
    
    def _calculate_location_density(self, play_data: Dict[str, Any]) -> List[Dict[str, float]]:
        """Calculate play density by location (simplified)"""
        # In a real implementation, this would use actual location data
        # For demo, create synthetic location clusters
        densities = []
        
        for date_str, data in play_data.items():
            play_count = len(data['plays'])
            
            # Add some variation to location
            date = datetime.fromisoformat(date_str)
            lat_offset = np.sin(date.toordinal()) * 0.1
            lon_offset = np.cos(date.toordinal()) * 0.1
            
            densities.append({
                'lat_offset': lat_offset,
                'lon_offset': lon_offset,
                'intensity': min(play_count / 50, 1.0)
            })
        
        return densities
    
    def _summarize_weather_preferences(self, patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize weather-based music preferences"""
        summary = {}
        
        for weather, data in patterns.items():
            if data['play_count'] > 0:
                # Find dominant characteristics
                top_mood = data['top_moods'][0][0] if data['top_moods'] else 'varied'
                avg_energy = data['avg_features'].get('energy', 0.5)
                avg_valence = data['avg_features'].get('valence', 0.5)
                
                # Create description
                energy_desc = 'high-energy' if avg_energy > 0.6 else 'calm' if avg_energy < 0.4 else 'moderate'
                mood_desc = 'upbeat' if avg_valence > 0.6 else 'melancholic' if avg_valence < 0.4 else 'balanced'
                
                summary[weather] = {
                    'description': f"{energy_desc}, {mood_desc} music",
                    'dominant_mood': top_mood,
                    'play_percentage': data['play_count'],
                    'characteristics': {
                        'energy': round(avg_energy, 2),
                        'valence': round(avg_valence, 2)
                    }
                }
        
        return summary
    
    def _get_track_genre(self, track: Track) -> str:
        """Get genre for track (simplified)"""
        # In production, this would use Spotify API data
        artist_genres = {
            "Taylor Swift": "pop",
            "Bon Iver": "folk",
            "Daft Punk": "electronic",
            "The Beatles": "rock",
            "Miles Davis": "jazz"
        }
        return artist_genres.get(track.artist.name, "other")
    
    def _empty_correlation_data(self) -> Dict[str, Any]:
        """Return empty correlation data structure"""
        return {
            'correlations': {},
            'patterns': {},
            'predictions': {'error': 'No listening data available'},
            'location': {'latitude': 0, 'longitude': 0, 'play_density': []},
            'weather_summary': {},
            'period_days': 0,
            'total_plays': 0
        }