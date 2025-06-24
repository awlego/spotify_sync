"""
Mood analysis based on Spotify audio features
"""
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from loguru import logger
import sys
from pathlib import Path

# Import shared components
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared import DatabaseManager, Track, PlayHistory
from sqlalchemy import func


class MoodAnalyzer:
    """Analyzes mood patterns from audio features"""
    
    def __init__(self):
        self.db = DatabaseManager()
        
        # Define mood quadrants based on valence and energy
        self.mood_map = {
            'happy': {'valence': (0.6, 1.0), 'energy': (0.6, 1.0), 'color': '#FFD700'},
            'energetic': {'valence': (0.0, 0.6), 'energy': (0.6, 1.0), 'color': '#FF4500'},
            'calm': {'valence': (0.6, 1.0), 'energy': (0.0, 0.6), 'color': '#87CEEB'},
            'sad': {'valence': (0.0, 0.6), 'energy': (0.0, 0.6), 'color': '#4682B4'},
            'angry': {'valence': (0.0, 0.4), 'energy': (0.7, 1.0), 'color': '#DC143C'},
            'romantic': {'valence': (0.5, 0.8), 'energy': (0.2, 0.5), 'color': '#FF69B4'},
            'melancholic': {'valence': (0.2, 0.5), 'energy': (0.2, 0.5), 'color': '#9370DB'},
            'uplifting': {'valence': (0.7, 1.0), 'energy': (0.5, 0.8), 'color': '#32CD32'}
        }
    
    def analyze_track_mood(self, audio_features: Dict[str, float]) -> Dict[str, Any]:
        """
        Analyze mood of a track based on audio features
        Returns mood classification and confidence scores
        """
        if not audio_features:
            return {'mood': 'unknown', 'confidence': 0.0, 'color': '#808080'}
        
        valence = audio_features.get('valence', 0.5)
        energy = audio_features.get('energy', 0.5)
        
        # Find best matching mood
        best_mood = None
        best_score = 0.0
        
        for mood, criteria in self.mood_map.items():
            val_range = criteria['valence']
            energy_range = criteria['energy']
            
            # Check if track falls within mood ranges
            if (val_range[0] <= valence <= val_range[1] and 
                energy_range[0] <= energy <= energy_range[1]):
                
                # Calculate distance from center of mood quadrant
                val_center = (val_range[0] + val_range[1]) / 2
                energy_center = (energy_range[0] + energy_range[1]) / 2
                
                distance = np.sqrt((valence - val_center)**2 + (energy - energy_center)**2)
                score = 1.0 - (distance / np.sqrt(2))  # Normalize to 0-1
                
                if score > best_score:
                    best_score = score
                    best_mood = mood
        
        # If no mood matched, classify based on dominant dimension
        if not best_mood:
            if valence > 0.5 and energy > 0.5:
                best_mood = 'happy'
            elif valence > 0.5 and energy <= 0.5:
                best_mood = 'calm'
            elif valence <= 0.5 and energy > 0.5:
                best_mood = 'energetic'
            else:
                best_mood = 'sad'
            best_score = 0.5
        
        return {
            'mood': best_mood,
            'confidence': best_score,
            'color': self.mood_map[best_mood]['color'],
            'valence': valence,
            'energy': energy
        }
    
    def get_mood_timeline(self, user_id: Optional[int] = None,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get mood progression over time
        Returns timeline of mood changes with timestamps
        """
        with self.db.session_scope() as session:
            # For demo purposes, generate synthetic audio features
            # In production, these would come from Spotify API
            query = session.query(PlayHistory).join(Track)
            
            if user_id:
                query = query.filter(PlayHistory.user_id == user_id)
            
            if start_date:
                query = query.filter(PlayHistory.played_at >= start_date)
            else:
                # Default to last 30 days
                start_date = datetime.now() - timedelta(days=30)
                query = query.filter(PlayHistory.played_at >= start_date)
            
            if end_date:
                query = query.filter(PlayHistory.played_at <= end_date)
            
            plays = query.order_by(PlayHistory.played_at).all()
            
            timeline = []
            for play in plays:
                # Generate synthetic audio features (in production, fetch from Spotify)
                audio_features = self._get_audio_features(play.track)
                mood_data = self.analyze_track_mood(audio_features)
                
                timeline.append({
                    'timestamp': play.played_at.isoformat(),
                    'track_name': play.track.name,
                    'artist_name': play.track.artist.name,
                    'mood': mood_data['mood'],
                    'confidence': mood_data['confidence'],
                    'color': mood_data['color'],
                    'valence': mood_data['valence'],
                    'energy': mood_data['energy']
                })
            
            return timeline
    
    def get_mood_patterns(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyze mood patterns by time of day and day of week
        """
        with self.db.session_scope() as session:
            query = session.query(PlayHistory).join(Track)
            
            if user_id:
                query = query.filter(PlayHistory.user_id == user_id)
            
            # Get last 90 days for pattern analysis
            start_date = datetime.now() - timedelta(days=90)
            plays = query.filter(PlayHistory.played_at >= start_date).all()
            
            # Analyze patterns
            hourly_moods = defaultdict(lambda: defaultdict(int))
            daily_moods = defaultdict(lambda: defaultdict(int))
            mood_transitions = defaultdict(lambda: defaultdict(int))
            
            prev_mood = None
            
            for play in plays:
                audio_features = self._get_audio_features(play.track)
                mood_data = self.analyze_track_mood(audio_features)
                mood = mood_data['mood']
                
                # Hourly pattern
                hour = play.played_at.hour
                hourly_moods[hour][mood] += 1
                
                # Daily pattern
                weekday = play.played_at.weekday()
                daily_moods[weekday][mood] += 1
                
                # Mood transitions
                if prev_mood:
                    mood_transitions[prev_mood][mood] += 1
                prev_mood = mood
            
            # Convert to percentages
            hourly_pattern = {}
            for hour, moods in hourly_moods.items():
                total = sum(moods.values())
                hourly_pattern[hour] = {
                    mood: (count / total) * 100
                    for mood, count in moods.items()
                }
            
            daily_pattern = {}
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for day_idx, moods in daily_moods.items():
                total = sum(moods.values())
                daily_pattern[days[day_idx]] = {
                    mood: (count / total) * 100
                    for mood, count in moods.items()
                }
            
            # Most common transitions
            transitions = []
            for from_mood, to_moods in mood_transitions.items():
                for to_mood, count in to_moods.items():
                    transitions.append({
                        'from': from_mood,
                        'to': to_mood,
                        'count': count
                    })
            transitions.sort(key=lambda x: x['count'], reverse=True)
            
            return {
                'hourly_pattern': hourly_pattern,
                'daily_pattern': daily_pattern,
                'common_transitions': transitions[:10],
                'mood_colors': {mood: data['color'] for mood, data in self.mood_map.items()}
            }
    
    def get_mood_summary(self, user_id: Optional[int] = None,
                        days: int = 30) -> Dict[str, Any]:
        """
        Get summary statistics of mood distribution
        """
        with self.db.session_scope() as session:
            query = session.query(PlayHistory).join(Track)
            
            if user_id:
                query = query.filter(PlayHistory.user_id == user_id)
            
            start_date = datetime.now() - timedelta(days=days)
            plays = query.filter(PlayHistory.played_at >= start_date).all()
            
            mood_counts = defaultdict(int)
            mood_durations = defaultdict(float)
            total_plays = 0
            
            for i, play in enumerate(plays):
                audio_features = self._get_audio_features(play.track)
                mood_data = self.analyze_track_mood(audio_features)
                mood = mood_data['mood']
                
                mood_counts[mood] += 1
                total_plays += 1
                
                # Estimate duration (3 minutes average if not available)
                duration = 180  # 3 minutes in seconds
                mood_durations[mood] += duration
            
            # Calculate percentages and insights
            mood_distribution = {}
            dominant_mood = None
            max_percentage = 0
            
            for mood, count in mood_counts.items():
                percentage = (count / total_plays) * 100 if total_plays > 0 else 0
                mood_distribution[mood] = {
                    'percentage': round(percentage, 1),
                    'count': count,
                    'duration_minutes': round(mood_durations[mood] / 60, 1),
                    'color': self.mood_map[mood]['color']
                }
                
                if percentage > max_percentage:
                    max_percentage = percentage
                    dominant_mood = mood
            
            # Generate insights
            insights = self._generate_mood_insights(mood_distribution, dominant_mood)
            
            return {
                'distribution': mood_distribution,
                'dominant_mood': dominant_mood,
                'total_tracks': total_plays,
                'insights': insights,
                'period_days': days
            }
    
    def _get_audio_features(self, track: Track) -> Dict[str, float]:
        """
        Get audio features for a track
        In production, this would fetch from Spotify API or cache
        """
        # For demo, generate synthetic features based on artist/track name
        # This is a placeholder - real implementation would use Spotify API
        
        # Use track and artist names to seed random generation for consistency
        seed = hash(f"{track.name}{track.artist.name}") % 10000
        np.random.seed(seed)
        
        # Generate features with some patterns
        base_valence = np.random.random()
        base_energy = np.random.random()
        
        # Add some artist-specific biases (demo only)
        artist_biases = {
            "Taylor Swift": {"valence": 0.1, "energy": 0.1},
            "Bon Iver": {"valence": -0.2, "energy": -0.2},
            "Daft Punk": {"valence": 0.2, "energy": 0.3},
            "Ed Sheeran": {"valence": 0.15, "energy": -0.1}
        }
        
        bias = artist_biases.get(track.artist.name, {"valence": 0, "energy": 0})
        
        return {
            'valence': np.clip(base_valence + bias['valence'], 0, 1),
            'energy': np.clip(base_energy + bias['energy'], 0, 1),
            'danceability': np.random.random(),
            'acousticness': np.random.random(),
            'instrumentalness': np.random.random() * 0.3,  # Usually low
            'speechiness': np.random.random() * 0.2,  # Usually low
            'tempo': np.random.randint(60, 180)
        }
    
    def _generate_mood_insights(self, distribution: Dict[str, Any], 
                               dominant_mood: str) -> List[str]:
        """Generate insights based on mood patterns"""
        insights = []
        
        # Dominant mood insight
        if dominant_mood:
            percentage = distribution[dominant_mood]['percentage']
            insights.append(
                f"Your music has been mostly {dominant_mood} ({percentage}%) lately"
            )
        
        # Variety insight
        mood_count = len([m for m, d in distribution.items() if d['count'] > 0])
        if mood_count >= 5:
            insights.append("You have diverse emotional range in your listening")
        elif mood_count <= 2:
            insights.append("Your mood preferences have been quite focused")
        
        # Specific mood insights
        if 'happy' in distribution and distribution['happy']['percentage'] > 40:
            insights.append("You've been in a positive mood! 🌟")
        
        if 'sad' in distribution and distribution['sad']['percentage'] > 30:
            insights.append("Music has been your emotional companion")
        
        if 'energetic' in distribution and distribution['energetic']['percentage'] > 25:
            insights.append("High energy music is keeping you motivated!")
        
        return insights