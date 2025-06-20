# Spotify Sync Automated

An automated system that continuously syncs your Last.fm listening history with Spotify, creates and updates playlists, and provides beautiful visualizations of your music listening habits.

## Features

- **Automatic Syncing**: Fetches listening history from Last.fm and Spotify every 5 minutes
- **Smart Playlists**: Automatically updates playlists based on your listening patterns:
  - Most Listened To (all-time favorites)
  - Recent Favorites (last 30 days)
  - Binged Songs (played 3+ times in a single day)
- **Web Dashboard**: Beautiful dark-themed interface showing sync status and controls
- **Visualizations**: 
  - Calendar heatmap of listening activity
  - Top tracks and artists charts
  - Listening patterns by hour and weekday
  - Music discovery timeline
  - Listening diversity metrics
  - Yearly "Wrapped" summaries
- **Database Storage**: All listening history stored locally in SQLite
- **Extensible Framework**: Easy to add new playlist types and visualizations

## Prerequisites

- Python 3.8+
- Spotify Premium account (for API access)
- Last.fm account with Spotify scrobbling enabled
- Spotify and Last.fm API credentials

## Installation

1. Clone the repository:
```bash
cd spotify_sync_automated
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API credentials
```

## Getting API Credentials

### Spotify API
1. Go to https://developer.spotify.com/dashboard
2. Create a new app
3. Add `http://localhost:5000/callback` to Redirect URIs
4. Copy Client ID and Client Secret to `.env`

### Last.fm API
1. Go to https://www.last.fm/api/account/create
2. Create an application
3. Copy API Key and Shared Secret to `.env`

## Running the Application

```bash
python run.py
```

Options:
- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to bind to (default: 5000)
- `--debug`: Enable debug mode
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--no-scheduler`: Disable automatic syncing

## First Time Setup

1. Start the application
2. Navigate to http://localhost:5000
3. Click "Connect Spotify" to authenticate
4. The system will start syncing automatically
5. Create playlists through the web UI or manually in Spotify
6. Update playlist IDs in your `.env` file

## Configuration

Edit `config.yaml` to customize:
- Sync intervals
- Playlist sizes
- Time periods for recent favorites
- Minimum plays for binged songs

## Project Structure

```
spotify_sync_automated/
├── src/
│   ├── api/              # API clients (Spotify, Last.fm)
│   ├── core/             # Database models and configuration
│   ├── services/         # Business logic (sync, playlists, analytics)
│   ├── scheduler/        # Automated task scheduling
│   └── web/              # Flask web application
├── templates/            # HTML templates
├── static/               # CSS, JS, images
├── logs/                 # Application logs
├── run.py               # Main entry point
└── config.yaml          # Application configuration
```

## API Endpoints

- `GET /api/status` - System status and statistics
- `POST /api/sync/trigger` - Manually trigger sync
- `GET /api/analytics/top-tracks` - Top tracks for time period
- `GET /api/analytics/top-artists` - Top artists for time period
- `GET /api/analytics/listening-patterns` - Hourly and weekly patterns
- `GET /api/analytics/calendar` - Calendar heatmap data
- `GET /api/analytics/yearly-stats/<year>` - Yearly statistics
- `GET /api/analytics/diversity` - Listening diversity metrics
- `POST /api/playlists/update/<type>` - Update specific playlist

## Extending the System

### Adding New Playlist Types

1. Add configuration in `config.yaml`
2. Create generation method in `PlaylistService`
3. Add to `update_all_playlists()` method
4. Update web UI to display new playlist

### Adding New Visualizations

1. Create data preparation method in `AnalyticsService`
2. Add visualization method in `VisualizationFramework`
3. Create API endpoint in `routes.py`
4. Add to web interface

## Troubleshooting

- **Authentication Issues**: Delete `.spotify_cache` and re-authenticate
- **Sync Not Working**: Check logs in `logs/` directory
- **Missing Tracks**: Some tracks may not have Spotify IDs; check `/api/tracks/missing-ids`
- **Database Issues**: Database is stored in `spotify_sync.db`

## Development

Run tests:
```bash
pytest tests/
```

Format code:
```bash
black src/
```

## License

MIT License - feel free to modify and use as you wish!

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.