from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from loguru import logger

from ..api.spotify_client import SpotifyClient
from ..core.database import DatabaseManager
from ..core.models import Track, Playlist
from ..core.config import get_config


class PlaylistService:
    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.spotify = SpotifyClient()
        
    def update_all_playlists(self) -> Dict[str, Tuple[bool, Optional[str]]]:
        """Update all configured playlists"""
        results = {}
        
        # Update each playlist type
        playlist_configs = self.config.playlists
        
        if 'most_listened' in playlist_configs:
            results['most_listened'] = self.update_most_listened_playlist()
            
        if 'recent_favorites' in playlist_configs:
            results['recent_favorites'] = self.update_recent_favorites_playlist()
            
        if 'binged_songs' in playlist_configs:
            results['binged_songs'] = self.update_binged_songs_playlist()
            
        return results
    
    def update_most_listened_playlist(self) -> Tuple[bool, Optional[str]]:
        """Update the most listened to playlist"""
        try:
            config = self.config.playlists.get('most_listened')
            if not config:
                error_msg = "Most Listened playlist not configured. Please add it to your configuration."
                logger.warning(error_msg)
                return False, error_msg
            
            if not config.id or config.id == '':
                error_msg = "Most Listened playlist ID is empty. Please set MOST_LISTENED_ID environment variable."
                logger.warning(error_msg)
                return False, error_msg
            
            with self.db.session_scope() as session:
                # Get playlist
                playlist = self.db.get_or_create_playlist(
                    session,
                    name="Most Listened To",
                    spotify_id=config.id,
                    playlist_type='most_listened',
                    size=config.size
                )
                
                # Get most played tracks
                play_counts = self.db.get_play_counts(session)
                tracks = [track for track, count in play_counts[:config.size]]
                
                # Filter tracks with Spotify IDs
                tracks_with_ids = [t for t in tracks if t.spotify_id]
                
                if not tracks_with_ids:
                    error_msg = "No tracks with Spotify IDs found. Please sync your Spotify library first."
                    logger.warning(error_msg)
                    return False, error_msg
                
                # Update playlist on Spotify
                track_ids = [t.spotify_id for t in tracks_with_ids]
                success = self.spotify.update_playlist_tracks(config.id, track_ids)
                
                if success:
                    # Update database
                    self.db.update_playlist_tracks(session, playlist, tracks_with_ids)
                    logger.info(f"Updated most listened playlist with {len(tracks_with_ids)} tracks")
                    return True, None
                else:
                    error_msg = "Failed to update playlist on Spotify. Check your authentication."
                    return False, error_msg
                
        except Exception as e:
            error_msg = f"Failed to update most listened playlist: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def update_recent_favorites_playlist(self) -> Tuple[bool, Optional[str]]:
        """Update the recent favorites playlist"""
        try:
            config = self.config.playlists.get('recent_favorites')
            if not config:
                error_msg = "Recent Favorites playlist not configured. Please add it to your configuration."
                logger.warning(error_msg)
                return False, error_msg
            
            if not config.id or config.id == '':
                error_msg = "Recent Favorites playlist ID is empty. Please set RECENT_FAVORITES_ID environment variable."
                logger.warning(error_msg)
                return False, error_msg
            
            with self.db.session_scope() as session:
                # Get playlist
                playlist = self.db.get_or_create_playlist(
                    session,
                    name="Recent Favorites",
                    spotify_id=config.id,
                    playlist_type='recent_favorites',
                    size=config.size
                )
                
                # Get recent favorites
                days = config.timeframe_days or 30
                play_counts = self.db.get_play_counts(session, days=days)
                tracks = [track for track, count in play_counts[:config.size]]
                
                # Filter tracks with Spotify IDs
                tracks_with_ids = [t for t in tracks if t.spotify_id]
                
                if not tracks_with_ids:
                    error_msg = f"No tracks with Spotify IDs found in the last {days} days. Please sync your Spotify library."
                    logger.warning(error_msg)
                    return False, error_msg
                
                # Update playlist on Spotify
                track_ids = [t.spotify_id for t in tracks_with_ids]
                success = self.spotify.update_playlist_tracks(config.id, track_ids)
                
                if success:
                    # Update database
                    self.db.update_playlist_tracks(session, playlist, tracks_with_ids)
                    logger.info(f"Updated recent favorites playlist with {len(tracks_with_ids)} tracks")
                    return True, None
                else:
                    error_msg = "Failed to update playlist on Spotify. Check your authentication."
                    return False, error_msg
                
        except Exception as e:
            error_msg = f"Failed to update recent favorites playlist: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def update_binged_songs_playlist(self) -> Tuple[bool, Optional[str]]:
        """Update the binged songs playlist"""
        try:
            config = self.config.playlists.get('binged_songs')
            if not config:
                error_msg = "Binged Songs playlist not configured. Please add it to your configuration."
                logger.warning(error_msg)
                return False, error_msg
            
            if not config.id or config.id == '':
                error_msg = "Binged Songs playlist ID is empty. Please set BINGED_SONGS_ID environment variable."
                logger.warning(error_msg)
                return False, error_msg
            
            with self.db.session_scope() as session:
                # Get playlist
                playlist = self.db.get_or_create_playlist(
                    session,
                    name="Binged Songs",
                    spotify_id=config.id,
                    playlist_type='binged_songs',
                    size=config.size
                )
                
                # Get binged songs
                min_plays = config.min_daily_plays or 3
                binged_tracks = self.db.get_binged_songs(session, min_daily_plays=min_plays)
                tracks = [track for track, count in binged_tracks[:config.size]]
                
                # Filter tracks with Spotify IDs
                tracks_with_ids = [t for t in tracks if t.spotify_id]
                
                if not tracks_with_ids:
                    error_msg = f"No binged tracks (played {min_plays}+ times per day) with Spotify IDs found. Try lowering the threshold or sync more data."
                    logger.warning(error_msg)
                    return False, error_msg
                
                # Update playlist on Spotify
                track_ids = [t.spotify_id for t in tracks_with_ids]
                success = self.spotify.update_playlist_tracks(config.id, track_ids)
                
                if success:
                    # Update database
                    self.db.update_playlist_tracks(session, playlist, tracks_with_ids)
                    logger.info(f"Updated binged songs playlist with {len(tracks_with_ids)} tracks")
                    return True, None
                else:
                    error_msg = "Failed to update playlist on Spotify. Check your authentication."
                    return False, error_msg
                
        except Exception as e:
            error_msg = f"Failed to update binged songs playlist: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def create_playlist(self, name: str, playlist_type: str, 
                       description: str = "") -> Optional[str]:
        """Create a new playlist on Spotify"""
        playlist_id = self.spotify.create_playlist(name, description)
        
        if playlist_id:
            # Store in database
            with self.db.session_scope() as session:
                self.db.get_or_create_playlist(
                    session,
                    name=name,
                    spotify_id=playlist_id,
                    playlist_type=playlist_type
                )
            
        return playlist_id
    
    def get_playlist_stats(self) -> Dict[str, Any]:
        """Get statistics about all playlists"""
        with self.db.session_scope() as session:
            playlists = session.query(Playlist).all()
            
            stats = {}
            for playlist in playlists:
                track_count = len(playlist.tracks)
                stats[playlist.type] = {
                    'name': playlist.name,
                    'spotify_id': playlist.spotify_id,
                    'track_count': track_count,
                    'last_updated': playlist.last_updated,
                    'configured_size': playlist.size
                }
            
            return stats
    
    def find_tracks_without_spotify_ids(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Find popular tracks that don't have Spotify IDs"""
        with self.db.session_scope() as session:
            # Get play counts for tracks without Spotify IDs
            from sqlalchemy import func, and_
            from ..core.models import Track, PlayHistory
            
            tracks = session.query(
                Track,
                func.count(PlayHistory.id).label('play_count')
            ).join(PlayHistory).filter(
                Track.spotify_id == None
            ).group_by(Track.id).order_by(
                func.count(PlayHistory.id).desc()
            ).limit(limit).all()
            
            return [{
                'track_name': track.name,
                'artist_name': track.artist.name,
                'album_name': track.album.name if track.album else None,
                'play_count': count
            } for track, count in tracks]
    
    def get_playlist_candidates(self, playlist_type: str, 
                               limit: int = 50) -> List[Dict[str, Any]]:
        """Get candidate tracks for a specific playlist type"""
        with self.db.session_scope() as session:
            if playlist_type == 'most_listened':
                results = self.db.get_play_counts(session)[:limit]
            elif playlist_type == 'recent_favorites':
                results = self.db.get_play_counts(session, days=30)[:limit]
            elif playlist_type == 'binged_songs':
                results = self.db.get_binged_songs(session)[:limit]
            else:
                return []
            
            candidates = []
            for track, count in results:
                candidates.append({
                    'track_name': track.name,
                    'artist_name': track.artist.name,
                    'album_name': track.album.name if track.album else None,
                    'play_count': count,
                    'has_spotify_id': bool(track.spotify_id)
                })
            
            return candidates