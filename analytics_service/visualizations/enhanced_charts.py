"""
Enhanced interactive visualizations for music listening data
"""
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import json
import plotly.utils
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import calendar


class EnhancedVisualizations:
    """Modern, interactive visualizations for music data"""
    
    def __init__(self):
        # Spotify-inspired color palette
        self.colors = {
            'primary': '#1DB954',      # Spotify green
            'secondary': '#191414',    # Spotify black
            'background': '#121212',   # Dark background
            'surface': '#282828',      # Card background
            'text_primary': '#FFFFFF',
            'text_secondary': '#B3B3B3',
            'accent': '#1ED760',       # Bright green
            'gradient_start': '#1DB954',
            'gradient_end': '#1ED760',
            'heat_colors': ['#121212', '#1DB954', '#1ED760', '#B8FF4F'],
            'chart_colors': [
                '#1DB954', '#1ED760', '#B8FF4F', '#FFF04F', 
                '#FF884F', '#FF4F4F', '#D14FFF', '#4F8FFF'
            ]
        }
        
        self.default_layout = {
            'template': 'plotly_dark',
            'font': {
                'family': 'Circular, Helvetica, Arial, sans-serif',
                'color': self.colors['text_primary']
            },
            'plot_bgcolor': self.colors['background'],
            'paper_bgcolor': self.colors['background'],
            'margin': {'l': 60, 'r': 60, 't': 80, 'b': 60},
            'hoverlabel': {
                'bgcolor': self.colors['surface'],
                'font_size': 14,
                'font_family': 'Circular, Helvetica, Arial, sans-serif'
            }
        }
    
    def create_github_style_calendar(self, data: pd.DataFrame, year: int) -> go.Figure:
        """Create a GitHub-style contribution calendar for listening activity"""
        # Create a full year calendar
        start_date = pd.Timestamp(f'{year}-01-01')
        end_date = pd.Timestamp(f'{year}-12-31')
        
        # Create date range
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Process data
        if not data.empty:
            data_dict = dict(zip(pd.to_datetime(data.index).date, data['plays']))
        else:
            data_dict = {}
        
        # Calculate positions for each day
        dates = []
        x_positions = []
        y_positions = []
        values = []
        hover_texts = []
        
        # Start from the first Sunday of the year
        first_day = start_date
        while first_day.weekday() != 6:  # Sunday
            first_day -= timedelta(days=1)
        
        current_date = first_day
        week = 0
        
        while current_date <= end_date:
            if current_date >= start_date:
                dates.append(current_date)
                x_positions.append(week)
                y_positions.append(6 - current_date.weekday())  # Invert for display
                
                plays = data_dict.get(current_date.date(), 0)
                values.append(plays)
                
                # Create hover text
                date_str = current_date.strftime('%b %d, %Y')
                hover_texts.append(f'{date_str}<br>{plays} plays')
            
            current_date += timedelta(days=1)
            if current_date.weekday() == 0:  # Monday
                week += 1
        
        # Create the heatmap
        fig = go.Figure()
        
        # Add the calendar heatmap
        fig.add_trace(go.Scatter(
            x=x_positions,
            y=y_positions,
            mode='markers',
            marker=dict(
                size=15,
                color=values,
                colorscale=[
                    [0, self.colors['surface']],
                    [0.25, self.colors['primary']],
                    [0.5, self.colors['accent']],
                    [0.75, '#B8FF4F'],
                    [1, '#FFF04F']
                ],
                showscale=True,
                colorbar=dict(
                    title="Plays",
                    titleside="right",
                    tickmode="linear",
                    tick0=0,
                    dtick=10,
                    thickness=15,
                    len=0.5,
                    x=1.02
                ),
                symbol='square'
            ),
            text=hover_texts,
            hovertemplate='%{text}<extra></extra>',
            showlegend=False
        ))
        
        # Add month labels
        month_positions = {}
        for i, date in enumerate(dates):
            month = date.month
            if month not in month_positions:
                month_positions[month] = x_positions[i]
        
        for month, x_pos in month_positions.items():
            fig.add_annotation(
                x=x_pos,
                y=7.5,
                text=calendar.month_abbr[month],
                showarrow=False,
                font=dict(size=12, color=self.colors['text_secondary'])
            )
        
        # Add day labels
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, day in enumerate(days):
            fig.add_annotation(
                x=-2,
                y=6-i,
                text=day,
                showarrow=False,
                font=dict(size=10, color=self.colors['text_secondary']),
                xanchor='right'
            )
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f'Your {year} Listening Activity',
                font=dict(size=24, color=self.colors['text_primary'])
            ),
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[-3, max(x_positions) + 1]
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                range=[-1, 8],
                autorange='reversed'
            ),
            **self.default_layout
        )
        
        return fig
    
    def create_radial_chart(self, data: Dict[str, int], title: str = "Listening Clock") -> go.Figure:
        """Create a radial/polar chart for hourly listening patterns"""
        # Prepare data
        hours = list(range(24))
        values = [data.get(h, 0) for h in hours]
        
        # Create labels
        labels = []
        for h in hours:
            if h == 0:
                labels.append('12 AM')
            elif h < 12:
                labels.append(f'{h} AM')
            elif h == 12:
                labels.append('12 PM')
            else:
                labels.append(f'{h-12} PM')
        
        # Add first value at end to close the circle
        values_plot = values + [values[0]]
        hours_plot = hours + [24]
        
        fig = go.Figure()
        
        # Add the radial line
        fig.add_trace(go.Scatterpolar(
            r=values_plot,
            theta=hours_plot,
            mode='lines+markers',
            name='Plays',
            line=dict(color=self.colors['primary'], width=3),
            marker=dict(size=8, color=self.colors['accent']),
            fill='toself',
            fillcolor='rgba(29, 185, 84, 0.25)',  # Add transparency
            hovertemplate='%{text}<br>%{r} plays<extra></extra>',
            text=[labels[i % 24] for i in range(25)]
        ))
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=20, color=self.colors['text_primary'])
            ),
            polar=dict(
                bgcolor=self.colors['surface'],
                radialaxis=dict(
                    visible=True,
                    showgrid=True,
                    gridcolor='rgba(179, 179, 179, 0.125)',
                    range=[0, max(values) * 1.1]
                ),
                angularaxis=dict(
                    direction='clockwise',
                    rotation=90,
                    tickmode='array',
                    tickvals=list(range(0, 24, 3)),
                    ticktext=[labels[i] for i in range(0, 24, 3)]
                )
            ),
            **self.default_layout
        )
        
        return fig
    
    def create_stream_graph(self, artist_data: pd.DataFrame, top_n: int = 10) -> go.Figure:
        """Create a stream graph showing artist popularity over time"""
        # Get top N artists by total plays
        top_artists = artist_data.groupby('artist').size().nlargest(top_n).index
        
        # Filter data for top artists
        filtered_data = artist_data[artist_data['artist'].isin(top_artists)]
        
        # Create pivot table
        pivot = filtered_data.groupby([pd.Grouper(key='date', freq='W'), 'artist']).size().reset_index(name='plays')
        pivot_wide = pivot.pivot(index='date', columns='artist', values='plays').fillna(0)
        
        # Create stream graph
        fig = go.Figure()
        
        # Add traces for each artist
        for i, artist in enumerate(pivot_wide.columns):
            fig.add_trace(go.Scatter(
                x=pivot_wide.index,
                y=pivot_wide[artist],
                name=artist,
                mode='lines',
                stackgroup='one',
                line=dict(width=0),
                fillcolor=self.colors['chart_colors'][i % len(self.colors['chart_colors'])],
                hovertemplate='%{y} plays<br>%{x}<extra>%{fullData.name}</extra>'
            ))
        
        # Update layout
        fig.update_layout(
            title=dict(
                text='Artist Listening Trends',
                font=dict(size=20, color=self.colors['text_primary'])
            ),
            xaxis=dict(
                title='Date',
                showgrid=False,
                color=self.colors['text_secondary']
            ),
            yaxis=dict(
                title='Plays per Week',
                showgrid=True,
                gridcolor='rgba(179, 179, 179, 0.125)',
                color=self.colors['text_secondary']
            ),
            hovermode='x unified',
            **self.default_layout
        )
        
        return fig
    
    def create_sunburst_chart(self, data: List[Dict[str, Any]], max_items: int = 100) -> go.Figure:
        """Create a sunburst chart for hierarchical music data (Artist > Album > Track)"""
        # Prepare hierarchical data
        labels = ['All Music']
        parents = ['']
        values = [0]
        colors = [self.colors['primary']]
        
        # Limit data
        data = data[:max_items]
        
        # Group by artist
        artist_groups = {}
        for item in data:
            artist = item['artist_name']
            album = item.get('album_name', 'Unknown Album')
            track = item['track_name']
            plays = item['play_count']
            
            if artist not in artist_groups:
                artist_groups[artist] = {}
            if album not in artist_groups[artist]:
                artist_groups[artist][album] = {}
            artist_groups[artist][album][track] = plays
        
        # Build hierarchy
        for i, (artist, albums) in enumerate(artist_groups.items()):
            artist_plays = sum(sum(tracks.values()) for tracks in albums.values())
            labels.append(artist)
            parents.append('All Music')
            values.append(artist_plays)
            colors.append(self.colors['chart_colors'][i % len(self.colors['chart_colors'])])
            
            for album, tracks in albums.items():
                album_plays = sum(tracks.values())
                labels.append(album)
                parents.append(artist)
                values.append(album_plays)
                colors.append(self.colors['chart_colors'][i % len(self.colors['chart_colors'])])
                
                for track, plays in tracks.items():
                    labels.append(track)
                    parents.append(album)
                    values.append(plays)
                    colors.append(self.colors['chart_colors'][i % len(self.colors['chart_colors'])])
        
        # Create sunburst
        fig = go.Figure(go.Sunburst(
            labels=labels,
            parents=parents,
            values=values,
            branchvalues='total',
            marker=dict(colors=colors),
            hovertemplate='<b>%{label}</b><br>Plays: %{value}<extra></extra>',
            textfont=dict(size=12, color=self.colors['text_primary'])
        ))
        
        # Update layout
        fig.update_layout(
            title=dict(
                text='Music Hierarchy',
                font=dict(size=20, color=self.colors['text_primary'])
            ),
            **self.default_layout
        )
        
        return fig
    
    def create_listening_heatmap(self, data: pd.DataFrame) -> go.Figure:
        """Create a heatmap of listening patterns by day of week and hour"""
        # Create a matrix of day x hour
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        hours = list(range(24))
        
        # Initialize matrix
        z = np.zeros((7, 24))
        
        # Fill matrix with play counts
        if isinstance(data, pd.Series):
            for (day, hour), plays in data.items():
                if 0 <= day < 7 and 0 <= hour < 24:
                    z[day, hour] = plays
        else:
            for idx, row in data.iterrows():
                if hasattr(idx, 'dayofweek') and hasattr(idx, 'hour'):
                    z[idx.dayofweek, idx.hour] = row['plays']
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=[f'{h:02d}:00' for h in hours],
            y=days,
            colorscale=[
                [0, self.colors['background']],
                [0.2, self.colors['surface']],
                [0.4, 'rgba(29, 185, 84, 0.5)'],
                [0.6, self.colors['primary']],
                [0.8, self.colors['accent']],
                [1, '#B8FF4F']
            ],
            hovertemplate='%{y}<br>%{x}<br>%{z} plays<extra></extra>',
            colorbar=dict(
                title="Plays",
                titleside="right",
                thickness=15,
                len=0.7,
                x=1.02
            )
        ))
        
        # Update layout
        fig.update_layout(
            title=dict(
                text='Weekly Listening Patterns',
                font=dict(size=20, color=self.colors['text_primary'])
            ),
            xaxis=dict(
                title='Hour of Day',
                side='bottom',
                color=self.colors['text_secondary']
            ),
            yaxis=dict(
                title='Day of Week',
                color=self.colors['text_secondary']
            ),
            **self.default_layout
        )
        
        return fig
    
    def create_animated_timeline(self, data: pd.DataFrame, metric: str = 'plays') -> go.Figure:
        """Create an animated timeline of listening history"""
        # Group by month
        monthly_data = data.groupby(pd.Grouper(freq='M')).agg({
            metric: 'sum',
            'unique_tracks': 'nunique',
            'unique_artists': 'nunique'
        }).reset_index()
        
        # Create figure
        fig = go.Figure()
        
        # Add initial trace
        fig.add_trace(go.Scatter(
            x=monthly_data['date'],
            y=monthly_data[metric],
            mode='lines+markers',
            name=metric.title(),
            line=dict(color=self.colors['primary'], width=3),
            marker=dict(size=8, color=self.colors['accent']),
            hovertemplate='%{x|%B %Y}<br>%{y} ' + metric + '<extra></extra>'
        ))
        
        # Add range slider
        fig.update_xaxes(
            rangeslider_visible=True,
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            )
        )
        
        # Update layout
        fig.update_layout(
            title=dict(
                text='Listening Timeline',
                font=dict(size=20, color=self.colors['text_primary'])
            ),
            xaxis=dict(
                title='Date',
                color=self.colors['text_secondary']
            ),
            yaxis=dict(
                title=metric.title(),
                color=self.colors['text_secondary']
            ),
            **self.default_layout
        )
        
        return fig
    
    def to_json(self, fig: go.Figure) -> str:
        """Convert figure to JSON for frontend"""
        return json.dumps(fig.to_dict(), cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_mood_timeline(self, mood_data: List[Dict[str, Any]]) -> go.Figure:
        """Create mood timeline visualization"""
        if not mood_data:
            return self._create_empty_figure("No mood data available")
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(mood_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Create stacked area chart for mood composition
        fig = go.Figure()
        
        # Group by hour and mood for smoother visualization
        df['hour'] = df['timestamp'].dt.floor('H')
        mood_counts = df.groupby(['hour', 'mood']).size().reset_index(name='count')
        
        # Pivot to get moods as columns
        mood_pivot = mood_counts.pivot(index='hour', columns='mood', values='count').fillna(0)
        
        # Add traces for each mood
        for mood in mood_pivot.columns:
            fig.add_trace(go.Scatter(
                x=mood_pivot.index,
                y=mood_pivot[mood],
                name=mood.title(),
                mode='lines',
                stackgroup='one',
                fillcolor=self._get_mood_color(mood),
                line=dict(width=0.5, color=self._get_mood_color(mood))
            ))
        
        fig.update_layout(
            title=dict(
                text='Emotional Journey Through Music',
                font=dict(size=24, color=self.colors['text_primary'])
            ),
            xaxis=dict(
                title='Time',
                color=self.colors['text_secondary'],
                rangeslider=dict(visible=True)
            ),
            yaxis=dict(
                title='Mood Intensity',
                color=self.colors['text_secondary']
            ),
            hovermode='x unified',
            **self.default_layout
        )
        
        return fig
    
    def create_mood_wheel(self, patterns: Dict[str, Any]) -> go.Figure:
        """Create circular mood visualization by hour"""
        hourly = patterns.get('hourly_pattern', {})
        if not hourly:
            return self._create_empty_figure("No hourly mood data")
        
        # Prepare data for polar chart
        hours = list(range(24))
        moods = list(patterns.get('mood_colors', {}).keys())
        
        fig = go.Figure()
        
        for mood in moods:
            values = [hourly.get(h, {}).get(mood, 0) for h in hours]
            
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=[f"{h:02d}:00" for h in hours],
                fill='toself',
                fillcolor=self._get_mood_color(mood),
                opacity=0.6,
                name=mood.title(),
                line=dict(color=self._get_mood_color(mood))
            ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    ticksuffix='%',
                    color=self.colors['text_secondary']
                ),
                angularaxis=dict(
                    direction='clockwise',
                    rotation=90,
                    color=self.colors['text_secondary']
                ),
                bgcolor=self.colors['background']
            ),
            title=dict(
                text='Daily Mood Patterns',
                font=dict(size=20, color=self.colors['text_primary'])
            ),
            showlegend=True,
            **self.default_layout
        )
        
        return fig
    
    def create_mood_heatmap(self, patterns: Dict[str, Any]) -> go.Figure:
        """Create heatmap of moods by day and hour"""
        daily = patterns.get('daily_pattern', {})
        hourly = patterns.get('hourly_pattern', {})
        
        if not daily or not hourly:
            return self._create_empty_figure("No pattern data available")
        
        # Create a matrix for the heatmap
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        hours = list(range(24))
        
        # For simplicity, show dominant mood per day/hour combination
        # In a real implementation, this would use actual play data
        matrix = []
        mood_matrix = []
        
        for day in days:
            row = []
            mood_row = []
            for hour in hours:
                # Get dominant mood (simplified - would use real data)
                dominant_mood = 'calm'  # Default
                max_percent = 0
                
                if day in daily and hour in hourly:
                    for mood in hourly[hour]:
                        if hourly[hour][mood] > max_percent:
                            max_percent = hourly[hour][mood]
                            dominant_mood = mood
                
                row.append(max_percent)
                mood_row.append(dominant_mood)
            
            matrix.append(row)
            mood_matrix.append(mood_row)
        
        # Create custom colorscale
        colorscale = [
            [0, self.colors['background']],
            [0.5, self.colors['primary']],
            [1, self.colors['accent']]
        ]
        
        fig = go.Figure(data=go.Heatmap(
            z=matrix,
            x=[f"{h:02d}:00" for h in hours],
            y=days,
            colorscale=colorscale,
            showscale=True,
            hoverongaps=False,
            hovertemplate='%{y}<br>%{x}<br>Intensity: %{z:.1f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title=dict(
                text='Weekly Mood Patterns',
                font=dict(size=20, color=self.colors['text_primary'])
            ),
            xaxis=dict(
                title='Hour of Day',
                color=self.colors['text_secondary']
            ),
            yaxis=dict(
                title='Day of Week',
                color=self.colors['text_secondary']
            ),
            **self.default_layout
        )
        
        return fig
    
    def _get_mood_color(self, mood: str) -> str:
        """Get color for mood visualization"""
        mood_colors = {
            'happy': '#FFD700',
            'energetic': '#FF4500',
            'calm': '#87CEEB',
            'sad': '#4682B4',
            'angry': '#DC143C',
            'romantic': '#FF69B4',
            'melancholic': '#9370DB',
            'uplifting': '#32CD32'
        }
        return mood_colors.get(mood, self.colors['primary'])
    
    def _create_empty_figure(self, message: str) -> go.Figure:
        """Create empty figure with message"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20, color=self.colors['text_secondary'])
        )
        fig.update_layout(**self.default_layout)
        return fig