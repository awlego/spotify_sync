# Spotify Sync - Service Architecture

This project is now organized into two separate services that share a common database:

## Services

### 1. Sync Service (Backend)
**Port:** 5001  
**Purpose:** Syncs Last.fm listening history to local database and maintains Spotify playlists

**Features:**
- Automated Last.fm → SQLite syncing every 5 minutes
- Smart playlist generation (Most Listened, Recent Favorites, Binged Songs)
- Minimal monitoring UI
- Spotify OAuth for playlist management

**Run:**
```bash
cd sync_service
python run.py
```

### 2. Wrapped Service (Analytics)
**Port:** 5002  
**Purpose:** Provides Spotify Wrapped-style analytics and visualizations

**Features:**
- Yearly wrapped summaries with interactive UI
- Listening personality analysis
- Pattern detection (streaks, peak times, discoveries)
- Beautiful visualizations
- Shareable insights

**Run:**
```bash
cd wrapped_service
python run.py
```

## Shared Components

Both services share:
- **Database** (`shared/`): SQLite database and models
- **Configuration**: Environment variables and config.yaml
- **Data Directory** (`data/`): Database file, CSVs, caches

## Architecture Benefits

1. **Separation of Concerns**: Sync runs continuously, wrapped is on-demand
2. **Independent Scaling**: Each service can be updated independently
3. **Focused Features**: Each service does one thing well
4. **Shared Data**: Both services work with the same listening history

## Quick Start

1. **Set up environment** (see .env.example)
2. **Run initial sync**:
   ```bash
   cd sync_service
   python scripts/sync_lastfm_complete.py
   ```
3. **Start sync service**:
   ```bash
   python run.py
   ```
4. **In another terminal, start wrapped service**:
   ```bash
   cd ../wrapped_service
   python run.py
   ```
5. **Access services**:
   - Sync Monitor: http://localhost:5001
   - Wrapped Analytics: http://localhost:5002

## Development

Each service can be developed and tested independently:
- Sync service focuses on reliability and data integrity
- Wrapped service focuses on user experience and insights