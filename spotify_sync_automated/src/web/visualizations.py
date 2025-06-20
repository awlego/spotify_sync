import plotly.graph_objects as go
import plotly.express as px
import plotly.utils
from plotly.subplots import make_subplots
import pandas as pd
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import calendar


class VisualizationFramework:
    """Extensible framework for creating music listening visualizations"""
    
    def __init__(self):
        self.default_layout = {
            'template': 'plotly_dark',
            'font': {'family': 'Arial, sans-serif'},
            'margin': {'l': 50, 'r': 50, 't': 50, 'b': 50},
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'paper_bgcolor': 'rgba(0,0,0,0)'
        }
    
    def to_json(self, fig) -> str:
        """Convert Plotly figure to JSON for frontend"""
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_calendar_heatmap(self, data: List[Dict[str, Any]], 
                               year: int, title: Optional[str] = None) -> go.Figure:
        """Create a calendar heatmap of listening activity"""
        # Convert data to DataFrame
        df = pd.DataFrame(data)
        if df.empty:
            return self._empty_figure("No listening data available")
        
        df['date'] = pd.to_datetime(df['date'])
        df['day'] = df['date'].dt.day
        df['month'] = df['date'].dt.month
        df['weekday'] = df['date'].dt.weekday
        
        # Create a matrix for the entire year
        import numpy as np
        z = np.zeros((7, 53))  # 7 days x 53 weeks
        
        # Fill the matrix
        for _, row in df.iterrows():
            week = row['date'].isocalendar()[1] - 1
            if 0 <= week < 53:
                z[row['weekday'], week] = row['plays']
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=list(range(53)),
            y=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            colorscale='Viridis',
            showscale=True,
            hoverongaps=False,
            hovertemplate='Week %{x}<br>%{y}<br>Plays: %{z}<extra></extra>'
        ))
        
        # Update layout
        fig.update_layout(
            title=title or f'Listening Activity Calendar - {year}',
            xaxis_title='Week of Year',
            yaxis_title='Day of Week',
            **self.default_layout
        )
        
        return fig
    
    def create_top_items_bar_chart(self, data: List[Dict[str, Any]], 
                                  item_type: str = 'tracks',
                                  limit: int = 20) -> go.Figure:
        """Create a horizontal bar chart of top items (tracks/artists)"""
        if not data:
            return self._empty_figure(f"No {item_type} data available")
        
        # Limit data
        data = data[:limit]
        
        # Prepare data
        if item_type == 'tracks':
            labels = [f"{d['track_name']} - {d['artist_name']}" for d in data]
        else:
            labels = [d['artist_name'] for d in data]
        
        values = [d['play_count'] for d in data]
        
        # Create figure
        fig = go.Figure(data=[
            go.Bar(
                x=values,
                y=labels,
                orientation='h',
                marker_color='lightblue',
                text=values,
                textposition='auto'
            )
        ])
        
        # Update layout
        fig.update_layout(
            title=f'Top {limit} {item_type.capitalize()}',
            xaxis_title='Play Count',
            yaxis={'categoryorder': 'total ascending'},
            height=max(400, len(labels) * 25),
            **self.default_layout
        )
        
        return fig
    
    def create_listening_patterns(self, hourly_data: Dict[int, int], 
                                 weekday_data: Dict[str, int]) -> go.Figure:
        """Create visualizations for listening patterns"""
        # Create subplots
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Listening by Hour of Day', 'Listening by Day of Week'),
            column_widths=[0.5, 0.5]
        )
        
        # Hourly pattern
        hours = list(range(24))
        hourly_values = [hourly_data.get(h, 0) for h in hours]
        
        fig.add_trace(
            go.Bar(x=hours, y=hourly_values, name='Hourly', marker_color='skyblue'),
            row=1, col=1
        )
        
        # Weekday pattern
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_values = [weekday_data.get(d, 0) for d in weekdays]
        
        fig.add_trace(
            go.Bar(x=weekdays, y=weekday_values, name='Weekday', marker_color='lightgreen'),
            row=1, col=2
        )
        
        # Update layout
        fig.update_xaxes(title_text="Hour", row=1, col=1)
        fig.update_xaxes(title_text="Day", row=1, col=2)
        fig.update_yaxes(title_text="Plays", row=1, col=1)
        fig.update_yaxes(title_text="Plays", row=1, col=2)
        
        fig.update_layout(
            title='Listening Patterns',
            showlegend=False,
            height=400,
            **self.default_layout
        )
        
        return fig
    
    def create_diversity_gauge(self, diversity_data: Dict[str, Any]) -> go.Figure:
        """Create gauge charts for listening diversity"""
        fig = make_subplots(
            rows=1, cols=2,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}]],
            subplot_titles=('Artist Diversity', 'Track Diversity')
        )
        
        # Artist diversity gauge
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=diversity_data['artist_diversity'] * 100,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Artist Diversity %"},
                gauge={'axis': {'range': [None, 100]},
                       'bar': {'color': "darkblue"},
                       'steps': [
                           {'range': [0, 25], 'color': "lightgray"},
                           {'range': [25, 50], 'color': "gray"}],
                       'threshold': {'line': {'color': "red", 'width': 4},
                                   'thickness': 0.75,
                                   'value': 90}}
            ),
            row=1, col=1
        )
        
        # Track diversity gauge
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=diversity_data['track_diversity'] * 100,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Track Diversity %"},
                gauge={'axis': {'range': [None, 100]},
                       'bar': {'color': "darkgreen"},
                       'steps': [
                           {'range': [0, 25], 'color': "lightgray"},
                           {'range': [25, 50], 'color': "gray"}],
                       'threshold': {'line': {'color': "red", 'width': 4},
                                   'thickness': 0.75,
                                   'value': 90}}
            ),
            row=1, col=2
        )
        
        fig.update_layout(
            title=f"Listening Diversity (Last {diversity_data.get('total_plays', 0)} plays)",
            height=300,
            **self.default_layout
        )
        
        return fig
    
    def create_monthly_trend(self, monthly_data: Dict[int, int], year: int) -> go.Figure:
        """Create monthly trend line chart"""
        months = list(range(1, 13))
        month_names = [calendar.month_abbr[m] for m in months]
        values = [monthly_data.get(m, 0) for m in months]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=month_names,
            y=values,
            mode='lines+markers',
            name='Plays',
            line={'color': 'rgb(100, 200, 100)', 'width': 3},
            marker={'size': 10}
        ))
        
        fig.update_layout(
            title=f'Monthly Listening Trend - {year}',
            xaxis_title='Month',
            yaxis_title='Total Plays',
            hovermode='x unified',
            **self.default_layout
        )
        
        return fig
    
    def create_discovery_timeline(self, discoveries: List[Dict[str, Any]]) -> go.Figure:
        """Create timeline of music discoveries"""
        if not discoveries:
            return self._empty_figure("No new artist discoveries in this period")
        
        df = pd.DataFrame(discoveries)
        df['discovered_date'] = pd.to_datetime(df['discovered_date'])
        
        fig = go.Figure()
        
        # Add scatter plot
        fig.add_trace(go.Scatter(
            x=df['discovered_date'],
            y=df['total_plays_since'],
            mode='markers+text',
            marker=dict(
                size=df['total_plays_since'],
                sizemode='area',
                sizeref=2.*max(df['total_plays_since'])/(40.**2),
                sizemin=4,
                color=df['total_plays_since'],
                colorscale='Viridis',
                showscale=True
            ),
            text=df['artist_name'],
            textposition="top center",
            hovertemplate='<b>%{text}</b><br>Discovered: %{x}<br>Plays since: %{y}<extra></extra>'
        ))
        
        fig.update_layout(
            title='Artist Discovery Timeline',
            xaxis_title='Discovery Date',
            yaxis_title='Total Plays Since Discovery',
            **self.default_layout
        )
        
        return fig
    
    def create_wrapped_summary(self, stats: Dict[str, Any]) -> go.Figure:
        """Create a Wrapped-style summary visualization"""
        # Create subplots for different metrics
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}],
                   [{'type': 'indicator'}, {'type': 'indicator'}]],
            subplot_titles=('Total Plays', 'Unique Tracks', 'Unique Artists', 'Daily Average')
        )
        
        # Add metrics
        metrics = [
            ('Total Plays', stats['total_plays'], 'number', 1, 1),
            ('Unique Tracks', stats['unique_tracks'], 'number', 1, 2),
            ('Unique Artists', stats['unique_artists'], 'number', 2, 1),
            ('Daily Average', round(stats['daily_average'], 1), 'number', 2, 2)
        ]
        
        for title, value, mode, row, col in metrics:
            fig.add_trace(
                go.Indicator(
                    mode=mode,
                    value=value,
                    title={'text': title, 'font': {'size': 20}},
                    number={'font': {'size': 40}}
                ),
                row=row, col=col
            )
        
        fig.update_layout(
            title=f"Your {stats['year']} in Music",
            height=400,
            **self.default_layout
        )
        
        return fig
    
    def _empty_figure(self, message: str) -> go.Figure:
        """Create an empty figure with a message"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20)
        )
        fig.update_layout(**self.default_layout)
        return fig