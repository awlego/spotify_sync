from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session
from contextlib import contextmanager
import json

from .models import (
    Artist, Album, Track, PlayHistory, Playlist, PlaylistTrack,
    SyncStatus, SyncProgress, UserPreference, get_engine, init_database, get_session
)
from .config import get_config


class DatabaseManager:
    def __init__(self, database_path: Optional[str] = None):
        config = get_config()
        self.database_path = database_path or config.database.path
        self.engine = get_engine(self.database_path)
        init_database(self.database_path)
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for database operations"""
        session = get_session(self.engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # Artist operations
    def get_or_create_artist(self, session: Session, name: str, spotify_id: Optional[str] = None) -> Artist:
        """Get existing artist or create new one"""
        artist = session.query(Artist).filter_by(name=name).first()
        if not artist:
            artist = Artist(name=name, spotify_id=spotify_id)
            session.add(artist)
            session.flush()
        elif spotify_id and not artist.spotify_id:
            artist.spotify_id = spotify_id
        return artist
    
    # Album operations
    def get_or_create_album(self, session: Session, name: str, artist_id: int, 
                           spotify_id: Optional[str] = None) -> Album:
        """Get existing album or create new one"""
        album = session.query(Album).filter_by(name=name, artist_id=artist_id).first()
        if not album:
            album = Album(name=name, artist_id=artist_id, spotify_id=spotify_id)
            session.add(album)
            session.flush()
        elif spotify_id and not album.spotify_id:
            album.spotify_id = spotify_id
        return album
    
    # Track operations
    def get_or_create_track(self, session: Session, name: str, artist_name: str, 
                           album_name: Optional[str] = None, spotify_id: Optional[str] = None) -> Track:
        """Get existing track or create new one"""
        artist = self.get_or_create_artist(session, artist_name)
        
        album = None
        if album_name:
            album = self.get_or_create_album(session, album_name, artist.id)
        
        track = session.query(Track).filter_by(
            name=name, 
            artist_id=artist.id,
            album_id=album.id if album else None
        ).first()
        
        if not track:
            track = Track(
                name=name,
                artist_id=artist.id,
                album_id=album.id if album else None,
                spotify_id=spotify_id
            )
            session.add(track)
            session.flush()
        elif spotify_id and not track.spotify_id:
            track.spotify_id = spotify_id
            
        return track
    
    # Play history operations
    def add_play(self, session: Session, track: Track, played_at: datetime, 
                 source: str = 'lastfm', lastfm_url: Optional[str] = None) -> Optional[PlayHistory]:
        """Add a play to history if it doesn't already exist"""
        existing = session.query(PlayHistory).filter_by(
            track_id=track.id,
            played_at=played_at
        ).first()
        
        if not existing:
            play = PlayHistory(
                track_id=track.id,
                artist_id=track.artist_id,
                played_at=played_at,
                source=source,
                lastfm_url=lastfm_url
            )
            session.add(play)
            return play
        return None
    
    def get_play_counts(self, session: Session, days: Optional[int] = None,
                       artist_filter: Optional[str] = None) -> List[Tuple[Track, int]]:
        """Get play counts for tracks, optionally filtered by time period and artist"""
        query = session.query(Track, func.count(PlayHistory.id).label('play_count'))\
            .join(PlayHistory)\
            .group_by(Track.id)
        
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(PlayHistory.played_at >= start_date)
        
        if artist_filter:
            query = query.join(Artist).filter(Artist.name == artist_filter)
        
        return query.order_by(desc('play_count')).all()
    
    def get_recent_plays(self, session: Session, limit: int = 50) -> List[PlayHistory]:
        """Get most recent plays"""
        return session.query(PlayHistory)\
            .order_by(desc(PlayHistory.played_at))\
            .limit(limit)\
            .all()
    
    def get_binged_songs(self, session: Session, min_daily_plays: int = 3, 
                        days: Optional[int] = None) -> List[Tuple[Track, int]]:
        """Get songs that were played multiple times in a single day"""
        query = session.query(
            Track,
            func.date(PlayHistory.played_at).label('play_date'),
            func.count(PlayHistory.id).label('daily_count')
        ).join(PlayHistory).group_by(Track.id, 'play_date')
        
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(PlayHistory.played_at >= start_date)
        
        # Subquery to find tracks with high daily play counts
        subquery = query.having(func.count(PlayHistory.id) >= min_daily_plays).subquery()
        
        # Sum up the high daily counts for each track
        result = session.query(
            Track,
            func.sum(subquery.c.daily_count).label('total_binged_plays')
        ).join(
            subquery, Track.id == subquery.c.id
        ).group_by(Track.id).order_by(desc('total_binged_plays')).all()
        
        return result
    
    # Playlist operations
    def get_or_create_playlist(self, session: Session, name: str, spotify_id: str, 
                              playlist_type: str, size: int = 50) -> Playlist:
        """Get existing playlist or create new one"""
        playlist = session.query(Playlist).filter_by(spotify_id=spotify_id).first()
        if not playlist:
            playlist = Playlist(
                name=name,
                spotify_id=spotify_id,
                type=playlist_type,
                size=size
            )
            session.add(playlist)
            session.flush()
        return playlist
    
    def update_playlist_tracks(self, session: Session, playlist: Playlist, 
                              tracks: List[Track]) -> None:
        """Update playlist with new tracks"""
        # Remove existing tracks
        session.query(PlaylistTrack).filter_by(playlist_id=playlist.id).delete()
        
        # Add new tracks
        for position, track in enumerate(tracks[:playlist.size]):
            playlist_track = PlaylistTrack(
                playlist_id=playlist.id,
                track_id=track.id,
                position=position
            )
            session.add(playlist_track)
        
        playlist.last_updated = datetime.utcnow()
    
    # Sync status operations
    def get_sync_status(self, session: Session, source: str) -> SyncStatus:
        """Get or create sync status for a source"""
        status = session.query(SyncStatus).filter_by(source=source).first()
        if not status:
            status = SyncStatus(source=source)
            session.add(status)
            session.flush()
        return status
    
    def update_sync_status(self, session: Session, source: str, status: str, 
                          error_message: Optional[str] = None, tracks_synced: int = 0):
        """Update sync status"""
        sync_status = self.get_sync_status(session, source)
        sync_status.status = status
        sync_status.last_sync = datetime.utcnow()
        
        if status == 'success':
            sync_status.last_successful_sync = datetime.utcnow()
            sync_status.error_message = None
            sync_status.tracks_synced += tracks_synced
        elif status == 'error':
            sync_status.error_message = error_message
    
    # Progress tracking operations
    def get_sync_progress(self, session: Session, sync_type: str) -> SyncProgress:
        """Get or create sync progress tracker"""
        progress = session.query(SyncProgress).filter_by(sync_type=sync_type).first()
        if not progress:
            progress = SyncProgress(sync_type=sync_type)
            session.add(progress)
            session.flush()
        return progress
    
    def update_sync_progress(self, session: Session, sync_type: str, **kwargs):
        """Update sync progress with provided fields"""
        progress = self.get_sync_progress(session, sync_type)
        for key, value in kwargs.items():
            if hasattr(progress, key):
                setattr(progress, key, value)
        progress.updated_at = datetime.utcnow()
    
    def reset_sync_progress(self, session: Session, sync_type: str):
        """Reset sync progress for a fresh start"""
        progress = self.get_sync_progress(session, sync_type)
        progress.status = 'idle'
        progress.current_chunk = None
        progress.last_timestamp = None
        progress.last_page = 1
        progress.total_chunks_completed = 0
        progress.total_tracks_synced = 0
        progress.api_calls_made = 0
        progress.error_count = 0
        progress.last_error = None
        progress.started_at = None
        progress.updated_at = datetime.utcnow()
    
    # Analytics queries
    def get_top_artists(self, session: Session, days: Optional[int] = None, 
                       limit: int = 30) -> List[Tuple[Artist, int]]:
        """Get top artists by play count"""
        query = session.query(Artist, func.count(PlayHistory.id).label('play_count'))\
            .join(PlayHistory)\
            .group_by(Artist.id)
        
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(PlayHistory.played_at >= start_date)
        
        return query.order_by(desc('play_count')).limit(limit).all()
    
    def get_listening_stats_by_date(self, session: Session, 
                                   start_date: Optional[datetime] = None,
                                   end_date: Optional[datetime] = None) -> List[Tuple[datetime, int]]:
        """Get number of plays per day"""
        query = session.query(
            func.date(PlayHistory.played_at).label('play_date'),
            func.count(PlayHistory.id).label('play_count')
        ).group_by('play_date')
        
        if start_date:
            query = query.filter(PlayHistory.played_at >= start_date)
        if end_date:
            query = query.filter(PlayHistory.played_at <= end_date)
        
        return query.order_by('play_date').all()
    
    # User preferences
    def get_preference(self, session: Session, key: str) -> Optional[str]:
        """Get user preference value"""
        pref = session.query(UserPreference).filter_by(key=key).first()
        return pref.value if pref else None
    
    def set_preference(self, session: Session, key: str, value: str) -> None:
        """Set user preference"""
        pref = session.query(UserPreference).filter_by(key=key).first()
        if pref:
            pref.value = value
        else:
            pref = UserPreference(key=key, value=value)
            session.add(pref)