"""
Pattern detection and analysis for listening habits
"""
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, Counter
import statistics
from loguru import logger

# Import shared components
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared import DatabaseManager, Track, Artist, PlayHistory
from sqlalchemy import func, Date


class PatternAnalyzer:
    """Analyzes listening patterns and habits"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def get_listening_streaks(self, min_days: int = 3) -> List[Dict[str, Any]]:
        """Find consecutive days of listening"""
        with self.db.session_scope() as session:
            # Get all play dates
            plays = session.query(
                PlayHistory.played_at.cast(Date).label('play_date')
            ).distinct().order_by('play_date').all()
            
            if not plays:
                return []
            
            streaks = []
            current_streak = [plays[0].play_date]
            
            for i in range(1, len(plays)):
                if plays[i].play_date - plays[i-1].play_date == timedelta(days=1):
                    current_streak.append(plays[i].play_date)
                else:
                    if len(current_streak) >= min_days:
                        streaks.append({
                            'start': current_streak[0],
                            'end': current_streak[-1],
                            'days': len(current_streak)
                        })
                    current_streak = [plays[i].play_date]
            
            # Check last streak
            if len(current_streak) >= min_days:
                streaks.append({
                    'start': current_streak[0],
                    'end': current_streak[-1],
                    'days': len(current_streak)
                })
            
            return sorted(streaks, key=lambda x: x['days'], reverse=True)
    
    def get_discovery_timeline(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Track when new artists were discovered"""
        with self.db.session_scope() as session:
            # Get first play of each artist
            subquery = session.query(
                PlayHistory.artist_id,
                func.min(PlayHistory.played_at).label('first_play')
            ).group_by(PlayHistory.artist_id).subquery()
            
            query = session.query(
                Artist.name,
                Artist.id,
                subquery.c.first_play
            ).join(subquery, Artist.id == subquery.c.artist_id)
            
            if year:
                query = query.filter(
                    subquery.c.first_play >= datetime(year, 1, 1),
                    subquery.c.first_play < datetime(year + 1, 1, 1)
                )
            
            discoveries = query.order_by(subquery.c.first_play).all()
            
            timeline = []
            for artist_name, artist_id, first_play in discoveries:
                # Get play count in first month
                first_month_plays = session.query(PlayHistory).filter(
                    PlayHistory.artist_id == artist_id,
                    PlayHistory.played_at >= first_play,
                    PlayHistory.played_at < first_play + timedelta(days=30)
                ).count()
                
                timeline.append({
                    'artist': artist_name,
                    'discovered_on': first_play,
                    'first_month_plays': first_month_plays,
                    'still_listening': self._is_still_listening(session, artist_id)
                })
            
            return timeline
    
    def _is_still_listening(self, session, artist_id: int) -> bool:
        """Check if still listening to an artist (played in last 90 days)"""
        recent_play = session.query(PlayHistory).filter(
            PlayHistory.artist_id == artist_id,
            PlayHistory.played_at >= datetime.now() - timedelta(days=90)
        ).first()
        return recent_play is not None
    
    def get_listening_personality(self) -> Dict[str, Any]:
        """Determine listening personality type"""
        with self.db.session_scope() as session:
            total_plays = session.query(PlayHistory).count()
            unique_tracks = session.query(Track).count()
            unique_artists = session.query(Artist).count()
            
            # Calculate repeat rate
            avg_plays_per_track = total_plays / unique_tracks if unique_tracks > 0 else 0
            
            # Calculate discovery rate (new artists per month)
            months_of_data = self._get_months_of_data(session)
            discovery_rate = unique_artists / months_of_data if months_of_data > 0 else 0
            
            # Determine personality
            personality = {
                'type': '',
                'description': '',
                'stats': {
                    'repeat_rate': avg_plays_per_track,
                    'discovery_rate': discovery_rate,
                    'unique_tracks': unique_tracks,
                    'unique_artists': unique_artists,
                    'total_plays': total_plays
                }
            }
            
            if avg_plays_per_track > 5 and discovery_rate < 5:
                personality['type'] = 'Comfort Listener'
                personality['description'] = 'You find your favorites and stick with them'
            elif avg_plays_per_track < 3 and discovery_rate > 10:
                personality['type'] = 'Musical Explorer'
                personality['description'] = 'Always seeking new sounds and artists'
            elif avg_plays_per_track > 4 and discovery_rate > 8:
                personality['type'] = 'Passionate Collector'
                personality['description'] = 'You discover lots of music and play favorites repeatedly'
            else:
                personality['type'] = 'Balanced Listener'
                personality['description'] = 'A healthy mix of favorites and discoveries'
            
            return personality
    
    def _get_months_of_data(self, session) -> float:
        """Calculate how many months of data we have"""
        first_play = session.query(func.min(PlayHistory.played_at)).scalar()
        last_play = session.query(func.max(PlayHistory.played_at)).scalar()
        
        if not first_play or not last_play:
            return 0
        
        days = (last_play - first_play).days
        return days / 30.0
    
    def get_peak_listening_periods(self) -> Dict[str, Any]:
        """Identify peak listening times and days"""
        with self.db.session_scope() as session:
            plays = session.query(PlayHistory).all()
            
            hours = defaultdict(int)
            days = defaultdict(int)
            months = defaultdict(int)
            
            for play in plays:
                hours[play.played_at.hour] += 1
                days[play.played_at.strftime('%A')] += 1
                months[play.played_at.month] += 1
            
            return {
                'peak_hour': max(hours.items(), key=lambda x: x[1]),
                'peak_day': max(days.items(), key=lambda x: x[1]),
                'peak_month': max(months.items(), key=lambda x: x[1]),
                'by_hour': dict(hours),
                'by_day': dict(days),
                'by_month': dict(months)
            }
    
    def get_binge_sessions(self, min_duration_hours: float = 2) -> List[Dict[str, Any]]:
        """Find extended listening sessions"""
        with self.db.session_scope() as session:
            plays = session.query(PlayHistory).order_by(PlayHistory.played_at).all()
            
            sessions = []
            current_session = []
            
            for i, play in enumerate(plays):
                if not current_session:
                    current_session = [play]
                else:
                    # Check if this play is within 10 minutes of the last
                    time_diff = play.played_at - current_session[-1].played_at
                    if time_diff.total_seconds() < 600:  # 10 minutes
                        current_session.append(play)
                    else:
                        # Session ended, check if it's long enough
                        session_duration = current_session[-1].played_at - current_session[0].played_at
                        if session_duration.total_seconds() >= min_duration_hours * 3600:
                            sessions.append(self._analyze_session(current_session))
                        current_session = [play]
            
            # Check last session
            if len(current_session) > 1:
                session_duration = current_session[-1].played_at - current_session[0].played_at
                if session_duration.total_seconds() >= min_duration_hours * 3600:
                    sessions.append(self._analyze_session(current_session))
            
            return sorted(sessions, key=lambda x: x['duration_hours'], reverse=True)[:20]
    
    def _analyze_session(self, plays: List[PlayHistory]) -> Dict[str, Any]:
        """Analyze a listening session"""
        start = plays[0].played_at
        end = plays[-1].played_at
        duration = (end - start).total_seconds() / 3600
        
        # Count unique artists and tracks
        artists = set()
        tracks = set()
        for play in plays:
            artists.add(play.track.artist.name)
            tracks.add(play.track.name)
        
        return {
            'start': start,
            'end': end,
            'duration_hours': round(duration, 1),
            'track_count': len(plays),
            'unique_tracks': len(tracks),
            'unique_artists': len(artists),
            'dominant_artist': Counter([p.track.artist.name for p in plays]).most_common(1)[0] if plays else None
        }
    
    def get_peak_month_by_artist(self, artist_name: str) -> Dict[str, Any]:
        """Find the peak listening month for a specific artist"""
        with self.db.session_scope() as session:
            # Find the artist
            artist = session.query(Artist).filter_by(name=artist_name).first()
            if not artist:
                return {'error': 'Artist not found'}
            
            # Get all plays for this artist grouped by month
            plays = session.query(
                func.strftime('%Y-%m', PlayHistory.played_at).label('month'),
                func.count(PlayHistory.id).label('play_count')
            ).join(Track).filter(
                Track.artist_id == artist.id
            ).group_by('month').order_by(
                func.count(PlayHistory.id).desc()
            ).all()
            
            if not plays:
                return {'error': 'No plays found for artist'}
            
            # Get the peak month
            peak_month_str, peak_count = plays[0]
            year, month = map(int, peak_month_str.split('-'))
            
            # Get all months data for context
            monthly_data = []
            for month_str, count in plays:
                y, m = map(int, month_str.split('-'))
                monthly_data.append({
                    'year': y,
                    'month': m,
                    'month_name': datetime(y, m, 1).strftime('%B %Y'),
                    'play_count': count
                })
            
            return {
                'artist': artist_name,
                'peak_month': {
                    'year': year,
                    'month': month,
                    'month_name': datetime(year, month, 1).strftime('%B %Y'),
                    'play_count': peak_count
                },
                'all_months': monthly_data[:12]  # Top 12 months
            }
    
    def analyze_binge_patterns(self, min_plays_per_day: int = 3) -> Dict[str, Any]:
        """Analyze binge listening patterns across all tracks"""
        with self.db.session_scope() as session:
            # Get daily play counts per track
            daily_plays = session.query(
                Track.id,
                func.date(PlayHistory.played_at).label('play_date'),
                func.count(PlayHistory.id).label('daily_count')
            ).join(PlayHistory).group_by(
                Track.id,
                func.date(PlayHistory.played_at)
            ).having(
                func.count(PlayHistory.id) >= min_plays_per_day
            ).all()
            
            if not daily_plays:
                return {
                    'total_binge_days': 0,
                    'unique_binged_tracks': 0,
                    'top_binge_days': [],
                    'binge_patterns': {}
                }
            
            # Analyze patterns
            binge_days = defaultdict(int)
            track_binges = defaultdict(list)
            
            for track_id, play_date, count in daily_plays:
                binge_days[play_date] += 1
                track_binges[track_id].append((play_date, count))
            
            # Find days with most binged tracks
            top_binge_days = sorted(binge_days.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Calculate binge frequency patterns
            binge_frequencies = Counter()
            for track_id, binges in track_binges.items():
                frequency = len(binges)
                binge_frequencies[frequency] += 1
            
            return {
                'total_binge_days': len(binge_days),
                'unique_binged_tracks': len(track_binges),
                'top_binge_days': [
                    {
                        'date': day,
                        'tracks_binged': count
                    } for day, count in top_binge_days
                ],
                'binge_patterns': {
                    'single_binge': binge_frequencies.get(1, 0),
                    'occasional_binge': sum(v for k, v in binge_frequencies.items() if 2 <= k <= 5),
                    'frequent_binge': sum(v for k, v in binge_frequencies.items() if k > 5)
                }
            }