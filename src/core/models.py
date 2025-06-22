from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Artist(Base):
    __tablename__ = 'artists'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    spotify_id = Column(String, unique=True)
    genres = Column(String)  # JSON string
    
    # Relationships
    tracks = relationship("Track", back_populates="artist")
    plays = relationship("PlayHistory", back_populates="artist")


class Album(Base):
    __tablename__ = 'albums'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    artist_id = Column(Integer, ForeignKey('artists.id'))
    spotify_id = Column(String, unique=True)
    release_date = Column(DateTime)
    
    # Relationships
    tracks = relationship("Track", back_populates="album")
    
    __table_args__ = (
        UniqueConstraint('name', 'artist_id', name='_album_artist_uc'),
    )


class Track(Base):
    __tablename__ = 'tracks'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    artist_id = Column(Integer, ForeignKey('artists.id'), nullable=False)
    album_id = Column(Integer, ForeignKey('albums.id'))
    spotify_id = Column(String, unique=True)
    duration_ms = Column(Integer)
    popularity = Column(Integer)
    
    # Relationships
    artist = relationship("Artist", back_populates="tracks")
    album = relationship("Album", back_populates="tracks")
    plays = relationship("PlayHistory", back_populates="track")
    
    __table_args__ = (
        UniqueConstraint('name', 'artist_id', 'album_id', name='_track_artist_album_uc'),
        Index('idx_track_spotify_id', 'spotify_id'),
    )


class PlayHistory(Base):
    __tablename__ = 'play_history'
    
    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey('tracks.id'), nullable=False)
    artist_id = Column(Integer, ForeignKey('artists.id'), nullable=False)
    played_at = Column(DateTime, nullable=False)
    source = Column(String, default='lastfm')  # 'lastfm' or 'spotify'
    lastfm_url = Column(String)  # Store Last.fm URL as unique identifier
    
    # Relationships
    track = relationship("Track", back_populates="plays")
    artist = relationship("Artist", back_populates="plays")
    
    __table_args__ = (
        UniqueConstraint('track_id', 'played_at', name='_track_time_uc'),
        Index('idx_played_at', 'played_at'),
        Index('idx_track_played', 'track_id', 'played_at'),
        Index('idx_lastfm_url', 'lastfm_url'),
    )


class Playlist(Base):
    __tablename__ = 'playlists'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    spotify_id = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False)  # 'most_listened', 'recent_favorites', 'binged_songs'
    size = Column(Integer, default=50)
    last_updated = Column(DateTime)
    config = Column(String)  # JSON string for additional config
    
    # Relationships
    tracks = relationship("PlaylistTrack", back_populates="playlist")


class PlaylistTrack(Base):
    __tablename__ = 'playlist_tracks'
    
    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey('playlists.id'), nullable=False)
    track_id = Column(Integer, ForeignKey('tracks.id'), nullable=False)
    position = Column(Integer, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    playlist = relationship("Playlist", back_populates="tracks")
    track = relationship("Track")
    
    __table_args__ = (
        UniqueConstraint('playlist_id', 'position', name='_playlist_position_uc'),
    )


class SyncStatus(Base):
    __tablename__ = 'sync_status'
    
    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False, unique=True)  # 'lastfm' or 'spotify'
    last_sync = Column(DateTime)
    last_successful_sync = Column(DateTime)
    status = Column(String, default='idle')  # 'idle', 'running', 'error'
    error_message = Column(String)
    tracks_synced = Column(Integer, default=0)


class SyncProgress(Base):
    __tablename__ = 'sync_progress'
    
    id = Column(Integer, primary_key=True)
    sync_type = Column(String, nullable=False, unique=True)  # 'lastfm_full', 'lastfm_incremental'
    status = Column(String, default='idle')  # 'idle', 'running', 'completed', 'error'
    current_chunk = Column(String)  # e.g., '2019-01' for monthly chunks
    last_timestamp = Column(Integer)  # Unix timestamp of last processed track
    last_page = Column(Integer, default=1)
    total_chunks_completed = Column(Integer, default=0)
    total_tracks_synced = Column(Integer, default=0)
    api_calls_made = Column(Integer, default=0)
    started_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_count = Column(Integer, default=0)
    last_error = Column(String)


class UserPreference(Base):
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Database helper functions
def get_engine(database_path: str):
    """Create database engine"""
    return create_engine(f'sqlite:///{database_path}', echo=False)


def init_database(database_path: str):
    """Initialize database with all tables"""
    engine = get_engine(database_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine) -> Session:
    """Get database session"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()