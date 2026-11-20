# Spotify Sync

Automatically sync your Last.fm listening history and maintain smart Spotify playlists based on your actual listening patterns.

## Overview

This project fetches your complete listening history from Last.fm and uses it to automatically generate and update Spotify playlists:
- **Most Listened To**: Your top 50 all-time tracks by play count
- **Recent Favorites**: Top 25 tracks from the last 30 days
- **Binged Songs**: Top 25 songs you've played 3+ times in a single day

## Features

### Core Sync Features
- ✅ Fetches listening history from Last.fm
- ✅ Automatic syncing every 5 minutes
- ✅ Smart playlist generation based on listening patterns
- ✅ Web dashboard for monitoring and control
- ✅ SQLite database for local history storage
- ✅ Resume capability for interrupted syncs
- ✅ Comprehensive error handling and logging

### Listening history viewer
- 📈 **Whole-history timeline** - every week since your first play, labelled with the artist that defined each year; drag across it to scope the page to any range
- 🏆 **Most played** - artists, songs (versions merged) and albums for any range, plus when in the week you listen and how long your sessions run
- 🔁 **Patterns** - your heaviest single-week rotations, artists who grew on you, evergreens, artists you drifted from or came back to, and how wide your listening ran each year
- 📅 **Years** - a calendar of every day, month-by-month favourites and the artists you found that year
- 🎤 **Artist and song pages** - lifetime plays, first listen, when in the day you play them, and the artists you play alongside them

## Project Structure

```
spotify_sync/
├── src/                     # Source code
│   ├── api/                # External API clients
│   ├── core/               # Database and configuration
│   ├── services/           # Business logic
│   ├── scheduler/          # Automated tasks
│   └── web/                # Flask web application
├── analytics_service/       # Listening history viewer (read-only)
│   ├── store.py            # In-memory snapshot of the history
│   ├── analytics.py        # Analytics over a snapshot
│   ├── app.py              # JSON API
│   └── static/             # Single-page web app
├── scripts/                 # Utility and maintenance scripts
├── templates/               # HTML templates
├── static/                  # CSS/JS assets
├── tests/                   # Test suite
├── data/                    # Data files (gitignored)
│   ├── csv/                # CSV exports
│   ├── cache/              # API caches
│   └── db/                 # SQLite database
├── notebooks/               # Jupyter notebooks (archived)
├── logs/                    # Application logs
├── run.py                   # Main entry point
├── config.yaml             # Configuration file
└── requirements.txt        # Python dependencies
```

## Setup

See the [detailed setup guide](docs/README-automated.md) for full instructions.

## Quick Start

1. Clone the repository
2. Set up environment variables (see `.env.example`)
3. Run the automated system:
   ```bash
   python run.py
   ```
4. Access the web dashboard at http://localhost:5001

### Running the history viewer

From the project root:
```bash
env3.10/bin/python analytics_service/run.py
```
Then visit http://localhost:5002. The viewer opens the database read-only and picks up new plays from the sync job on its own.

## Data Flow

```
Last.fm API → SQLite Database → Spotify Playlists
     ↓              ↓                    ↑
(listening)    (storage)          (auto-update)
```

## Requirements

- Python 3.10+
- Last.fm API credentials
- Spotify API credentials
- SQLite

## Legacy Jupyter Notebook

The original Jupyter notebook implementation has been archived in the `notebooks/` directory.