#!/usr/bin/env python3
"""
Continue the Last.fm sync from where it left off
"""

import sys
import os
import subprocess

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import DatabaseManager


def main():
    db = DatabaseManager()
    
    with db.session_scope() as session:
        progress = db.get_sync_progress(session, 'lastfm_full')
        
        print("=== Last.fm Sync Status ===")
        print(f"Status: {progress.status}")
        print(f"Current chunk: {progress.current_chunk}")
        print(f"Progress: {progress.total_chunks_completed}/76 chunks ({progress.total_tracks_synced:,} tracks)")
        
        if progress.status == 'completed':
            print("\nSync is already complete!")
            return
        
        if progress.status == 'error':
            print(f"\nSync stopped due to error: {progress.last_error}")
            response = input("Reset and start fresh? (y/N): ")
            if response.lower() == 'y':
                subprocess.run([sys.executable, "sync_lastfm_complete_v2.py", "--reset"])
                return
        
        print("\nContinuing sync from where it left off...")
        print("Press Ctrl+C to stop at any time (progress will be saved)")
        
        # Run the sync
        subprocess.run([sys.executable, "sync_lastfm_complete_v2.py"])


if __name__ == "__main__":
    main()