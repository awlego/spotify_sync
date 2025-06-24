"""
Musical diversity analysis using portfolio theory concepts
"""
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
from scipy.stats import entropy
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from loguru import logger
import sys
from pathlib import Path

# Import shared components
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared import DatabaseManager, Track, Artist, PlayHistory
from sqlalchemy import func


class DiversityMetrics:
    """Analyzes musical diversity using financial portfolio concepts"""
    
    def __init__(self):
        self.db = DatabaseManager()
        
        # Genre categories (simplified - would use Spotify data in production)
        self.genre_categories = {
            'rock': ['rock', 'indie rock', 'alternative', 'punk', 'metal'],
            'pop': ['pop', 'indie pop', 'dance pop', 'synth-pop'],
            'electronic': ['electronic', 'house', 'techno', 'edm', 'ambient'],
            'hip hop': ['hip hop', 'rap', 'trap', 'r&b'],
            'jazz': ['jazz', 'blues', 'soul', 'funk'],
            'classical': ['classical', 'orchestral', 'opera'],
            'folk': ['folk', 'country', 'americana', 'bluegrass'],
            'world': ['latin', 'reggae', 'afrobeat', 'k-pop']
        }
    
    def calculate_portfolio_metrics(self, user_id: Optional[int] = None,
                                  days: int = 30) -> Dict[str, Any]:
        """
        Calculate portfolio-style metrics for music listening
        """
        with self.db.session_scope() as session:
            # Get play data for the period
            query = session.query(PlayHistory).join(Track).join(Artist)
            
            if user_id:
                query = query.filter(PlayHistory.user_id == user_id)
            
            start_date = datetime.now() - timedelta(days=days)
            plays = query.filter(PlayHistory.played_at >= start_date).all()
            
            if not plays:
                return self._empty_portfolio()
            
            # Calculate current portfolio
            current_portfolio = self._calculate_genre_distribution(plays)
            
            # Calculate historical performance
            historical_data = self._calculate_historical_performance(session, user_id, days)
            
            # Calculate diversity metrics
            diversity_score = self._calculate_diversity_score(current_portfolio)
            
            # Calculate risk metrics
            risk_metrics = self._calculate_risk_metrics(historical_data)
            
            # Generate recommendations
            recommendations = self._generate_diversification_recommendations(
                current_portfolio, diversity_score
            )
            
            return {
                'portfolio': current_portfolio,
                'diversity_score': diversity_score,
                'risk_metrics': risk_metrics,
                'historical_performance': historical_data,
                'recommendations': recommendations,
                'period_days': days,
                'total_plays': len(plays)
            }
    
    def _calculate_genre_distribution(self, plays: List[PlayHistory]) -> Dict[str, Any]:
        """
        Calculate current genre distribution (portfolio allocation)
        """
        # Count plays by genre (using artist as proxy)
        genre_plays = defaultdict(int)
        total_plays = len(plays)
        
        for play in plays:
            # Assign genre based on artist (simplified)
            genre = self._get_artist_genre(play.track.artist.name)
            genre_plays[genre] += 1
        
        # Convert to portfolio format
        assets = []
        for genre, count in genre_plays.items():
            percentage = (count / total_plays) * 100
            assets.append({
                'genre': genre,
                'percentage': round(percentage, 1),
                'play_count': count,
                'color': self._get_genre_color(genre)
            })
        
        # Sort by percentage
        assets.sort(key=lambda x: x['percentage'], reverse=True)
        
        return {
            'assets': assets,
            'total_value': total_plays,
            'last_updated': datetime.now().isoformat()
        }
    
    def _calculate_historical_performance(self, session, user_id: Optional[int],
                                        days: int) -> List[Dict[str, Any]]:
        """
        Calculate genre performance over time (like stock performance)
        """
        performance = []
        
        # Calculate weekly snapshots
        for week in range(min(12, days // 7)):  # Up to 12 weeks
            week_start = datetime.now() - timedelta(days=(week + 1) * 7)
            week_end = week_start + timedelta(days=7)
            
            query = session.query(PlayHistory).join(Track).join(Artist)
            if user_id:
                query = query.filter(PlayHistory.user_id == user_id)
            
            week_plays = query.filter(
                PlayHistory.played_at >= week_start,
                PlayHistory.played_at < week_end
            ).all()
            
            if week_plays:
                week_distribution = self._calculate_genre_distribution(week_plays)
                
                # Calculate changes from previous week
                if performance:
                    prev_week = performance[-1]
                    for asset in week_distribution['assets']:
                        prev_asset = next(
                            (a for a in prev_week['assets'] if a['genre'] == asset['genre']),
                            {'percentage': 0}
                        )
                        asset['change'] = asset['percentage'] - prev_asset['percentage']
                
                performance.append({
                    'week': week_start.isoformat(),
                    'assets': week_distribution['assets']
                })
        
        return list(reversed(performance))  # Chronological order
    
    def _calculate_diversity_score(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate diversity metrics using information theory
        """
        assets = portfolio['assets']
        if not assets:
            return {'score': 0, 'metrics': {}}
        
        # Get percentages as probabilities
        percentages = [a['percentage'] / 100 for a in assets]
        
        # Shannon entropy (0 = no diversity, higher = more diverse)
        shannon_entropy = entropy(percentages) if len(percentages) > 1 else 0
        max_entropy = np.log(len(self.genre_categories))  # Maximum possible entropy
        normalized_entropy = shannon_entropy / max_entropy if max_entropy > 0 else 0
        
        # Gini coefficient (0 = perfect equality, 1 = perfect inequality)
        gini = self._calculate_gini_coefficient(percentages)
        
        # Number of genres (breadth)
        genre_count = len(assets)
        genre_breadth = min(genre_count / len(self.genre_categories), 1.0)
        
        # Concentration risk (top 3 genres)
        top_3_concentration = sum(sorted(percentages, reverse=True)[:3])
        concentration_risk = 1.0 - top_3_concentration  # Higher is better
        
        # Overall diversity score (0-100)
        diversity_score = (
            normalized_entropy * 0.4 +
            (1 - gini) * 0.3 +
            genre_breadth * 0.2 +
            concentration_risk * 0.1
        ) * 100
        
        return {
            'score': round(diversity_score, 1),
            'metrics': {
                'entropy': round(normalized_entropy, 3),
                'gini_coefficient': round(gini, 3),
                'genre_count': genre_count,
                'genre_breadth': round(genre_breadth * 100, 1),
                'top_3_concentration': round(top_3_concentration * 100, 1)
            },
            'risk_level': self._determine_risk_level(diversity_score)
        }
    
    def _calculate_gini_coefficient(self, values: List[float]) -> float:
        """
        Calculate Gini coefficient for inequality measurement
        """
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        index = range(1, n + 1)
        
        return (2 * sum(index[i] * sorted_values[i] for i in range(n))) / (n * sum(sorted_values)) - (n + 1) / n
    
    def _calculate_risk_metrics(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate portfolio risk metrics
        """
        if len(historical_data) < 2:
            return {
                'volatility': 0,
                'trend': 'stable',
                'consistency': 100
            }
        
        # Calculate volatility for each genre
        genre_volatilities = {}
        genres = set()
        
        for week in historical_data:
            for asset in week['assets']:
                genres.add(asset['genre'])
        
        for genre in genres:
            weekly_percentages = []
            for week in historical_data:
                week_genre = next((a for a in week['assets'] if a['genre'] == genre), None)
                percentage = week_genre['percentage'] if week_genre else 0
                weekly_percentages.append(percentage)
            
            if len(weekly_percentages) > 1:
                genre_volatilities[genre] = np.std(weekly_percentages)
        
        # Portfolio volatility (weighted average)
        total_volatility = 0
        current_week = historical_data[-1] if historical_data else {'assets': []}
        
        for asset in current_week['assets']:
            genre = asset['genre']
            weight = asset['percentage'] / 100
            volatility = genre_volatilities.get(genre, 0)
            total_volatility += weight * volatility
        
        # Determine trend
        if len(historical_data) >= 3:
            recent_scores = []
            for week in historical_data[-3:]:
                dist = {'assets': week['assets']}
                score = self._calculate_diversity_score(dist)['score']
                recent_scores.append(score)
            
            if recent_scores[-1] > recent_scores[0] * 1.1:
                trend = 'improving'
            elif recent_scores[-1] < recent_scores[0] * 0.9:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        # Consistency score (inverse of volatility)
        max_volatility = 50  # Normalize to 0-100
        consistency = max(0, 100 - (total_volatility / max_volatility * 100))
        
        return {
            'volatility': round(total_volatility, 2),
            'trend': trend,
            'consistency': round(consistency, 1),
            'genre_volatilities': {k: round(v, 2) for k, v in genre_volatilities.items()}
        }
    
    def _determine_risk_level(self, diversity_score: float) -> str:
        """
        Determine risk level based on diversity score
        """
        if diversity_score >= 70:
            return 'low'  # Well diversified
        elif diversity_score >= 40:
            return 'moderate'  # Some concentration
        else:
            return 'high'  # Echo chamber risk
    
    def _generate_diversification_recommendations(self, portfolio: Dict[str, Any],
                                                diversity_score: Dict[str, Any]) -> List[str]:
        """
        Generate recommendations for portfolio diversification
        """
        recommendations = []
        
        # Check concentration
        if diversity_score['metrics']['top_3_concentration'] > 70:
            recommendations.append(
                "Your top 3 genres dominate your listening. Try exploring new genres."
            )
        
        # Check genre count
        if diversity_score['metrics']['genre_count'] < 4:
            missing_genres = set(self.genre_categories.keys())
            for asset in portfolio['assets']:
                missing_genres.discard(asset['genre'])
            
            if missing_genres:
                suggestions = list(missing_genres)[:3]
                recommendations.append(
                    f"Consider exploring: {', '.join(suggestions)}"
                )
        
        # Check for echo chamber
        if diversity_score['risk_level'] == 'high':
            recommendations.append(
                "High echo chamber risk detected. Your music taste is very concentrated."
            )
        
        # Check for positive trends
        if diversity_score['score'] > 70:
            recommendations.append(
                "Great diversity! You have a well-balanced musical portfolio."
            )
        
        return recommendations
    
    def _get_artist_genre(self, artist_name: str) -> str:
        """
        Get genre for artist (simplified mapping for demo)
        """
        # In production, this would use Spotify API data
        artist_genres = {
            "Taylor Swift": "pop",
            "The Beatles": "rock",
            "Daft Punk": "electronic",
            "Kendrick Lamar": "hip hop",
            "Miles Davis": "jazz",
            "Bob Dylan": "folk",
            "Bad Bunny": "world",
            "Bon Iver": "folk",
            "Ed Sheeran": "pop",
            "Portugal. The Man": "rock"
        }
        
        return artist_genres.get(artist_name, "other")
    
    def _get_genre_color(self, genre: str) -> str:
        """
        Get color for genre visualization
        """
        colors = {
            'rock': '#FF6B6B',
            'pop': '#4ECDC4',
            'electronic': '#45B7D1',
            'hip hop': '#96CEB4',
            'jazz': '#DDA0DD',
            'classical': '#FFD93D',
            'folk': '#95E1D3',
            'world': '#FF7F50',
            'other': '#A8A8A8'
        }
        return colors.get(genre, colors['other'])
    
    def _empty_portfolio(self) -> Dict[str, Any]:
        """
        Return empty portfolio structure
        """
        return {
            'portfolio': {
                'assets': [],
                'total_value': 0,
                'last_updated': datetime.now().isoformat()
            },
            'diversity_score': {
                'score': 0,
                'metrics': {},
                'risk_level': 'unknown'
            },
            'risk_metrics': {
                'volatility': 0,
                'trend': 'no_data',
                'consistency': 0
            },
            'historical_performance': [],
            'recommendations': ["No listening data available for analysis"],
            'period_days': 0,
            'total_plays': 0
        }