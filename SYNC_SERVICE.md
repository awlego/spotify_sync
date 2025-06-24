# Spotify Sync Service Management

## Overview
The Spotify Sync Service automatically syncs your Last.fm listening history to a local database and updates Spotify playlists based on your listening patterns. It runs as a background service on macOS using launchd.

## Service Status

### Check if service is running
```bash
launchctl list | grep spotify-sync
```

### View service logs
```bash
# Standard output
tail -f logs/sync_service_stdout.log

# Error output
tail -f logs/sync_service_stderr.log
```

### Check sync status in database
```bash
sqlite3 data/db/spotify_sync.db "SELECT * FROM sync_status ORDER BY last_sync DESC LIMIT 5;"
```

## Managing the Service

### Start the service
```bash
launchctl load ~/Library/LaunchAgents/com.spotify-sync.plist
```

### Stop the service
```bash
launchctl unload ~/Library/LaunchAgents/com.spotify-sync.plist
```

### Restart the service
```bash
launchctl unload ~/Library/LaunchAgents/com.spotify-sync.plist
launchctl load ~/Library/LaunchAgents/com.spotify-sync.plist
```

### Run manually (for testing)
```bash
bash sync_service/run_with_env.sh
```

## Web Interface

The sync service provides a web interface at http://localhost:5001/

Features:
- View sync status and history
- Manually trigger syncs
- Configure sync settings
- View listening analytics

## Configuration

### Environment Variables
Edit `.env` file to configure:
- Last.fm API credentials
- Spotify API credentials
- Playlist IDs

### Sync Settings
Edit `config.yaml` to configure:
- Sync interval (default: 5 minutes)
- Playlist update settings
- Data retention policies

## Troubleshooting

### Service won't start
1. Check port 5001 is available: `lsof -i :5001`
2. Verify environment variables in `.env`
3. Check logs for errors

### Sync is failing
1. Check Last.fm API key is valid
2. Verify network connectivity
3. Check database permissions
4. Review error logs for specific issues

### Known Issues
- The service currently has a 'track' KeyError that prevents Last.fm syncing
- This needs to be fixed in the sync_service code

## Uninstalling

To completely remove the service:
```bash
# Stop and unload service
launchctl unload ~/Library/LaunchAgents/com.spotify-sync.plist

# Remove plist file
rm ~/Library/LaunchAgents/com.spotify-sync.plist

# Remove local plist copy
rm com.spotify-sync.plist
```