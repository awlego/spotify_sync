#!/usr/bin/env python3
"""
Database migration script to add new fields and tables
"""

import sys
import os
from sqlalchemy import text
from loguru import logger

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.database import DatabaseManager
from src.core.models import Base, SyncProgress, PlayHistory


def migrate_database():
    """Run database migrations"""
    logger.info("Running database migrations...")
    
    db = DatabaseManager()
    
    with db.engine.connect() as conn:
        # Check if SyncProgress table exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sync_progress'"
        ))
        if not result.fetchone():
            logger.info("Creating sync_progress table...")
            SyncProgress.__table__.create(db.engine)
        
        # Check if lastfm_url column exists in play_history
        result = conn.execute(text(
            "PRAGMA table_info(play_history)"
        ))
        columns = [row[1] for row in result]
        
        if 'lastfm_url' not in columns:
            logger.info("Adding lastfm_url column to play_history...")
            conn.execute(text(
                "ALTER TABLE play_history ADD COLUMN lastfm_url TEXT"
            ))
            conn.execute(text(
                "CREATE INDEX idx_lastfm_url ON play_history(lastfm_url)"
            ))
            conn.commit()
    
    logger.success("Database migration complete!")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    migrate_database()