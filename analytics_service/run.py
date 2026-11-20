#!/usr/bin/env python3
"""
Listening history viewer.

Usage (from the project root):
  env3.10/bin/python analytics_service/run.py            # http://127.0.0.1:5002
  env3.10/bin/python analytics_service/run.py --port 5003 --db path/to/spotify_sync.db
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from app import create_app  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Listening history viewer')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5002, help='Port to bind to')
    parser.add_argument('--db', default=os.path.join(ROOT, 'data', 'db', 'spotify_sync.db'),
                        help='SQLite database (opened read-only)')
    parser.add_argument('--debug', action='store_true', help='Enable Flask debug mode')
    args = parser.parse_args()

    app = create_app(args.db)
    print(f'Listening history viewer on http://{args.host}:{args.port}')
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=args.debug, threaded=True)


if __name__ == '__main__':
    main()
