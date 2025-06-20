from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from loguru import logger

from ..services.sync_service import SyncService
from ..services.playlist_service import PlaylistService
from ..core.config import get_config


class TaskScheduler:
    def __init__(self):
        self.config = get_config()
        self.sync_service = SyncService()
        self.playlist_service = PlaylistService()
        
        # Configure scheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(2)
        }
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300  # 5 minutes
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        # Add event listeners
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
    def _job_executed(self, event):
        """Log successful job execution"""
        logger.info(f"Job {event.job_id} executed successfully at {event.scheduled_run_time}")
        
    def _job_error(self, event):
        """Log job errors"""
        logger.error(f"Job {event.job_id} crashed: {event.exception}")
        
    def sync_listening_history(self):
        """Task to sync listening history from all sources"""
        logger.info("Starting listening history sync")
        try:
            results = self.sync_service.sync_all()
            
            # Log results
            for source, result in results.items():
                if result['success']:
                    logger.info(f"{source} sync successful: {result['tracks_synced']} new tracks")
                else:
                    logger.error(f"{source} sync failed: {result['error']}")
                    
        except Exception as e:
            logger.error(f"Sync task failed: {e}")
            raise
            
    def update_playlists(self):
        """Task to update all playlists"""
        logger.info("Starting playlist updates")
        try:
            # First, try to update any missing Spotify IDs
            updated_ids = self.sync_service.sync_spotify_ids(limit=50)
            if updated_ids:
                logger.info(f"Updated {updated_ids} tracks with Spotify IDs")
            
            # Update playlists
            results = self.playlist_service.update_all_playlists()
            
            # Log results
            for playlist_type, success in results.items():
                if success:
                    logger.info(f"{playlist_type} playlist updated successfully")
                else:
                    logger.error(f"{playlist_type} playlist update failed")
                    
        except Exception as e:
            logger.error(f"Playlist update task failed: {e}")
            raise
            
    def daily_maintenance(self):
        """Daily maintenance tasks"""
        logger.info("Running daily maintenance")
        try:
            # Database cleanup could go here
            # Backup could go here
            logger.info("Daily maintenance completed")
        except Exception as e:
            logger.error(f"Daily maintenance failed: {e}")
            raise
            
    def start(self):
        """Start the scheduler with configured jobs"""
        # Schedule sync job
        sync_interval = self.config.sync.interval_minutes
        self.scheduler.add_job(
            func=self.sync_listening_history,
            trigger='interval',
            minutes=sync_interval,
            id='sync_history',
            name='Sync listening history',
            replace_existing=True
        )
        
        # Schedule playlist update job (offset by 1 minute to avoid conflicts)
        next_minute = datetime.now() + timedelta(minutes=1)
        self.scheduler.add_job(
            func=self.update_playlists,
            trigger='interval',
            minutes=sync_interval,
            id='update_playlists',
            name='Update playlists',
            replace_existing=True,
            next_run_time=next_minute.replace(second=0, microsecond=0)
        )
        
        # Schedule daily maintenance
        self.scheduler.add_job(
            func=self.daily_maintenance,
            trigger='cron',
            hour=3,  # Run at 3 AM
            minute=0,
            id='daily_maintenance',
            name='Daily maintenance',
            replace_existing=True
        )
        
        # Start scheduler
        self.scheduler.start()
        logger.info(f"Scheduler started with sync interval of {sync_interval} minutes")
        
        # Run initial sync
        logger.info("Running initial sync")
        self.sync_listening_history()
        self.update_playlists()
        
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
        
    def get_jobs(self):
        """Get information about scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time,
                'trigger': str(job.trigger)
            })
        return jobs
        
    def trigger_sync(self):
        """Manually trigger a sync"""
        logger.info("Manual sync triggered")
        self.sync_listening_history()
        self.update_playlists()
        
    def pause_job(self, job_id: str):
        """Pause a specific job"""
        self.scheduler.pause_job(job_id)
        logger.info(f"Job {job_id} paused")
        
    def resume_job(self, job_id: str):
        """Resume a specific job"""
        self.scheduler.resume_job(job_id)
        logger.info(f"Job {job_id} resumed")