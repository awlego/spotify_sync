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

### 2. History viewer (analytics_service)
**Port:** 5002  
**Purpose:** Browse and analyse the whole listening history

**Features:**
- Whole-history timeline with a draggable date range
- Most played artists, songs and albums for any range
- Patterns: heaviest rotations, long arcs, breadth of listening
- Year pages, artist pages and song pages
- Opens the database read-only; reloads when the sync job adds plays

**Run (from the project root):**
```bash
env3.10/bin/python analytics_service/run.py
```

## Shared Components

Both services share:
- **Database** (`shared/`): SQLite database and models
- **Configuration**: Environment variables and config.yaml
- **Data Directory** (`data/`): Database file, CSVs, caches

## Architecture Benefits

1. **Separation of Concerns**: Sync runs continuously, the viewer is on-demand
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
4. **In another terminal, start the history viewer** (from the project root):
   ```bash
   env3.10/bin/python analytics_service/run.py
   ```
5. **Access services**:
   - Sync Monitor: http://localhost:5001
   - History viewer: http://localhost:5002

## Development

Each service can be developed and tested independently:
- Sync service focuses on reliability and data integrity
- The history viewer focuses on fast, honest analytics and a pleasant experience