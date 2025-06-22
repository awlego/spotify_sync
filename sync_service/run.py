#!/usr/bin/env python3
"""
Spotify Sync Service - Main Entry Point

This service syncs Last.fm listening history to a local database
and maintains smart Spotify playlists.
"""

import os
import sys
import argparse
from loguru import logger

# Add parent directory for shared imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import create_app
from config import get_config


def setup_logging(log_level: str = "INFO"):
    """Configure logging"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )
    logger.add(
        "../logs/sync_service_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=log_level
    )


def main():
    parser = argparse.ArgumentParser(description='Spotify Sync Service')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5001, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--no-scheduler', action='store_true', help='Disable automatic scheduler')
    args = parser.parse_args()
    
    # Setup logging
    os.makedirs('../logs', exist_ok=True)
    setup_logging(args.log_level)
    
    logger.info("Starting Spotify Sync Service")
    
    # Load configuration
    config = get_config()
    logger.info(f"Configuration loaded")
    
    # Create Flask app
    app = create_app()
    
    # Disable scheduler if requested
    if args.no_scheduler:
        logger.warning("Scheduler disabled by command line flag")
        app.config['SCHEDULER_DISABLED'] = True
    
    # Run the app
    logger.info(f"Starting sync service on {args.host}:{args.port}")
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug
    )


if __name__ == '__main__':
    main()