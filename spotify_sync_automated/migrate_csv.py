#!/usr/bin/env python3
"""
Migration script to import existing CSV listening history into the database
"""

import sys
import os
import pandas as pd
from datetime import datetime
import pytz
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.database import DatabaseManager
from src.core.config import get_config


def migrate_csv_data(csv_path: str, lastfm_username: str):
    """Import CSV listening history into database"""
    logger.info(f"Starting CSV migration from {csv_path}")
    
    # Read CSV
    header_names = ["artist", "album", "song", "date_played"]
    df = pd.read_csv(csv_path, header=None, names=header_names)
    
    # Process dates
    df['date_played'] = pd.to_datetime(df['date_played'], utc=True, infer_datetime_format=True)
    df = df.dropna()
    
    logger.info(f"Found {len(df)} plays to import")
    
    # Initialize database
    db = DatabaseManager()
    
    imported = 0
    with db.session_scope() as session:
        for idx, row in df.iterrows():
            try:
                # Get or create track
                track = db.get_or_create_track(
                    session,
                    name=row['song'],
                    artist_name=row['artist'],
                    album_name=row['album'] if pd.notna(row['album']) else None
                )
                
                # Add play history
                play = db.add_play(
                    session,
                    track,
                    row['date_played'],
                    source='lastfm'
                )
                
                if play:
                    imported += 1
                
                # Commit every 1000 records
                if imported % 1000 == 0:
                    session.commit()
                    logger.info(f"Imported {imported} plays...")
                    
            except Exception as e:
                logger.error(f"Error importing row {idx}: {e}")
                continue
    
    logger.info(f"Migration complete! Imported {imported} plays")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import CSV listening history')
    parser.add_argument('csv_file', help='Path to Last.fm CSV export')
    parser.add_argument('--username', help='Last.fm username', 
                       default=os.getenv('LASTFM_USERNAME'))
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_file):
        logger.error(f"CSV file not found: {args.csv_file}")
        sys.exit(1)
    
    migrate_csv_data(args.csv_file, args.username)


if __name__ == '__main__':
    # Setup logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    main()