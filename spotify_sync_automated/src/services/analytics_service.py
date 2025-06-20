from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, Counter
import pandas as pd
from sqlalchemy import func
from loguru import logger

from ..core.database import DatabaseManager
from ..core.models import Track, Artist, PlayHistory


class AnalyticsService:
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_listening_calendar_data(self, year: Optional[int] = None, 
                                   artist_filter: Optional[str] = None) -> pd.DataFrame:
        """Get listening data formatted for calendar heatmap"""
        with self.db.session_scope() as session:
            query = session.query(
                PlayHistory.played_at,
                Track.name,
                Artist.name.label('artist_name')
            ).join(Track).join(Artist)
            
            if year:
                query = query.filter(
                    PlayHistory.played_at >= datetime(year, 1, 1),
                    PlayHistory.played_at < datetime(year + 1, 1, 1)
                )
            
            if artist_filter:
                query = query.filter(Artist.name == artist_filter)
            
            plays = query.all()
            
            # Convert to DataFrame
            data = []
            for play in plays:
                data.append({
                    'date': play.played_at.date(),
                    'plays': 1,
                    'track': play[1],
                    'artist': play.artist_name
                })
            
            df = pd.DataFrame(data)
            if not df.empty:
                # Group by date and count plays
                df = df.groupby('date')['plays'].sum().reset_index()
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            
            return df
    
    def get_top_tracks_by_period(self, days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
        """Get top tracks for a specific time period"""
        with self.db.session_scope() as session:
            play_counts = self.db.get_play_counts(session, days=days)
            
            results = []
            for track, count in play_counts[:limit]:
                results.append({
                    'position': len(results) + 1,
                    'track_name': track.name,
                    'artist_name': track.artist.name,
                    'album_name': track.album.name if track.album else '',
                    'play_count': count,
                    'spotify_id': track.spotify_id
                })
            
            return results
    
    def get_top_artists_by_period(self, days: int = 30, limit: int = 30) -> List[Dict[str, Any]]:
        """Get top artists for a specific time period"""
        with self.db.session_scope() as session:
            artist_plays = self.db.get_top_artists(session, days=days, limit=limit)
            
            results = []
            for artist, count in artist_plays:
                results.append({
                    'position': len(results) + 1,
                    'artist_name': artist.name,
                    'play_count': count,
                    'spotify_id': artist.spotify_id,
                    'genres': artist.genres
                })
            
            return results
    
    def get_listening_stats_by_hour(self, days: int = 30) -> Dict[int, int]:
        """Get listening patterns by hour of day"""
        with self.db.session_scope() as session:
            start_date = datetime.now() - timedelta(days=days)
            
            plays = session.query(PlayHistory).filter(
                PlayHistory.played_at >= start_date
            ).all()
            
            hour_counts = defaultdict(int)
            for play in plays:
                # Convert to local time if needed
                hour = play.played_at.hour
                hour_counts[hour] += 1
            
            return dict(hour_counts)
    
    def get_listening_stats_by_weekday(self, days: int = 30) -> Dict[str, int]:
        """Get listening patterns by day of week"""
        with self.db.session_scope() as session:
            start_date = datetime.now() - timedelta(days=days)
            
            plays = session.query(PlayHistory).filter(
                PlayHistory.played_at >= start_date
            ).all()
            
            weekday_counts = defaultdict(int)
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                           'Friday', 'Saturday', 'Sunday']
            
            for play in plays:
                weekday = weekday_names[play.played_at.weekday()]
                weekday_counts[weekday] += 1
            
            # Ensure all days are present
            for day in weekday_names:
                if day not in weekday_counts:
                    weekday_counts[day] = 0
            
            return dict(weekday_counts)
    
    def get_yearly_stats(self, year: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a specific year"""
        with self.db.session_scope() as session:
            # Define year boundaries
            year_start = datetime(year, 1, 1)
            year_end = datetime(year + 1, 1, 1)
            
            # Total plays
            total_plays = session.query(PlayHistory).filter(
                PlayHistory.played_at >= year_start,
                PlayHistory.played_at < year_end
            ).count()
            
            # Unique tracks
            unique_tracks = session.query(PlayHistory.track_id).filter(
                PlayHistory.played_at >= year_start,
                PlayHistory.played_at < year_end
            ).distinct().count()
            
            # Unique artists
            unique_artists = session.query(PlayHistory.artist_id).filter(
                PlayHistory.played_at >= year_start,
                PlayHistory.played_at < year_end
            ).distinct().count()
            
            # Top track
            top_track_result = session.query(
                Track, 
                func.count(PlayHistory.id).label('play_count')
            ).join(PlayHistory).filter(
                PlayHistory.played_at >= year_start,
                PlayHistory.played_at < year_end
            ).group_by(Track.id).order_by(
                func.count(PlayHistory.id).desc()
            ).first()
            
            top_track = None
            if top_track_result:
                track, count = top_track_result
                top_track = {
                    'track_name': track.name,
                    'artist_name': track.artist.name,
                    'play_count': count
                }
            
            # Top artist
            top_artist_result = session.query(
                Artist,
                func.count(PlayHistory.id).label('play_count')
            ).join(PlayHistory).filter(
                PlayHistory.played_at >= year_start,
                PlayHistory.played_at < year_end
            ).group_by(Artist.id).order_by(
                func.count(PlayHistory.id).desc()
            ).first()
            
            top_artist = None
            if top_artist_result:
                artist, count = top_artist_result
                top_artist = {
                    'artist_name': artist.name,
                    'play_count': count
                }
            
            # Monthly breakdown
            from sqlalchemy import func
            monthly_plays = session.query(
                func.strftime('%m', PlayHistory.played_at).label('month'),
                func.count(PlayHistory.id).label('play_count')
            ).filter(
                PlayHistory.played_at >= year_start,
                PlayHistory.played_at < year_end
            ).group_by('month').all()
            
            monthly_data = {int(month): count for month, count in monthly_plays}
            
            return {
                'year': year,
                'total_plays': total_plays,
                'unique_tracks': unique_tracks,
                'unique_artists': unique_artists,
                'top_track': top_track,
                'top_artist': top_artist,
                'monthly_plays': monthly_data,
                'daily_average': total_plays / 365 if total_plays else 0
            }
    
    def get_music_discovery_timeline(self, days: int = 90) -> List[Dict[str, Any]]:
        """Get timeline of when new artists were discovered"""
        with self.db.session_scope() as session:
            # Get first play date for each artist
            from sqlalchemy import func, and_
            
            first_plays = session.query(
                Artist.name,
                func.min(PlayHistory.played_at).label('first_played'),
                func.count(PlayHistory.id).label('total_plays')
            ).join(PlayHistory).group_by(Artist.id).having(
                func.min(PlayHistory.played_at) >= datetime.now() - timedelta(days=days)
            ).order_by('first_played').all()
            
            results = []
            for artist_name, first_played, total_plays in first_plays:
                results.append({
                    'artist_name': artist_name,
                    'discovered_date': first_played.date(),
                    'total_plays_since': total_plays
                })
            
            return results
    
    def get_listening_diversity_score(self, days: int = 30) -> Dict[str, Any]:
        """Calculate listening diversity metrics"""
        with self.db.session_scope() as session:
            start_date = datetime.now() - timedelta(days=days)
            
            # Get all plays in period
            plays = session.query(
                PlayHistory.track_id,
                PlayHistory.artist_id
            ).filter(
                PlayHistory.played_at >= start_date
            ).all()
            
            if not plays:
                return {
                    'artist_diversity': 0,
                    'track_diversity': 0,
                    'top_artist_percentage': 0,
                    'unique_artists': 0,
                    'unique_tracks': 0
                }
            
            # Count plays per artist and track
            artist_counts = Counter(play.artist_id for play in plays)
            track_counts = Counter(play.track_id for play in plays)
            
            total_plays = len(plays)
            unique_artists = len(artist_counts)
            unique_tracks = len(track_counts)
            
            # Calculate diversity scores (higher = more diverse)
            artist_diversity = unique_artists / total_plays if total_plays else 0
            track_diversity = unique_tracks / total_plays if total_plays else 0
            
            # Top artist percentage
            top_artist_plays = max(artist_counts.values()) if artist_counts else 0
            top_artist_percentage = (top_artist_plays / total_plays * 100) if total_plays else 0
            
            return {
                'artist_diversity': round(artist_diversity, 3),
                'track_diversity': round(track_diversity, 3),
                'top_artist_percentage': round(top_artist_percentage, 1),
                'unique_artists': unique_artists,
                'unique_tracks': unique_tracks,
                'total_plays': total_plays
            }
    
    def get_peak_listening_periods(self, artist_name: str) -> List[Dict[str, Any]]:
        """Find peak listening periods for a specific artist"""
        with self.db.session_scope() as session:
            # Get all plays for the artist
            artist = session.query(Artist).filter_by(name=artist_name).first()
            if not artist:
                return []
            
            plays = session.query(PlayHistory).filter_by(
                artist_id=artist.id
            ).order_by(PlayHistory.played_at).all()
            
            if not plays:
                return []
            
            # Group plays by month
            monthly_plays = defaultdict(int)
            for play in plays:
                month_key = play.played_at.strftime('%Y-%m')
                monthly_plays[month_key] += 1
            
            # Find peak months
            sorted_months = sorted(monthly_plays.items(), 
                                 key=lambda x: x[1], reverse=True)
            
            results = []
            for month_str, count in sorted_months[:12]:  # Top 12 months
                year, month = map(int, month_str.split('-'))
                results.append({
                    'year': year,
                    'month': month,
                    'month_name': datetime(year, month, 1).strftime('%B %Y'),
                    'play_count': count
                })
            
            return results