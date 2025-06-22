# Music Analytics Service

A personal music listening analytics dashboard that provides comprehensive insights into your listening history.

## Features

### Time Range Flexibility
- **All Time**: Analyze your complete listening history
- **Specific Year**: Focus on any year of data
- **Recent Periods**: Last 7, 30, or 90 days
- **Custom Range**: Select any date range for analysis

### Interactive Visualizations

1. **GitHub-Style Calendar Heatmap**
   - Daily listening activity visualization
   - Color intensity shows play frequency
   - Full year view with month labels

2. **Listening Clock (Radial Chart)**
   - 24-hour listening pattern analysis
   - Shows peak listening hours
   - Adapts to selected time period

3. **Weekly Patterns Heatmap**
   - Day of week vs hour analysis
   - Identify your listening routines
   - Spot weekend vs weekday differences

4. **Artist Trends Stream Graph**
   - Track how your top artists' popularity changes over time
   - Stacked area visualization
   - Top 10 artists by play count

5. **Music Hierarchy Sunburst**
   - Interactive Artist → Album → Track breakdown
   - Click to zoom into specific artists or albums
   - Proportional sizing by play count

6. **Listening Timeline**
   - Animated monthly progression
   - Range selector for zooming
   - Shows play count trends

### Statistics Dashboard
- Total plays
- Unique tracks discovered
- Unique artists explored
- Total hours listened

## Usage

### Starting the Service

```bash
cd analytics_service
python run.py
```

The service will start on `http://localhost:5002`

### Navigation

- **Dashboard**: `/explore` - Main analytics dashboard
- **Year Review**: `/` - Annual summary view (similar to year-end wrapped)

### API Endpoints

All visualization endpoints support flexible time ranges via query parameters:

- `?period=all` - All time data
- `?period=year&year=2024` - Specific year
- `?period=days&days=30` - Last N days
- `?period=custom&start_date=2024-01-01&end_date=2024-12-31` - Custom range

Example:
```
/api/visualizations/calendar?period=year&year=2024
/api/analytics/data?period=all
```

## Configuration

The service uses the shared configuration from the main Spotify Sync project. No additional configuration is needed.

## Data Source

This service reads from the SQLite database populated by the sync service. It provides read-only analytics and does not modify any data.

## Design Philosophy

- **Privacy First**: All analytics are computed locally on your data
- **No External Services**: No data is sent to third parties
- **Flexible Time Ranges**: Not limited to annual summaries
- **Interactive Exploration**: Discover patterns in your listening habits
- **Modern UI**: Clean, dark-themed interface with smooth animations