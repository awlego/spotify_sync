"""
Minimal Flask app for sync service monitoring
"""
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from loguru import logger
import os
import sys

# Add parent directory to path for imports
sync_service_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, sync_service_root)

from services.sync_service import SyncService
from services.playlist_service import PlaylistService
from scheduler.tasks import TaskScheduler
from api.spotify_client import SpotifyClient
from config import get_config


def create_app():
    """Create and configure the Flask app"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24)
    CORS(app)
    
    # Initialize services
    config = get_config()
    app.sync_service = SyncService()
    app.playlist_service = PlaylistService()
    app.spotify_client = SpotifyClient()
    app.scheduler = TaskScheduler(app)
    
    # Register routes
    register_routes(app)
    
    # Start scheduler unless disabled
    if not app.config.get('SCHEDULER_DISABLED'):
        app.scheduler.start()
        logger.info("Scheduler started")
    
    return app


def register_routes(app):
    """Register monitoring routes"""
    
    @app.route('/')
    def index():
        """Monitoring dashboard"""
        return render_template('monitor.html')
    
    @app.route('/api/status')
    def api_status():
        """Get sync status"""
        sync_status = app.sync_service.get_sync_status()
        playlist_stats = app.playlist_service.get_playlist_stats()
        
        return jsonify({
            'sync_status': sync_status,
            'playlist_stats': playlist_stats,
            'spotify_authenticated': app.spotify_client.ensure_authenticated()
        })
    
    @app.route('/api/sync/trigger', methods=['POST'])
    def trigger_sync():
        """Manually trigger sync"""
        try:
            result = app.sync_service.sync_all()
            return jsonify({'success': True, 'result': result})
        except Exception as e:
            logger.error(f"Manual sync failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/playlists/update/<playlist_type>', methods=['POST'])
    def update_playlist(playlist_type):
        """Manually update a playlist"""
        try:
            result = app.playlist_service.update_playlist(playlist_type)
            return jsonify({'success': True, 'result': result})
        except Exception as e:
            logger.error(f"Playlist update failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/auth/spotify')
    def spotify_auth():
        """Redirect to Spotify auth"""
        from flask import redirect
        auth_url = app.spotify_client.get_auth_url()
        return redirect(auth_url)
    
    @app.route('/callback')
    def spotify_callback():
        """Handle Spotify OAuth callback"""
        from flask import request, redirect, url_for
        code = request.args.get('code')
        if code:
            success = app.spotify_client.process_auth_code(code)
            if success:
                return redirect(url_for('index', auth='success'))
        return redirect(url_for('index', auth='failed'))