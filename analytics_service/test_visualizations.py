#!/usr/bin/env python3
"""Test enhanced visualizations directly"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from wrapped_service.visualizations.enhanced_charts import EnhancedVisualizations
from wrapped_service.analytics.core import AnalyticsService
import pandas as pd
from datetime import datetime, timedelta
import random

def test_visualizations():
    """Test visualization generation"""
    print("Testing Enhanced Visualizations")
    print("=" * 50)
    
    # Initialize services
    viz = EnhancedVisualizations()
    analytics = AnalyticsService()
    
    # Test 1: Calendar visualization
    print("\n1. Testing Calendar Visualization...")
    try:
        calendar_data = analytics.get_listening_calendar_data(2024)
        if not calendar_data.empty:
            fig = viz.create_github_style_calendar(calendar_data, 2024)
            print("✓ Calendar visualization created successfully")
        else:
            print("✗ No calendar data for 2024")
    except Exception as e:
        print(f"✗ Calendar error: {e}")
    
    # Test 2: Radial chart (listening clock)
    print("\n2. Testing Listening Clock...")
    try:
        hourly_data = analytics.get_listening_stats_by_hour()
        if hourly_data:
            fig = viz.create_radial_chart(hourly_data, "Listening Clock")
            print("✓ Listening clock created successfully")
        else:
            print("✗ No hourly data available")
    except Exception as e:
        print(f"✗ Clock error: {e}")
    
    # Test 3: Generate sample data for other visualizations
    print("\n3. Testing with sample data...")
    
    # Sample artist data for stream graph
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    artists = ['Artist A', 'Artist B', 'Artist C', 'Artist D', 'Artist E']
    artist_data = []
    
    for date in dates:
        for artist in artists:
            if random.random() > 0.3:  # 70% chance of play
                artist_data.append({
                    'date': date,
                    'artist': artist
                })
    
    artist_df = pd.DataFrame(artist_data)
    
    try:
        fig = viz.create_stream_graph(artist_df)
        print("✓ Stream graph created successfully")
    except Exception as e:
        print(f"✗ Stream graph error: {e}")
    
    # Sample data for sunburst
    sample_tracks = []
    for i in range(50):
        sample_tracks.append({
            'artist_name': f'Artist {i % 5}',
            'album_name': f'Album {i % 10}',
            'track_name': f'Track {i}',
            'play_count': random.randint(1, 100)
        })
    
    try:
        fig = viz.create_sunburst_chart(sample_tracks)
        print("✓ Sunburst chart created successfully")
    except Exception as e:
        print(f"✗ Sunburst error: {e}")
    
    # Test weekly patterns
    try:
        # Create sample weekly data
        weekly_data = pd.Series(
            index=pd.MultiIndex.from_product([range(7), range(24)], names=['dayofweek', 'hour']),
            data=[random.randint(0, 20) for _ in range(7*24)]
        )
        weekly_data.name = 'plays'
        
        fig = viz.create_listening_heatmap(weekly_data)
        print("✓ Weekly heatmap created successfully")
    except Exception as e:
        print(f"✗ Heatmap error: {e}")
    
    print("\n" + "=" * 50)
    print("Visualization tests complete!")
    print("\nNote: The wrapped service provides these visualizations via web endpoints.")
    print("Start the service with: python wrapped_service/run.py")
    print("Then visit: http://localhost:5002/explore")

if __name__ == "__main__":
    test_visualizations()