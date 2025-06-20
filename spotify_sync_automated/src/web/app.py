from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
from loguru import logger
import os

from ..api.spotify_client import SpotifyClient
from ..services.sync_service import SyncService
from ..services.playlist_service import PlaylistService
from ..services.analytics_service import AnalyticsService
from ..scheduler.tasks import TaskScheduler
from ..core.config import get_config


def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, 
                template_folder='../../templates',
                static_folder='../../static')
    
    # Enable CORS for API endpoints
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Configure app
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    
    # Initialize services
    config = get_config()
    spotify_client = SpotifyClient()
    sync_service = SyncService()
    playlist_service = PlaylistService()
    analytics_service = AnalyticsService()
    scheduler = TaskScheduler()
    
    # Store services in app context
    app.spotify_client = spotify_client
    app.sync_service = sync_service
    app.playlist_service = playlist_service
    app.analytics_service = analytics_service
    app.scheduler = scheduler
    
    # Import and register routes
    from .routes import register_routes
    register_routes(app)
    
    # Start scheduler when app context is ready
    with app.app_context():
        if not scheduler.scheduler.running and not app.config.get('SCHEDULER_DISABLED'):
            scheduler.start()
            logger.info("Scheduler started with Flask app")
    
    # Shutdown scheduler when app stops
    @app.teardown_appcontext
    def shutdown_scheduler(error=None):
        if hasattr(app, 'scheduler') and app.scheduler.scheduler.running:
            app.scheduler.stop()
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)