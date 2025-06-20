# Spotify Sync Automated

An automated system that continuously syncs your Last.fm listening history with Spotify, creates and updates playlists, and provides beautiful visualizations of your music listening habits.

## Features

- **Automatic Syncing**: Fetches listening history from Last.fm and Spotify every 5 minutes
- **Complete History Import**: Sync your entire Last.fm history (70k+ scrobbles) with resume capability
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
- **Database Storage**: All listening history stored locally in SQLite with deduplication
- **Robust Error Handling**: Automatic retries, rate limit handling, and resume from failures
- **Extensible Framework**: Easy to add new playlist types and visualizations

## Prerequisites

- Python 3.8+
- Spotify Premium account (for API access)
- Last.fm account with listening history
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
3. Add `http://localhost:5001/callback` to Redirect URIs (note: port 5001 to avoid macOS conflicts)
4. Copy Client ID and Client Secret to `.env`

### Last.fm API
1. Go to https://www.last.fm/api/account/create
2. Create an application
3. Copy API Key and Shared Secret to `.env`

## Initial Setup - Syncing Your Complete History

Before running the web application, sync your complete Last.fm history:

### 1. Run Database Migration (first time only)
```bash
python migrate_database.py
```

### 2. Start the Complete Sync
```bash
python sync_lastfm_complete_v2.py
```

This will:
- Sync your entire Last.fm history in monthly chunks
- Resume automatically if interrupted
- Show real-time progress and ETA
- Handle rate limits gracefully

### 3. Monitor Progress (optional, in another terminal)
```bash
python monitor_sync.py
```

### 4. Resume Sync (if interrupted)
```bash
python continue_sync.py
```

The sync saves progress after each chunk, so you can safely stop and resume anytime.

## Running the Application

After initial sync is complete:

```bash
python run.py
```

Options:
- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to bind to (default: 5001)
- `--debug`: Enable debug mode
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--no-scheduler`: Disable automatic syncing

## First Time Web Setup

1. Start the application
2. Navigate to http://localhost:5001
3. Click "Connect Spotify" to authenticate
4. The system will start syncing new plays automatically every 5 minutes
5. Create playlists through the web UI or manually in Spotify
6. Update playlist IDs in your `.env` file

## Utility Scripts

### Check Database Status
```bash
python check_db_status.py
```
Shows current database statistics and date ranges.

### Check Sync Progress
```bash
python check_sync_progress.py
```
Shows detailed progress of the full history sync.

### Test Individual Components
```bash
python test_sync.py
```
Interactive menu to test Last.fm connection, database, and sync operations.

### Run Component Tests
```bash
python -m pytest tests/
```

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
├── tests/                # Unit and integration tests
├── run.py               # Main entry point
├── sync_lastfm_complete_v2.py  # Full history sync script
├── continue_sync.py     # Resume sync helper
├── monitor_sync.py      # Live sync monitoring
├── check_db_status.py   # Database statistics
├── check_sync_progress.py # Sync progress checker
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

## Database Schema

The system uses SQLite with the following main tables:
- `artists` - Artist information with Spotify IDs
- `albums` - Album information linked to artists
- `tracks` - Track information with Spotify IDs
- `play_history` - Complete listening history with timestamps
- `playlists` - Configured playlists
- `playlist_tracks` - Tracks in each playlist
- `sync_status` - Status of sync operations
- `sync_progress` - Detailed progress tracking for full syncs

## Troubleshooting

- **Port 5000 Already in Use**: The default port is 5001 to avoid macOS AirPlay conflicts
- **Authentication Issues**: Delete `.spotify_cache` and re-authenticate
- **Sync Not Working**: Check logs in `logs/` directory
- **Missing Tracks**: Some tracks may not have Spotify IDs; check `/api/tracks/missing-ids`
- **Database Issues**: Database is stored in `spotify_sync.db`
- **Sync Interrupted**: Use `python continue_sync.py` to resume
- **Rate Limits**: The sync automatically handles rate limits with exponential backoff

## Performance

- Initial sync of 70k+ tracks takes approximately 60-90 minutes
- Sync rate: ~100-150 tracks/second
- Database queries optimized with proper indexing
- Monthly chunks ensure manageable memory usage
- Resume capability prevents data loss

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