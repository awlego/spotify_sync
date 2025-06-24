from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from loguru import logger
import sys
from pathlib import Path

# Add project root to path for shared imports
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared import DatabaseManager

# Use absolute imports within sync_service
from api.spotify_client import SpotifyClient
from api.lastfm_client import LastFMClient
from api.spotify_search_improvements import ImprovedSpotifySearch
from config import get_config


class SyncService:
    def __init__(self):
        self.config = get_config()
        self.db = DatabaseManager()
        self.spotify = SpotifyClient()
        self.lastfm = LastFMClient()
        self.search_helper = ImprovedSpotifySearch()
        
    def sync_all(self) -> Dict[str, Any]:
        """Perform a full sync from all sources"""
        results = {
            'lastfm': {'success': False, 'tracks_synced': 0, 'error': None}
        }
        
        # Sync from Last.fm only - Spotify should not be used as a listening history source
        try:
            lastfm_count = self.sync_lastfm()
            results['lastfm']['success'] = True
            results['lastfm']['tracks_synced'] = lastfm_count
            logger.info(f"Last.fm sync completed: {lastfm_count} tracks")
        except Exception as e:
            results['lastfm']['error'] = str(e)
            logger.error(f"Last.fm sync failed: {e}")
        
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
            # Convert datetime to timestamp for Last.fm API
            from_timestamp = int(from_date.timestamp())
            tracks = self.lastfm.get_all_recent_tracks(from_timestamp=from_timestamp)
            
            # Process and store tracks
            tracks_added = 0
            with self.db.session_scope() as session:
                for raw_track in tracks:
                    # Parse the raw Last.fm track data
                    track_data = self.lastfm.parse_track(raw_track)
                    
                    track = self.db.get_or_create_track(
                        session,
                        name=track_data['track'],
                        artist_name=track_data['artist'],
                        album_name=track_data['album'] if track_data['album'] else None
                    )
                    
                    # Try to get Spotify ID if we don't have it
                    if not track.spotify_id and self.spotify.ensure_authenticated():
                        # Try improved search first
                        spotify_track = self.search_helper.search_track_flexible(
                            self.spotify._sp,
                            track_data['track'],
                            track_data['artist'],
                            track_data['album'] if track_data['album'] else None
                        )
                        
                        # Fallback to original search if improved search fails
                        if not spotify_track:
                            spotify_track = self.spotify.search_track(
                                track_data['track'],
                                track_data['artist'],
                                track_data['album'] if track_data['album'] else None
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
    
    # DEPRECATED: Spotify should not be used as a listening history source
    # Last.fm is the only source of truth for listening history
    # This method is kept for reference but should not be called
    # def sync_spotify_recent(self) -> int:
    #     """Sync recently played tracks from Spotify"""
    #     if not self.spotify.ensure_authenticated():
    #         logger.warning("Spotify not authenticated, skipping sync")
    #         return 0
    #     
    #     with self.db.session_scope() as session:
    #         # Update sync status
    #         self.db.update_sync_status(session, 'spotify', 'running')
    #         session.commit()
    #     
    #     try:
    #         # Fetch recently played from Spotify
    #         recent_tracks = self.spotify.get_recently_played(limit=50)
    #         
    #         # Process and store tracks
    #         tracks_added = 0
    #         with self.db.session_scope() as session:
    #             for item in recent_tracks:
    #                 track_info = item['track']
    #                 played_at = datetime.fromisoformat(
    #                     item['played_at'].replace('Z', '+00:00')
    #                 )
    #                 
    #                 # Create or get track
    #                 track = self.db.get_or_create_track(
    #                     session,
    #                     name=track_info['name'],
    #                     artist_name=track_info['artists'][0]['name'],
    #                     album_name=track_info['album']['name'],
    #                     spotify_id=track_info['id']
    #                 )
    #                 
    #                 # Update track metadata
    #                 track.duration_ms = track_info['duration_ms']
    #                 track.popularity = track_info['popularity']
    #                 
    #                 # Add play history
    #                 play = self.db.add_play(
    #                     session,
    #                     track,
    #                     played_at,
    #                     source='spotify'
    #                 )
    #                 
    #                 if play:
    #                     tracks_added += 1
    #             
    #             # Update sync status
    #             self.db.update_sync_status(
    #                 session, 'spotify', 'success',
    #                 tracks_synced=tracks_added
    #             )
    #         
    #         return tracks_added
    #         
    #     except Exception as e:
    #         with self.db.session_scope() as session:
    #             self.db.update_sync_status(
    #                 session, 'spotify', 'error',
    #                 error_message=str(e)
    #             )
    #         raise
    
    def sync_spotify_ids(self, limit: int = 200) -> int:
        """Find and update missing Spotify IDs for tracks"""
        if not self.spotify.ensure_authenticated():
            return 0
        
        updated = 0
        skipped_duplicates = 0
        
        with self.db.session_scope() as session:
            # Find tracks without Spotify IDs
            from shared import Track
            tracks = session.query(Track).filter(
                Track.spotify_id == None
            ).limit(limit).all()
            
            for track in tracks:
                try:
                    # Try improved search first
                    spotify_track = self.search_helper.search_track_flexible(
                        self.spotify._sp,
                        track.name,
                        track.artist.name,
                        track.album.name if track.album else None
                    )
                    
                    # If no match, try finding alternative versions
                    if not spotify_track:
                        spotify_track = self.search_helper.find_alternative_versions(
                            self.spotify._sp,
                            track.name,
                            track.artist.name
                        )
                    
                    # Final fallback to original search
                    if not spotify_track:
                        spotify_track = self.spotify.search_track(
                            track.name,
                            track.artist.name,
                            track.album.name if track.album else None
                        )
                    
                    if spotify_track:
                        spotify_id = spotify_track['id']
                        
                        # Check if another track already has this Spotify ID
                        from sqlalchemy import and_
                        existing = session.query(Track).filter(
                            and_(
                                Track.spotify_id == spotify_id,
                                Track.id != track.id
                            )
                        ).first()
                        
                        if existing:
                            # Skip this track - it's a duplicate
                            skipped_duplicates += 1
                            logger.debug(f"Skipping duplicate: '{track.name}' by {track.artist.name} - "
                                       f"Spotify ID already assigned to '{existing.name}'")
                            continue
                        
                        # Update the track
                        track.spotify_id = spotify_id
                        track.duration_ms = spotify_track['duration_ms']
                        track.popularity = spotify_track['popularity']
                        updated += 1
                        
                        # Update artist Spotify ID if needed
                        if not track.artist.spotify_id:
                            track.artist.spotify_id = spotify_track['artists'][0]['id']
                            
                except Exception as e:
                    logger.error(f"Error updating track '{track.name}' by {track.artist.name}: {e}")
                    continue
        
        if skipped_duplicates > 0:
            logger.info(f"Skipped {skipped_duplicates} duplicate tracks")
        
        logger.info(f"Updated {updated} tracks with Spotify IDs")
        return updated
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status for all sources"""
        with self.db.session_scope() as session:
            lastfm_status = self.db.get_sync_status(session, 'lastfm')
            
            # Only return Last.fm status as it's the only listening history source
            return {
                'lastfm': {
                    'last_sync': lastfm_status.last_sync,
                    'last_successful_sync': lastfm_status.last_successful_sync,
                    'status': lastfm_status.status,
                    'error_message': lastfm_status.error_message,
                    'total_tracks_synced': lastfm_status.tracks_synced
                }
            }