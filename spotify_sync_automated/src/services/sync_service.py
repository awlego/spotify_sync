from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from loguru import logger

from ..api.spotify_client import SpotifyClient
from ..api.lastfm_client import LastFMClient
from ..core.database import DatabaseManager
from ..core.config import get_config


class SyncService:
    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.spotify = SpotifyClient()
        self.lastfm = LastFMClient()
        
    def sync_all(self) -> Dict[str, Any]:
        """Perform a full sync from all sources"""
        results = {
            'lastfm': {'success': False, 'tracks_synced': 0, 'error': None},
            'spotify': {'success': False, 'tracks_synced': 0, 'error': None}
        }
        
        # Sync from Last.fm
        try:
            lastfm_count = self.sync_lastfm()
            results['lastfm']['success'] = True
            results['lastfm']['tracks_synced'] = lastfm_count
            logger.info(f"Last.fm sync completed: {lastfm_count} tracks")
        except Exception as e:
            results['lastfm']['error'] = str(e)
            logger.error(f"Last.fm sync failed: {e}")
        
        # Sync from Spotify
        try:
            spotify_count = self.sync_spotify_recent()
            results['spotify']['success'] = True
            results['spotify']['tracks_synced'] = spotify_count
            logger.info(f"Spotify sync completed: {spotify_count} tracks")
        except Exception as e:
            results['spotify']['error'] = str(e)
            logger.error(f"Spotify sync failed: {e}")
        
        return results
    
    def sync_lastfm(self, days_back: Optional[int] = None) -> int:
        """Sync tracks from Last.fm"""
        with self.db.session_scope() as session:
            # Get last sync time
            sync_status = self.db.get_sync_status(session, 'lastfm')
            
            # Determine how far back to sync
            if sync_status.last_successful_sync:
                # Add a small buffer to avoid missing tracks
                from_date = sync_status.last_successful_sync - timedelta(minutes=5)
            elif days_back:
                from_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            else:
                from_date = datetime.now(timezone.utc) - timedelta(days=self.config.sync.history_days)
            
            # Update sync status
            self.db.update_sync_status(session, 'lastfm', 'running')
            session.commit()
        
        try:
            # Fetch tracks from Last.fm
            logger.info(f"Fetching Last.fm tracks since {from_date}")
            tracks = self.lastfm.get_listening_history_since(from_date)
            
            # Process and store tracks
            tracks_added = 0
            with self.db.session_scope() as session:
                for track_data in tracks:
                    track = self.db.get_or_create_track(
                        session,
                        name=track_data['track'],
                        artist_name=track_data['artist'],
                        album_name=track_data['album'] if track_data['album'] else None
                    )
                    
                    # Try to get Spotify ID if we don't have it
                    if not track.spotify_id and self.spotify.ensure_authenticated():
                        spotify_track = self.spotify.search_track(
                            track_data['track'],
                            track_data['artist'],
                            track_data['album']
                        )
                        if spotify_track:
                            track.spotify_id = spotify_track['id']
                    
                    # Add play history
                    play = self.db.add_play(
                        session,
                        track,
                        track_data['played_at'],
                        source='lastfm'
                    )
                    
                    if play:
                        tracks_added += 1
                
                # Update sync status
                self.db.update_sync_status(
                    session, 'lastfm', 'success', 
                    tracks_synced=tracks_added
                )
            
            return tracks_added
            
        except Exception as e:
            with self.db.session_scope() as session:
                self.db.update_sync_status(
                    session, 'lastfm', 'error', 
                    error_message=str(e)
                )
            raise
    
    def sync_spotify_recent(self) -> int:
        """Sync recently played tracks from Spotify"""
        if not self.spotify.ensure_authenticated():
            logger.warning("Spotify not authenticated, skipping sync")
            return 0
        
        with self.db.session_scope() as session:
            # Update sync status
            self.db.update_sync_status(session, 'spotify', 'running')
            session.commit()
        
        try:
            # Fetch recently played from Spotify
            recent_tracks = self.spotify.get_recently_played(limit=50)
            
            # Process and store tracks
            tracks_added = 0
            with self.db.session_scope() as session:
                for item in recent_tracks:
                    track_info = item['track']
                    played_at = datetime.fromisoformat(
                        item['played_at'].replace('Z', '+00:00')
                    )
                    
                    # Create or get track
                    track = self.db.get_or_create_track(
                        session,
                        name=track_info['name'],
                        artist_name=track_info['artists'][0]['name'],
                        album_name=track_info['album']['name'],
                        spotify_id=track_info['id']
                    )
                    
                    # Update track metadata
                    track.duration_ms = track_info['duration_ms']
                    track.popularity = track_info['popularity']
                    
                    # Add play history
                    play = self.db.add_play(
                        session,
                        track,
                        played_at,
                        source='spotify'
                    )
                    
                    if play:
                        tracks_added += 1
                
                # Update sync status
                self.db.update_sync_status(
                    session, 'spotify', 'success',
                    tracks_synced=tracks_added
                )
            
            return tracks_added
            
        except Exception as e:
            with self.db.session_scope() as session:
                self.db.update_sync_status(
                    session, 'spotify', 'error',
                    error_message=str(e)
                )
            raise
    
    def sync_spotify_ids(self, limit: int = 100) -> int:
        """Find and update missing Spotify IDs for tracks"""
        if not self.spotify.ensure_authenticated():
            return 0
        
        updated = 0
        with self.db.session_scope() as session:
            # Find tracks without Spotify IDs
            from ..core.models import Track
            tracks = session.query(Track).filter(
                Track.spotify_id == None
            ).limit(limit).all()
            
            for track in tracks:
                spotify_track = self.spotify.search_track(
                    track.name,
                    track.artist.name,
                    track.album.name if track.album else None
                )
                
                if spotify_track:
                    track.spotify_id = spotify_track['id']
                    track.duration_ms = spotify_track['duration_ms']
                    track.popularity = spotify_track['popularity']
                    updated += 1
                    
                    # Update artist Spotify ID if needed
                    if not track.artist.spotify_id:
                        track.artist.spotify_id = spotify_track['artists'][0]['id']
        
        logger.info(f"Updated {updated} tracks with Spotify IDs")
        return updated
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status for all sources"""
        with self.db.session_scope() as session:
            lastfm_status = self.db.get_sync_status(session, 'lastfm')
            spotify_status = self.db.get_sync_status(session, 'spotify')
            
            return {
                'lastfm': {
                    'last_sync': lastfm_status.last_sync,
                    'last_successful_sync': lastfm_status.last_successful_sync,
                    'status': lastfm_status.status,
                    'error_message': lastfm_status.error_message,
                    'total_tracks_synced': lastfm_status.tracks_synced
                },
                'spotify': {
                    'last_sync': spotify_status.last_sync,
                    'last_successful_sync': spotify_status.last_successful_sync,
                    'status': spotify_status.status,
                    'error_message': spotify_status.error_message,
                    'total_tracks_synced': spotify_status.tracks_synced
                }
            }