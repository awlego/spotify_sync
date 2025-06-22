#!/usr/bin/env python3
"""
Spotify Sync Automated - Main Entry Point

This script starts the web server and scheduler for automated Spotify playlist syncing.
"""

import os
import sys
import argparse
from loguru import logger

from src.web.app import create_app
from src.core.config import get_config


def setup_logging(log_level: str = "INFO"):
    """Configure logging"""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(
        "logs/spotify_sync_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )


def main():
    parser = argparse.ArgumentParser(description='Spotify Sync Automated')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5001, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--no-scheduler', action='store_true', help='Disable automatic scheduler')
    args = parser.parse_args()
    
    # Setup logging
    os.makedirs('logs', exist_ok=True)
    setup_logging(args.log_level)
    
    logger.info("Starting Spotify Sync Automated")
    
    # Load configuration
    config = get_config()
    logger.info(f"Configuration loaded from {config.config_path}")
    
    # Create Flask app
    app = create_app()
    
    # Disable scheduler if requested
    if args.no_scheduler:
        logger.warning("Scheduler disabled by command line flag")
        app.config['SCHEDULER_DISABLED'] = True
    
    # Run the app
    logger.info(f"Starting web server on {args.host}:{args.port}")
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug
    )


if __name__ == '__main__':
    main()