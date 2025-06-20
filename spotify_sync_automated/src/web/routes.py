from flask import render_template, jsonify, request, redirect, url_for, current_app
from datetime import datetime, timedelta
from loguru import logger


def register_routes(app):
    """Register all routes for the application"""
    
    # Main dashboard
    @app.route('/')
    def index():
        """Main dashboard view"""
        return render_template('index.html')
    
    # Spotify OAuth endpoints
    @app.route('/auth/spotify')
    def spotify_auth():
        """Redirect to Spotify authorization"""
        auth_url = current_app.spotify_client.get_auth_url()
        return redirect(auth_url)
    
    @app.route('/callback')
    def spotify_callback():
        """Handle Spotify OAuth callback"""
        code = request.args.get('code')
        if code:
            success = current_app.spotify_client.process_auth_code(code)
            if success:
                return redirect(url_for('index', auth='success'))
        return redirect(url_for('index', auth='failed'))
    
    # API endpoints
    @app.route('/api/status')
    def api_status():
        """Get current system status"""
        sync_status = current_app.sync_service.get_sync_status()
        scheduler_jobs = current_app.scheduler.get_jobs()
        playlist_stats = current_app.playlist_service.get_playlist_stats()
        
        return jsonify({
            'sync_status': sync_status,
            'scheduler_jobs': scheduler_jobs,
            'playlist_stats': playlist_stats,
            'spotify_authenticated': current_app.spotify_client.ensure_authenticated()
        })
    
    @app.route('/api/sync/trigger', methods=['POST'])
    def trigger_sync():
        """Manually trigger a sync"""
        try:
            current_app.scheduler.trigger_sync()
            return jsonify({'success': True, 'message': 'Sync triggered successfully'})
        except Exception as e:
            logger.error(f"Manual sync failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/analytics/top-tracks')
    def api_top_tracks():
        """Get top tracks for a time period"""
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        tracks = current_app.analytics_service.get_top_tracks_by_period(days, limit)
        return jsonify(tracks)
    
    @app.route('/api/analytics/top-artists')
    def api_top_artists():
        """Get top artists for a time period"""
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 30, type=int)
        
        artists = current_app.analytics_service.get_top_artists_by_period(days, limit)
        return jsonify(artists)
    
    @app.route('/api/analytics/listening-patterns')
    def api_listening_patterns():
        """Get listening patterns (by hour and weekday)"""
        days = request.args.get('days', 30, type=int)
        
        hourly = current_app.analytics_service.get_listening_stats_by_hour(days)
        weekday = current_app.analytics_service.get_listening_stats_by_weekday(days)
        
        return jsonify({
            'hourly': hourly,
            'weekday': weekday
        })
    
    @app.route('/api/analytics/calendar')
    def api_calendar_data():
        """Get calendar heatmap data"""
        year = request.args.get('year', datetime.now().year, type=int)
        artist = request.args.get('artist', None)
        
        df = current_app.analytics_service.get_listening_calendar_data(year, artist)
        
        # Convert DataFrame to list of dicts for JSON
        data = []
        for date, row in df.iterrows():
            data.append({
                'date': date.isoformat(),
                'plays': int(row['plays'])
            })
        
        return jsonify(data)
    
    @app.route('/api/analytics/yearly-stats/<int:year>')
    def api_yearly_stats(year):
        """Get comprehensive yearly statistics"""
        stats = current_app.analytics_service.get_yearly_stats(year)
        return jsonify(stats)
    
    @app.route('/api/analytics/diversity')
    def api_diversity_score():
        """Get listening diversity metrics"""
        days = request.args.get('days', 30, type=int)
        diversity = current_app.analytics_service.get_listening_diversity_score(days)
        return jsonify(diversity)
    
    @app.route('/api/analytics/discovery')
    def api_music_discovery():
        """Get music discovery timeline"""
        days = request.args.get('days', 90, type=int)
        discoveries = current_app.analytics_service.get_music_discovery_timeline(days)
        return jsonify(discoveries)
    
    @app.route('/api/analytics/artist/<artist_name>/peaks')
    def api_artist_peaks(artist_name):
        """Get peak listening periods for an artist"""
        peaks = current_app.analytics_service.get_peak_listening_periods(artist_name)
        return jsonify(peaks)
    
    @app.route('/api/playlists/candidates/<playlist_type>')
    def api_playlist_candidates(playlist_type):
        """Get candidate tracks for a playlist"""
        limit = request.args.get('limit', 50, type=int)
        candidates = current_app.playlist_service.get_playlist_candidates(playlist_type, limit)
        return jsonify(candidates)
    
    @app.route('/api/playlists/update/<playlist_type>', methods=['POST'])
    def api_update_playlist(playlist_type):
        """Manually update a specific playlist"""
        try:
            if playlist_type == 'most_listened':
                success = current_app.playlist_service.update_most_listened_playlist()
            elif playlist_type == 'recent_favorites':
                success = current_app.playlist_service.update_recent_favorites_playlist()
            elif playlist_type == 'binged_songs':
                success = current_app.playlist_service.update_binged_songs_playlist()
            else:
                return jsonify({'success': False, 'error': 'Invalid playlist type'}), 400
            
            return jsonify({'success': success})
        except Exception as e:
            logger.error(f"Playlist update failed: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/tracks/missing-ids')
    def api_missing_spotify_ids():
        """Get tracks missing Spotify IDs"""
        limit = request.args.get('limit', 100, type=int)
        tracks = current_app.playlist_service.find_tracks_without_spotify_ids(limit)
        return jsonify(tracks)
    
    # Visualization pages
    @app.route('/visualizations')
    def visualizations():
        """Visualization dashboard"""
        return render_template('visualizations.html')
    
    @app.route('/wrapped/<int:year>')
    def wrapped(year):
        """Spotify Wrapped-style yearly summary"""
        stats = current_app.analytics_service.get_yearly_stats(year)
        return render_template('wrapped.html', year=year, stats=stats)