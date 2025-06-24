# Music Analytics Service

A personal music listening analytics dashboard that provides comprehensive insights into your listening history.

## Features

### Time Range Flexibility
- **All Time**: Analyze your complete listening history
- **Specific Year**: Focus on any year of data
- **Recent Periods**: Last 7, 30, or 90 days
- **Custom Range**: Select any date range for analysis

### Interactive Visualizations

#### Standard Visualizations

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

#### Advanced Visualizations

7. **Genre Galaxy Explorer** 🌌
   - 3D interactive visualization of your genre landscape
   - Genres positioned based on their musical relationships
   - Size represents listening frequency
   - Click and drag to rotate, scroll to zoom
   - Shows your journey through different genres over time

8. **Mood Spectrum Analyzer** 🎭
   - Tracks the emotional journey of your music
   - Analyzes energy, valence, and other audio features
   - Daily and hourly mood patterns
   - Mood timeline showing emotional shifts
   - Recommendations based on time of day

9. **Discovery Network Graph** 🕸️
   - Interactive network showing how you discovered artists
   - Visualizes connections between related artists
   - Identifies "gateway" artists that led to new discoveries
   - Find shortest path between any two artists
   - Community detection to find genre clusters

10. **Musical Diversity Index** 📊
    - Portfolio-style analysis of your genre distribution
    - Risk/return scatter plot for genre preferences
    - Diversity score calculation
    - Historical performance tracking
    - Recommendations for broadening musical horizons
    - Export detailed diversity reports

11. **Weather-Music Correlation** 🌤️
    - Analyzes how weather affects your music choices
    - Correlation matrix between weather and audio features
    - Real-time music recommendations based on current weather
    - Location-aware analysis with interactive map
    - Historical patterns by weather type
    - Predictions for optimal listening based on conditions

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

#### Advanced Visualizations
- **Genre Galaxy**: `/genre-galaxy` - 3D genre exploration
- **Mood Spectrum**: `/mood-spectrum` - Emotional journey analysis
- **Discovery Network**: `/discovery-network` - Artist discovery patterns
- **Musical Diversity**: `/diversity-index` - Portfolio-style diversity analysis
- **Weather Correlation**: `/weather-correlation` - Weather-music relationship analysis

### API Endpoints

All visualization endpoints support flexible time ranges via query parameters:

- `?period=all` - All time data
- `?period=year&year=2024` - Specific year
- `?period=days&days=30` - Last N days
- `?period=custom&start_date=2024-01-01&end_date=2024-12-31` - Custom range

#### Standard API Examples:
```
/api/visualizations/calendar?period=year&year=2024
/api/analytics/data?period=all
/api/visualizations/listening-clock?period=days&days=30
```

#### Advanced Visualization APIs:

**Genre Galaxy**
```
/api/visualizations/genre-galaxy?user_id=1
/api/visualizations/genre-journey?start_date=2024-01-01&end_date=2024-12-31
```

**Mood Analysis**
```
/api/visualizations/mood-timeline?days=30
/api/visualizations/mood-patterns
/api/insights/mood-analysis?days=7
```

**Discovery Network**
```
/api/visualizations/discovery-network?user_id=1
/api/visualizations/discovery-path/Taylor%20Swift/Bon%20Iver
```

**Musical Diversity**
```
/api/visualizations/genre-portfolio?days=30
/api/visualizations/genre-performance?days=90
```

**Weather Correlation**
```
/api/visualizations/weather-correlation?days=90&lat=40.7128&lon=-74.0060
/api/weather/current-predictions?lat=40.7128&lon=-74.0060
```

## Configuration

The service uses the shared configuration from the main Spotify Sync project. No additional configuration is needed.

### Optional Configuration

**Weather API (for Weather-Music Correlation)**
- Set `OPENWEATHER_API_KEY` environment variable for real weather data
- Without API key, the service uses synthetic weather data for demonstration

**Location Settings**
- The service auto-detects your location for weather correlation
- You can override with custom latitude/longitude in the UI

## Data Source

This service reads from the SQLite database populated by the sync service. It provides read-only analytics and does not modify any data.

## How to Use Advanced Visualizations

### Genre Galaxy Explorer
1. Navigate to `/genre-galaxy`
2. Use mouse to rotate the 3D visualization (click and drag)
3. Scroll to zoom in/out
4. Click on genres to see details
5. Use time controls to see your genre journey over time

### Mood Spectrum Analyzer
1. Go to `/mood-spectrum`
2. Select time range to analyze mood patterns
3. View mood timeline to see emotional journey
4. Check hourly/daily patterns for optimal listening times
5. Get personalized recommendations based on time of day

### Discovery Network Graph
1. Visit `/discovery-network`
2. Explore artist connections and discovery paths
3. Click on nodes to highlight connections
4. Drag nodes to rearrange the network
5. Use search to find paths between specific artists

### Musical Diversity Index
1. Open `/diversity-index`
2. View your genre portfolio allocation
3. Check diversity score and risk metrics
4. Analyze historical performance trends
5. Export detailed reports for tracking progress

### Weather-Music Correlation
1. Access `/weather-correlation`
2. Allow location access or set custom location
3. View correlation matrix for weather vs music features
4. Get real-time recommendations based on current weather
5. Explore historical patterns by weather type

## Design Philosophy

- **Privacy First**: All analytics are computed locally on your data
- **No External Services**: No data is sent to third parties (except optional weather API)
- **Flexible Time Ranges**: Not limited to annual summaries
- **Interactive Exploration**: Discover patterns in your listening habits
- **Modern UI**: Clean, dark-themed interface with smooth animations
- **Data-Driven Insights**: Advanced algorithms to uncover hidden patterns