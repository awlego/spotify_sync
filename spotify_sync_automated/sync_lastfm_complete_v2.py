#!/usr/bin/env python3
"""
Complete Last.fm history sync with monthly chunks and resume capability
Version 2 with better session management
"""

import sys
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from loguru import logger
import time
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.database import DatabaseManager
from src.api.lastfm_client import LastFMClient
from src.core.models import PlayHistory


class CompleteSyncManager:
    """Manages the complete sync process with resume capability"""
    
    def __init__(self, lastfm_client: LastFMClient, db_manager: DatabaseManager):
        self.lastfm = lastfm_client
        self.db = db_manager
        self.sync_type = 'lastfm_full'
        self.batch_size = 500  # Tracks per database batch
        self.pages_per_chunk = 50  # Max pages per month (10k tracks)
        
    def get_month_chunks(self, start_date: datetime, end_date: datetime):
        """Generate list of monthly chunks to sync"""
        chunks = []
        current = start_date.replace(day=1)
        
        while current < end_date:
            month_start = current
            month_end = (current + relativedelta(months=1)) - timedelta(seconds=1)
            
            # Don't go past end_date
            if month_end > end_date:
                month_end = end_date
                
            chunks.append({
                'id': current.strftime('%Y-%m'),
                'start': month_start,
                'end': month_end,
                'start_ts': int(month_start.timestamp()),
                'end_ts': int(month_end.timestamp())
            })
            
            current = current + relativedelta(months=1)
            
        return chunks
    
    def sync_chunk(self, chunk: dict):
        """Sync a single monthly chunk"""
        chunk_id = chunk['id']
        logger.info(f"\nSyncing chunk {chunk_id} ({chunk['start'].date()} to {chunk['end'].date()})")
        
        # Get current progress
        with self.db.session_scope() as session:
            progress = self.db.get_sync_progress(session, self.sync_type)
            start_page = progress.last_page if progress.current_chunk == chunk_id else 1
            api_calls_start = progress.api_calls_made
        
        tracks_added = 0
        page = start_page
        
        while page <= self.pages_per_chunk:
            logger.info(f"  Fetching page {page} for {chunk_id}")
            
            tracks, info = self.lastfm.get_recent_tracks_with_info(
                page=page,
                from_timestamp=chunk['start_ts'],
                to_timestamp=chunk['end_ts']
            )
            
            if not tracks:
                logger.info(f"  No tracks found on page {page}")
                break
            
            # Process tracks in batches
            for i in range(0, len(tracks), self.batch_size):
                batch = tracks[i:i + self.batch_size]
                batch_added = self.process_batch(batch)
                tracks_added += batch_added
                
                # Update progress after each batch
                with self.db.session_scope() as session:
                    progress = self.db.get_sync_progress(session, self.sync_type)
                    self.db.update_sync_progress(
                        session,
                        self.sync_type,
                        current_chunk=chunk_id,
                        last_page=page,
                        total_tracks_synced=progress.total_tracks_synced + batch_added,
                        api_calls_made=api_calls_start + (page - start_page + 1)
                    )
            
            # Check if we've reached the last page for this chunk
            if page >= info.get('totalPages', 1):
                logger.info(f"  Reached last page ({page}) for {chunk_id}")
                break
                
            page += 1
        
        logger.success(f"Chunk {chunk_id} complete: {tracks_added} tracks added")
        return tracks_added
    
    def process_batch(self, tracks):
        """Process a batch of tracks"""
        added = 0
        
        with self.db.session_scope() as session:
            for track_data in tracks:
                try:
                    parsed = self.lastfm.parse_track(track_data)
                    
                    # Get or create track
                    track = self.db.get_or_create_track(
                        session,
                        name=parsed['track'],
                        artist_name=parsed['artist'],
                        album_name=parsed['album'] if parsed['album'] else None
                    )
                    
                    # Add play with Last.fm URL for deduplication
                    play = self.db.add_play(
                        session,
                        track,
                        parsed['played_at'],
                        source='lastfm',
                        lastfm_url=parsed['url'] if parsed['url'] else None
                    )
                    
                    if play:
                        added += 1
                        
                except Exception as e:
                    logger.error(f"Error processing track: {e}")
                    continue
            
            session.commit()
            
        return added
    
    def run_sync(self, force_reset: bool = False):
        """Run the complete sync process"""
        logger.info("=== Last.fm Complete History Sync ===")
        
        # Get user info
        user_info = self.lastfm.get_user_info()
        if not user_info:
            logger.error("Failed to connect to Last.fm API")
            return False
        
        logger.info(f"Connected to Last.fm as: {user_info['name']}")
        logger.info(f"Total scrobbles on Last.fm: {int(user_info.get('playcount', 0)):,}")
        
        # Get current database status
        with self.db.session_scope() as session:
            current_plays = session.query(PlayHistory).filter_by(source='lastfm').count()
            logger.info(f"Current plays in database: {current_plays:,}")
            
            # Get or create progress tracker
            progress = self.db.get_sync_progress(session, self.sync_type)
            
            if force_reset or progress.status == 'error':
                logger.warning("Resetting sync progress...")
                self.db.reset_sync_progress(session, self.sync_type)
        
        # Determine date range
        registered = user_info.get('registered', {})
        if isinstance(registered, dict) and '#text' in registered:
            reg_timestamp = int(registered['#text'])
        else:
            # Default to 2019 if can't determine
            reg_timestamp = int(datetime(2019, 1, 1).timestamp())
        
        start_date = datetime.fromtimestamp(reg_timestamp)
        end_date = datetime.now()
        
        logger.info(f"Will sync from {start_date.date()} to {end_date.date()}")
        
        # Get monthly chunks
        chunks = self.get_month_chunks(start_date, end_date)
        logger.info(f"Total chunks to process: {len(chunks)}")
        
        # Update progress status
        with self.db.session_scope() as session:
            progress = self.db.get_sync_progress(session, self.sync_type)
            started_at = progress.started_at if progress.started_at else datetime.utcnow()
            self.db.update_sync_progress(
                session,
                self.sync_type,
                status='running',
                started_at=started_at
            )
        
        # Find starting chunk if resuming
        start_chunk_idx = 0
        with self.db.session_scope() as session:
            progress = self.db.get_sync_progress(session, self.sync_type)
            if progress.current_chunk:
                for i, chunk in enumerate(chunks):
                    if chunk['id'] == progress.current_chunk:
                        start_chunk_idx = i
                        logger.info(f"Resuming from chunk {progress.current_chunk} (chunk {i+1}/{len(chunks)})")
                        break
        
        # Process chunks
        start_time = time.time()
        total_added = 0
        
        # Sync each chunk
        for i, chunk in enumerate(chunks[start_chunk_idx:], start_chunk_idx):
            try:
                logger.info(f"\nProcessing chunk {i+1}/{len(chunks)}: {chunk['id']}")
                
                chunk_added = self.sync_chunk(chunk)
                total_added += chunk_added
                
                # Update progress
                with self.db.session_scope() as session:
                    progress = self.db.get_sync_progress(session, self.sync_type)
                    self.db.update_sync_progress(
                        session,
                        self.sync_type,
                        current_chunk=chunk['id'],
                        total_chunks_completed=i + 1,
                        last_page=1  # Reset for next chunk
                    )
                    
                    # Update main sync status
                    self.db.update_sync_status(session, 'lastfm', 'success', tracks_synced=chunk_added)
                
                # Progress report
                elapsed = time.time() - start_time
                rate = total_added / elapsed if elapsed > 0 else 0
                eta_chunks = len(chunks) - (i + 1)
                eta_seconds = (eta_chunks * (elapsed / (i - start_chunk_idx + 1))) if i > start_chunk_idx else 0
                
                with self.db.session_scope() as session:
                    progress = self.db.get_sync_progress(session, self.sync_type)
                    logger.info(f"Progress: {i+1}/{len(chunks)} chunks, "
                              f"{progress.total_tracks_synced:,} total tracks, "
                              f"{rate:.1f} tracks/sec, "
                              f"ETA: {int(eta_seconds/60)} minutes")
                
            except Exception as e:
                logger.error(f"Error syncing chunk {chunk['id']}: {e}")
                
                # Update error status
                with self.db.session_scope() as session:
                    progress = self.db.get_sync_progress(session, self.sync_type)
                    self.db.update_sync_progress(
                        session,
                        self.sync_type,
                        status='error',
                        error_count=progress.error_count + 1,
                        last_error=str(e)
                    )
                
                # Decide whether to continue
                with self.db.session_scope() as session:
                    progress = self.db.get_sync_progress(session, self.sync_type)
                    if progress.error_count >= 3:
                        logger.error("Too many errors, stopping sync")
                        return False
                
                logger.warning("Continuing with next chunk...")
                continue
        
        # Mark as completed
        with self.db.session_scope() as session:
            self.db.update_sync_progress(
                session,
                self.sync_type,
                status='completed'
            )
        
        # Final statistics
        total_time = time.time() - start_time
        logger.success(f"\nSync complete! Added {total_added:,} tracks in {total_time/60:.1f} minutes")
        
        # Show final database stats
        with self.db.session_scope() as session:
            from src.core.models import Track, Artist
            
            total_tracks = session.query(Track).count()
            total_plays = session.query(PlayHistory).count()
            total_artists = session.query(Artist).count()
            lastfm_plays = session.query(PlayHistory).filter_by(source='lastfm').count()
            
            progress = self.db.get_sync_progress(session, self.sync_type)
            
            logger.info(f"\nFinal database statistics:")
            logger.info(f"  Total unique tracks: {total_tracks:,}")
            logger.info(f"  Total plays: {total_plays:,}")
            logger.info(f"  Total artists: {total_artists:,}")
            logger.info(f"  Last.fm plays: {lastfm_plays:,}")
            logger.info(f"  Sync rate: {total_added/total_time:.1f} tracks/second")
            logger.info(f"  API calls made: {progress.api_calls_made:,}")
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Complete Last.fm history sync')
    parser.add_argument('--reset', action='store_true', help='Reset sync progress and start fresh')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    args = parser.parse_args()
    
    # Setup logging
    logger.remove()
    level = "DEBUG" if args.verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )
    
    # Initialize components
    lastfm = LastFMClient()
    db = DatabaseManager()
    
    # Run sync
    sync_manager = CompleteSyncManager(lastfm, db)
    success = sync_manager.run_sync(force_reset=args.reset)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())