"""
Health checks for the sync service, with macOS notifications.

Each check covers a failure that went unnoticed for months in 2026:
- sync_stuck: the history sync job hung (a token refresh with no timeout), so
  every later run was skipped while scrobbles piled up on Last.fm.
- no_new_plays: Last.fm stopped receiving scrobbles because its Spotify
  connection expired (Spotify refresh tokens now expire after 6 months).
- spotify_auth: this app's own Spotify sign-in expired, so playlists stopped updating.
"""
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Optional

from loguru import logger
from sqlalchemy import func

# Add project root to path for shared imports
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared import DatabaseManager, PlayHistory, SyncStatus

SYNC_STUCK_AFTER = timedelta(minutes=30)
NO_PLAYS_AFTER = timedelta(days=3)
REALERT_EVERY = timedelta(hours=24)
NOTIFICATION_TITLE = 'Spotify Sync'


def _fmt(dt: datetime) -> str:
    return dt.strftime('%b %-d %-I:%M %p')


def find_problems(now_utc: datetime, now_local: datetime,
                  last_sync_utc: Optional[datetime], latest_play_local: Optional[datetime],
                  spotify_ok: bool) -> Dict[str, str]:
    """Return {problem_key: message} for every failing check."""
    problems = {}

    # sync_status.last_sync is naive UTC and is written at the start and end of every run
    if last_sync_utc is None or now_utc - last_sync_utc > SYNC_STUCK_AFTER:
        since = _fmt(last_sync_utc.replace(tzinfo=timezone.utc).astimezone()) if last_sync_utc else 'never'
        problems['sync_stuck'] = (f"History sync hasn't run since {since}; it may be stuck. "
                                  "Restart: launchctl kickstart -k gui/$(id -u)/com.spotify-sync")

    # play_history.played_at is stored as naive *local* time, so compare against local now
    if latest_play_local is None or now_local - latest_play_local > NO_PLAYS_AFTER:
        since = _fmt(latest_play_local) if latest_play_local else 'ever'
        problems['no_new_plays'] = (f"No new scrobbles since {since}. If you've been listening, "
                                    "reconnect Spotify at last.fm/settings/applications")

    if not spotify_ok:
        problems['spotify_auth'] = ("Spotify sign-in expired or revoked; playlists can't update. "
                                    "Reconnect at http://127.0.0.1:5001/auth/spotify")

    return problems


def send_mac_notification(title: str, message: str) -> bool:
    """Show a macOS notification. Returns False (and logs) on failure."""
    try:
        subprocess.run(
            ['osascript',
             '-e', 'on run argv',
             '-e', 'display notification (item 2 of argv) with title (item 1 of argv)',
             '-e', 'end run',
             title, message],
            check=True, timeout=10, capture_output=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


class HealthMonitor:
    def __init__(self, spotify_client=None, db=None,
                 notify: Callable[[str, str], bool] = send_mac_notification):
        if spotify_client is None:
            from api.spotify_client import SpotifyClient
            spotify_client = SpotifyClient()
        self.spotify = spotify_client
        self.db = db or DatabaseManager()
        self.notify = notify
        self.problems: Dict[str, str] = {}
        self.last_check: Optional[datetime] = None
        self._streak: Dict[str, int] = {}  # consecutive checks each problem has been seen
        self._last_alert: Dict[str, datetime] = {}

    def check(self) -> Dict[str, str]:
        """Run all checks and send any due notifications"""
        with self.db.session_scope() as session:
            status = session.query(SyncStatus).filter_by(source='lastfm').first()
            last_sync = status.last_sync if status else None
            latest_play = session.query(func.max(PlayHistory.played_at)).scalar()

        problems = find_problems(datetime.utcnow(), datetime.now(), last_sync, latest_play,
                                 self.spotify.ensure_authenticated())
        self.process(problems, datetime.now())
        return problems

    def process(self, problems: Dict[str, str], now: datetime):
        """Track how long each problem has persisted and notify when due"""
        for key in list(self._streak):
            if key not in problems:
                logger.info(f"Health check: {key} resolved")
                del self._streak[key]
                self._last_alert.pop(key, None)

        for key, message in problems.items():
            self._streak[key] = self._streak.get(key, 0) + 1
            logger.warning(f"Health check: {key}: {message}")
            # Require two consecutive checks so a blip (network drop, Mac waking from
            # sleep before the sync job catches up) doesn't alert; then remind daily.
            last = self._last_alert.get(key)
            if self._streak[key] >= 2 and (last is None or now - last >= REALERT_EVERY):
                if self.notify(NOTIFICATION_TITLE, message):
                    self._last_alert[key] = now

        self.problems = problems
        self.last_check = now
