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
        """Main home page with navigation"""
        return render_template('home.html')
    
    @app.route('/wrapped')
    def wrapped():
        """Year in review wrapped view"""
        current_year = datetime.now().year
        return render_template('wrapped.html', year=current_year)
    
    @app.route('/explore')
    def explore():
        """Interactive exploration view"""
        return render_template('explore.html')
    
    @app.route('/genre-galaxy')
    def genre_galaxy():
        """Genre Galaxy 3D visualization"""
        return render_template('genre_galaxy.html')
    
    @app.route('/mood-spectrum')
    def mood_spectrum():
        """Mood Spectrum Analyzer visualization"""
        return render_template('mood_spectrum.html')
    
    @app.route('/discovery-network')
    def discovery_network():
        """Discovery Network Graph visualization"""
        return render_template('discovery_network.html')
    
    @app.route('/diversity-index')
    def diversity_index():
        """Musical Diversity Index visualization"""
        return render_template('diversity_index.html')
    
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
    
    # New advanced visualizations
    @app.route('/api/visualizations/genre-galaxy')
    def get_genre_galaxy():
        """Get 3D genre galaxy data"""
        try:
            from analytics.genre_mapper import GenreMapper
            
            mapper = GenreMapper()
            user_id = request.args.get('user_id', type=int)
            
            galaxy_data = mapper.get_genre_positions(user_id)
            return jsonify(galaxy_data)
            
        except Exception as e:
            logger.error(f"Error creating genre galaxy: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/genre-journey')
    def get_genre_journey():
        """Get user's journey through genres"""
        try:
            from analytics.genre_mapper import GenreMapper
            
            mapper = GenreMapper()
            user_id = request.args.get('user_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            journey = mapper.get_user_journey(user_id, start_date, end_date)
            return jsonify({'journey': journey})
            
        except Exception as e:
            logger.error(f"Error getting genre journey: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Mood analysis endpoints
    @app.route('/api/visualizations/mood-timeline')
    def get_mood_timeline():
        """Get mood changes over time"""
        try:
            from analytics.mood_analyzer import MoodAnalyzer
            
            analyzer = MoodAnalyzer()
            user_id = request.args.get('user_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if start_date:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            timeline = analyzer.get_mood_timeline(user_id, start_date, end_date)
            return jsonify({'timeline': timeline})
            
        except Exception as e:
            logger.error(f"Error creating mood timeline: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/mood-patterns')
    def get_mood_patterns():
        """Get mood patterns by time"""
        try:
            from analytics.mood_analyzer import MoodAnalyzer
            
            analyzer = MoodAnalyzer()
            user_id = request.args.get('user_id', type=int)
            
            patterns = analyzer.get_mood_patterns(user_id)
            return jsonify(patterns)
            
        except Exception as e:
            logger.error(f"Error analyzing mood patterns: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/insights/mood-analysis')
    def get_mood_analysis():
        """Get mood summary and insights"""
        try:
            from analytics.mood_analyzer import MoodAnalyzer
            
            analyzer = MoodAnalyzer()
            user_id = request.args.get('user_id', type=int)
            days = request.args.get('days', 30, type=int)
            
            summary = analyzer.get_mood_summary(user_id, days)
            return jsonify(summary)
            
        except Exception as e:
            logger.error(f"Error analyzing mood: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Discovery network endpoints
    @app.route('/api/visualizations/discovery-network')
    def get_discovery_network():
        """Get artist discovery network data"""
        try:
            from analytics.discovery_tracker import DiscoveryTracker
            
            tracker = DiscoveryTracker()
            user_id = request.args.get('user_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if start_date:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            
            network = tracker.build_discovery_network(user_id, start_date, end_date)
            return jsonify(network)
            
        except Exception as e:
            logger.error(f"Error building discovery network: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/discovery-path/<artist1>/<artist2>')
    def get_discovery_path(artist1, artist2):
        """Get discovery path between two artists"""
        try:
            from analytics.discovery_tracker import DiscoveryTracker
            
            tracker = DiscoveryTracker()
            user_id = request.args.get('user_id', type=int)
            
            path = tracker.get_artist_discovery_path(artist1, artist2, user_id)
            if path:
                return jsonify({'path': path})
            else:
                return jsonify({'error': 'No path found between artists'}), 404
                
        except Exception as e:
            logger.error(f"Error finding discovery path: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Musical diversity endpoints
    @app.route('/api/visualizations/genre-portfolio')
    def get_genre_portfolio():
        """Get musical diversity portfolio data"""
        try:
            from analytics.diversity_metrics import DiversityMetrics
            
            metrics = DiversityMetrics()
            user_id = request.args.get('user_id', type=int)
            days = request.args.get('days', 30, type=int)
            
            portfolio_data = metrics.calculate_portfolio_metrics(user_id, days)
            return jsonify(portfolio_data)
            
        except Exception as e:
            logger.error(f"Error calculating portfolio: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/genre-performance')
    def get_genre_performance():
        """Get historical genre performance data"""
        try:
            from analytics.diversity_metrics import DiversityMetrics
            
            metrics = DiversityMetrics()
            user_id = request.args.get('user_id', type=int)
            days = request.args.get('days', 90, type=int)
            
            # Get extended historical data
            portfolio_data = metrics.calculate_portfolio_metrics(user_id, days)
            
            # Format for time series visualization
            performance_data = {
                'historical': portfolio_data['historical_performance'],
                'current': portfolio_data['portfolio'],
                'volatility': portfolio_data['risk_metrics']['genre_volatilities']
            }
            
            return jsonify(performance_data)
            
        except Exception as e:
            logger.error(f"Error getting performance data: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Weather correlation endpoints
    @app.route('/weather-correlation')
    def weather_correlation():
        """Weather-Music Correlation visualization page"""
        return render_template('weather_correlation.html')
    
    @app.route('/api/visualizations/weather-correlation')
    def get_weather_correlation():
        """Get weather-music correlation data"""
        try:
            from analytics.weather_correlation import WeatherMusicCorrelation
            
            analyzer = WeatherMusicCorrelation()
            user_id = request.args.get('user_id', type=int)
            days = request.args.get('days', 90, type=int)
            lat = request.args.get('lat', type=float)
            lon = request.args.get('lon', type=float)
            
            # Get location if not provided
            location = (lat, lon) if lat and lon else None
            
            correlation_data = analyzer.analyze_weather_correlations(
                user_id=user_id,
                days=days,
                location=location
            )
            
            return jsonify(correlation_data)
            
        except Exception as e:
            logger.error(f"Error analyzing weather correlation: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/weather-patterns')
    def get_weather_patterns():
        """Get weather-based music patterns"""
        try:
            from analytics.weather_correlation import WeatherMusicCorrelation
            
            analyzer = WeatherMusicCorrelation()
            user_id = request.args.get('user_id', type=int)
            days = request.args.get('days', 90, type=int)
            
            correlation_data = analyzer.analyze_weather_correlations(user_id, days)
            
            # Return just the patterns for visualization
            return jsonify({
                'patterns': correlation_data['patterns'],
                'summary': correlation_data['weather_summary']
            })
            
        except Exception as e:
            logger.error(f"Error getting weather patterns: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/weather/current-predictions')
    def get_current_predictions():
        """Get music predictions based on current weather"""
        try:
            from analytics.weather_correlation import WeatherMusicCorrelation
            
            analyzer = WeatherMusicCorrelation()
            user_id = request.args.get('user_id', type=int)
            lat = request.args.get('lat', type=float)
            lon = request.args.get('lon', type=float)
            
            location = (lat, lon) if lat and lon else None
            
            # Get full analysis
            data = analyzer.analyze_weather_correlations(user_id, location=location)
            
            return jsonify({
                'predictions': data['predictions'],
                'current_weather': {
                    'category': data['predictions']['weather'],
                    'temperature': data['predictions']['temperature'],
                    'description': data['predictions']['description']
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting predictions: {e}")
            return jsonify({'error': str(e)}), 500
    
    # New analytics endpoints from Jupyter notebook
    @app.route('/api/analytics/artist/<artist_name>/songs')
    def get_artist_songs(artist_name):
        """Get most played songs by a specific artist"""
        try:
            limit = request.args.get('limit', 25, type=int)
            songs = app.analytics.get_songs_by_artist(artist_name, limit=limit)
            return jsonify({'artist': artist_name, 'songs': songs})
        except Exception as e:
            logger.error(f"Error getting artist songs: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/analytics/binged-songs')
    def get_binged_songs():
        """Get songs that were binged (played multiple times in a day)"""
        try:
            limit = request.args.get('limit', 25, type=int)
            min_plays = request.args.get('min_plays', 3, type=int)
            songs = app.analytics.get_binged_songs(limit=limit, min_daily_plays=min_plays)
            return jsonify({'binged_songs': songs})
        except Exception as e:
            logger.error(f"Error getting binged songs: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/analytics/recent-favorites')
    def get_recent_favorites():
        """Get most played songs in recent time period"""
        try:
            days = request.args.get('days', 30, type=int)
            limit = request.args.get('limit', 50, type=int)
            songs = app.analytics.get_recent_favorites(days=days, limit=limit)
            return jsonify({'recent_favorites': songs, 'days': days})
        except Exception as e:
            logger.error(f"Error getting recent favorites: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/analytics/dow-patterns')
    def get_dow_patterns():
        """Get play counts by day of week"""
        try:
            days = request.args.get('days', type=int)
            patterns = app.analytics.get_play_counts_by_dow(days=days)
            return jsonify({'dow_patterns': patterns})
        except Exception as e:
            logger.error(f"Error getting DOW patterns: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/analytics/consistent-artists')
    def get_consistent_artists():
        """Get artists with most days of listening"""
        try:
            limit = request.args.get('limit', 30, type=int)
            artists = app.analytics.get_artist_listening_consistency(limit=limit)
            return jsonify({'consistent_artists': artists})
        except Exception as e:
            logger.error(f"Error getting consistent artists: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/visualizations/artist-calendar/<artist_name>')
    def get_artist_calendar(artist_name):
        """Get calendar heatmap for a specific artist"""
        try:
            year = request.args.get('year', type=int)
            data = app.analytics.get_listening_calendar_data(year=year, artist_filter=artist_name)
            
            if data.empty:
                return jsonify({'error': 'No data for artist'}), 404
            
            # Use enhanced calendar visualization
            fig = app.enhanced_viz.create_github_style_calendar(data, year or datetime.now().year)
            return jsonify({'chart': app.enhanced_viz.to_json(fig), 'artist': artist_name})
        except Exception as e:
            logger.error(f"Error creating artist calendar: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/analytics/artist/<artist_name>/peak-month')
    def get_artist_peak_month(artist_name):
        """Get peak listening month for an artist"""
        try:
            result = app.patterns.get_peak_month_by_artist(artist_name)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error getting artist peak month: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/analytics/binge-patterns')
    def get_binge_patterns():
        """Get overall binge listening patterns"""
        try:
            min_plays = request.args.get('min_plays', 3, type=int)
            patterns = app.patterns.analyze_binge_patterns(min_plays_per_day=min_plays)
            return jsonify(patterns)
        except Exception as e:
            logger.error(f"Error analyzing binge patterns: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Artist analysis page
    @app.route('/artist-analysis')
    def artist_analysis():
        """Artist-specific analysis page"""
        return render_template('artist_analysis.html')