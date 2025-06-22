"""
Flask app for Spotify Wrapped-style analytics service
"""
from flask import Flask, render_template, jsonify, request
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
from visualizations.enhanced_charts import EnhancedVisualizations
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
    app.enhanced_viz = EnhancedVisualizations()
    
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
            try:
                logger.debug("Getting top tracks...")
                top_tracks = app.analytics.get_top_tracks_by_period(days=365, limit=10)
            except Exception as e:
                logger.error(f"Error in get_top_tracks_by_period: {e}")
                raise
                
            try:
                logger.debug("Getting top artists...")
                top_artists = app.analytics.get_top_artists_by_period(days=365, limit=10)
            except Exception as e:
                logger.error(f"Error in get_top_artists_by_period: {e}")
                raise
            
            # Get patterns
            try:
                personality = app.patterns.get_listening_personality()
                streaks = app.patterns.get_listening_streaks()
                discoveries = app.patterns.get_discovery_timeline(year)
                peak_periods = app.patterns.get_peak_listening_periods()
                binge_sessions = app.patterns.get_binge_sessions()
            except Exception as e:
                logger.error(f"Error in patterns methods: {e}")
                raise
            
            # Get calendar data
            logger.debug("Getting calendar data...")
            calendar_data = app.analytics.get_listening_calendar_data(year=year)
            
            # Calculate statistics
            logger.debug("Getting total listening time...")
            total_minutes = app.analytics.get_total_listening_time(year=year)
            logger.debug("Getting unique track count...")
            unique_tracks = app.analytics.get_unique_track_count(year=year)
            logger.debug("Getting unique artist count...")
            unique_artists = app.analytics.get_unique_artist_count(year=year)
            
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
            import traceback
            logger.error(f"Error generating wrapped data: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500
    
    @app.route('/api/visualizations/calendar/<int:year>')
    def get_calendar_viz_year(year):
        """Get calendar heatmap visualization for a year"""
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
    
    @app.route('/api/visualizations/calendar')
    def get_calendar_viz():
        """Get calendar heatmap visualization for flexible date ranges"""
        try:
            from datetime import datetime, timedelta
            
            period = request.args.get('period', 'year')
            
            if period == 'all':
                # For all time, show the current year
                year = datetime.now().year
                data = app.analytics.get_listening_calendar_data(year)
            elif period == 'year':
                year = int(request.args.get('year', datetime.now().year))
                data = app.analytics.get_listening_calendar_data(year)
            else:
                # For other periods, use current year calendar with highlighting
                year = datetime.now().year
                data = app.analytics.get_listening_calendar_data(year)
            
            if data.empty:
                return jsonify({'error': 'No data available'}), 404
            
            # Use enhanced calendar visualization
            fig = app.enhanced_viz.create_github_style_calendar(data, year)
            return jsonify({'chart': app.enhanced_viz.to_json(fig)})
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
    
    # Enhanced visualization endpoints
    @app.route('/api/analytics/data/<int:year>')
    def get_analytics_data_year(year):
        """Get comprehensive analytics data for a year"""
        try:
            stats = {
                'total_plays': app.analytics.get_total_listening_time(year) // 3,  # Approx plays
                'unique_tracks': app.analytics.get_unique_track_count(year),
                'unique_artists': app.analytics.get_unique_artist_count(year),
                'total_minutes': app.analytics.get_total_listening_time(year)
            }
            return jsonify({'stats': stats, 'year': year})
        except Exception as e:
            logger.error(f"Error getting analytics data: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/analytics/data')
    def get_analytics_data():
        """Get analytics data for flexible time ranges"""
        try:
            from datetime import datetime, timedelta
            
            period = request.args.get('period', 'all')
            start_date = None
            end_date = None
            
            if period == 'all':
                # All time stats
                pass
            elif period == 'year':
                year = int(request.args.get('year', datetime.now().year))
                start_date = datetime(year, 1, 1)
                end_date = datetime(year + 1, 1, 1)
            elif period == 'days':
                days = int(request.args.get('days', 30))
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
            elif period == 'custom':
                start_date = datetime.fromisoformat(request.args.get('start_date'))
                end_date = datetime.fromisoformat(request.args.get('end_date'))
            
            # Get stats for the period
            stats = app.analytics.get_stats_for_period(start_date, end_date)
            
            return jsonify({
                'stats': stats,
                'period': period,
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            })
        except Exception as e:
            logger.error(f"Error getting analytics data: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/listening-clock')
    def get_listening_clock():
        """Get hourly listening pattern visualization"""
        try:
            # Get time period from request
            period = request.args.get('period', 'days')
            
            if period == 'all':
                # All time - use larger window
                days = 365 * 10  # 10 years
            elif period == 'year':
                days = 365
            elif period == 'days':
                days = int(request.args.get('days', 30))
            else:
                days = 30
            
            hourly_data = app.analytics.get_listening_stats_by_hour(days=days)
            title = "Listening Clock" if period == 'all' else f"Listening Clock (Last {days} Days)"
            fig = app.enhanced_viz.create_radial_chart(hourly_data, title)
            return jsonify({'chart': app.enhanced_viz.to_json(fig)})
        except Exception as e:
            logger.error(f"Error creating listening clock: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/weekly-patterns')
    def get_weekly_patterns():
        """Get weekly listening patterns heatmap"""
        try:
            # Get raw play history data and process it
            from shared import DatabaseManager, PlayHistory
            import pandas as pd
            
            db = DatabaseManager()
            with db.session_scope() as session:
                plays = session.query(PlayHistory).all()
                
                # Create DataFrame
                data = []
                for play in plays:
                    data.append({
                        'datetime': play.played_at,
                        'plays': 1
                    })
                
                df = pd.DataFrame(data)
                if not df.empty:
                    df['hour'] = df['datetime'].dt.hour
                    df['dayofweek'] = df['datetime'].dt.dayofweek
                    
                    # Group by day and hour
                    grouped = df.groupby(['dayofweek', 'hour'])['plays'].sum()
                    
                    fig = app.enhanced_viz.create_listening_heatmap(grouped)
                    return jsonify({'chart': app.enhanced_viz.to_json(fig)})
                else:
                    return jsonify({'error': 'No data available'}), 404
                    
        except Exception as e:
            logger.error(f"Error creating weekly patterns: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/artist-trends')
    def get_artist_trends():
        """Get artist listening trends stream graph"""
        try:
            from shared import DatabaseManager, PlayHistory
            import pandas as pd
            
            db = DatabaseManager()
            with db.session_scope() as session:
                plays = session.query(PlayHistory).all()
                
                # Create DataFrame with artist info
                data = []
                for play in plays:
                    data.append({
                        'date': play.played_at,
                        'artist': play.track.artist.name
                    })
                
                df = pd.DataFrame(data)
                if not df.empty:
                    fig = app.enhanced_viz.create_stream_graph(df)
                    return jsonify({'chart': app.enhanced_viz.to_json(fig)})
                else:
                    return jsonify({'error': 'No data available'}), 404
                    
        except Exception as e:
            logger.error(f"Error creating artist trends: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/music-hierarchy')
    def get_music_hierarchy():
        """Get music hierarchy sunburst chart"""
        try:
            # Get top tracks with hierarchy info
            top_tracks = app.analytics.get_top_tracks_by_period(days=365, limit=100)
            
            if top_tracks:
                fig = app.enhanced_viz.create_sunburst_chart(top_tracks)
                return jsonify({'chart': app.enhanced_viz.to_json(fig)})
            else:
                return jsonify({'error': 'No data available'}), 404
                
        except Exception as e:
            logger.error(f"Error creating music hierarchy: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/timeline')
    def get_timeline():
        """Get animated listening timeline"""
        try:
            from shared import DatabaseManager, PlayHistory
            import pandas as pd
            
            db = DatabaseManager()
            with db.session_scope() as session:
                plays = session.query(PlayHistory).all()
                
                # Create DataFrame
                data = []
                for play in plays:
                    data.append({
                        'date': play.played_at,
                        'plays': 1
                    })
                
                df = pd.DataFrame(data)
                if not df.empty:
                    # Set date as index for grouping
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    
                    # Add unique track and artist counts
                    df['unique_tracks'] = 1  # Simplified for now
                    df['unique_artists'] = 1  # Simplified for now
                    
                    fig = app.enhanced_viz.create_animated_timeline(df)
                    return jsonify({'chart': app.enhanced_viz.to_json(fig)})
                else:
                    return jsonify({'error': 'No data available'}), 404
                    
        except Exception as e:
            logger.error(f"Error creating timeline: {e}")
            return jsonify({'error': str(e)}), 500