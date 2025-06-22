"""
Flask app for Spotify Wrapped-style analytics service
"""
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from loguru import logger
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.core import AnalyticsService
from analytics.patterns import PatternAnalyzer
from visualizations.charts import VisualizationFramework
from config import get_config


def create_app():
    """Create and configure the Flask app"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24)
    CORS(app)
    
    # Initialize services
    config = get_config()
    app.analytics = AnalyticsService()
    app.patterns = PatternAnalyzer()
    app.visualizations = VisualizationFramework()
    
    # Register routes
    register_routes(app)
    
    return app


def register_routes(app):
    """Register wrapped service routes"""
    
    @app.route('/')
    def index():
        """Main wrapped view"""
        current_year = datetime.now().year
        return render_template('wrapped.html', year=current_year)
    
    @app.route('/explore')
    def explore():
        """Interactive exploration view"""
        return render_template('explore.html')
    
    # Analytics API endpoints
    @app.route('/api/wrapped/<int:year>')
    def get_wrapped_data(year):
        """Get complete wrapped data for a year"""
        try:
            # Get all analytics data
            top_tracks = app.analytics.get_top_tracks_by_period(days=365, limit=10)
            top_artists = app.analytics.get_top_artists_by_period(days=365, limit=10)
            
            # Get patterns
            personality = app.patterns.get_listening_personality()
            streaks = app.patterns.get_listening_streaks()
            discoveries = app.patterns.get_discovery_timeline(year)
            peak_periods = app.patterns.get_peak_listening_periods()
            binge_sessions = app.patterns.get_binge_sessions()
            
            # Get calendar data
            calendar_data = app.analytics.get_listening_calendar_data(year)
            
            # Calculate statistics
            total_minutes = app.analytics.get_total_listening_time(year)
            unique_tracks = app.analytics.get_unique_track_count(year)
            unique_artists = app.analytics.get_unique_artist_count(year)
            
            return jsonify({
                'year': year,
                'stats': {
                    'total_minutes': total_minutes,
                    'unique_tracks': unique_tracks,
                    'unique_artists': unique_artists,
                    'top_tracks': top_tracks,
                    'top_artists': top_artists
                },
                'personality': personality,
                'patterns': {
                    'streaks': streaks[:3],  # Top 3 streaks
                    'peak_periods': peak_periods,
                    'discoveries': discoveries[:10],  # Top 10 discoveries
                    'binge_sessions': binge_sessions[:5]  # Top 5 sessions
                },
                'calendar_data': calendar_data.to_dict() if not calendar_data.empty else {}
            })
        except Exception as e:
            logger.error(f"Error generating wrapped data: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/calendar/<int:year>')
    def get_calendar_viz(year):
        """Get calendar heatmap visualization"""
        try:
            data = app.analytics.get_listening_calendar_data(year)
            if data.empty:
                return jsonify({'error': 'No data for year'}), 404
            
            # Convert to list of dicts for visualization
            viz_data = []
            for date, plays in data.iterrows():
                viz_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'plays': int(plays['plays'])
                })
            
            fig = app.visualizations.create_calendar_heatmap(viz_data, year)
            return jsonify({'chart': app.visualizations.to_json(fig)})
        except Exception as e:
            logger.error(f"Error creating calendar visualization: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/top-tracks/<int:year>')
    def get_top_tracks_viz(year):
        """Get top tracks bar chart"""
        try:
            days = 365 if year else 30
            tracks = app.analytics.get_top_tracks_by_period(days=days, limit=20)
            fig = app.visualizations.create_top_items_bar_chart(tracks, 'tracks')
            return jsonify({'chart': app.visualizations.to_json(fig)})
        except Exception as e:
            logger.error(f"Error creating tracks visualization: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/insights/listening-personality')
    def get_personality():
        """Get listening personality analysis"""
        try:
            personality = app.patterns.get_listening_personality()
            return jsonify(personality)
        except Exception as e:
            logger.error(f"Error analyzing personality: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/insights/peak-times')
    def get_peak_times():
        """Get peak listening times"""
        try:
            peaks = app.patterns.get_peak_listening_periods()
            return jsonify(peaks)
        except Exception as e:
            logger.error(f"Error analyzing peak times: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/insights/discoveries/<int:year>')
    def get_discoveries(year):
        """Get artist discovery timeline"""
        try:
            discoveries = app.patterns.get_discovery_timeline(year)
            return jsonify({'discoveries': discoveries[:20]})  # Top 20
        except Exception as e:
            logger.error(f"Error getting discoveries: {e}")
            return jsonify({'error': str(e)}), 500