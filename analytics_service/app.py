"""
HTTP layer for the history viewer: one static single-page app plus a JSON API.
"""

import os
import re
import time

from flask import Flask, abort, jsonify, request, send_from_directory

import analytics as A
from store import StoreManager

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def create_app(db_path):
    app = Flask(__name__, static_folder=None)
    manager = StoreManager(db_path, prepare=A.warm)

    def store():
        return manager.get()

    def date_arg(name):
        v = request.args.get(name)
        if v is None or v == '':
            return None
        if not DATE.match(v):
            abort(400, f'{name} must be YYYY-MM-DD')
        return v

    def int_arg(name, default, lo, hi):
        try:
            v = int(request.args.get(name, default))
        except ValueError:
            abort(400, f'{name} must be an integer')
        return max(lo, min(hi, v))

    @app.errorhandler(400)
    @app.errorhandler(404)
    def error(e):
        return jsonify({'error': e.description}), e.code

    @app.after_request
    def timing(resp):
        if request.path.startswith('/api/'):
            resp.headers['Server-Timing'] = f'app;dur={(time.perf_counter() - request.environ["t0"]) * 1000:.1f}'
            resp.headers['Cache-Control'] = 'no-store'
        return resp

    @app.before_request
    def start_timer():
        request.environ['t0'] = time.perf_counter()

    # ---------------------------------------------------------------- pages

    @app.route('/')
    def index():
        return send_from_directory(STATIC, 'index.html')

    @app.route('/static/<path:path>')
    def static_files(path):
        return send_from_directory(STATIC, path)

    # ---------------------------------------------------------------- api

    @app.route('/api/meta')
    def meta():
        return jsonify(A.meta(store()))

    @app.route('/api/timeline')
    def timeline():
        return jsonify(A.timeline(store()))

    @app.route('/api/overview')
    def overview():
        s, start, end = store(), date_arg('start'), date_arg('end')
        return jsonify({
            'summary': A.summary(s, start, end),
            'artists': A.top(s, 'artists', start, end, 15),
            'songs': A.top(s, 'songs', start, end, 15),
            'albums': A.top(s, 'albums', start, end, 10),
            'clock': A.clock(s, start, end),
            'sessions': A.sessions(s, start, end, 5),
        })

    @app.route('/api/on-this-day')
    def on_this_day():
        return jsonify(A.on_this_day(store(), int_arg('month', 1, 1, 12), int_arg('day', 1, 1, 31)))

    @app.route('/api/patterns')
    def patterns():
        s = store()
        return jsonify({'obsessions': A.obsessions(s), 'arcs': A.artist_arcs(s), 'diversity': A.diversity(s)})

    @app.route('/api/year/<int:year>')
    def year(year):
        data = A.year_review(store(), year)
        if data is None:
            abort(404, f'No plays in {year}')
        return jsonify(data)

    @app.route('/api/artist/<int:artist_id>')
    def artist(artist_id):
        s = store()
        if artist_id not in s.artist_by_id:
            abort(404, 'No artist with that id')
        data = dict(A.artist(s, s.artist_by_id[artist_id]))
        data['clock'] = A.clock(s, a=s.artist_by_id[artist_id])
        return jsonify(data)

    @app.route('/api/song/<int:track_id>')
    def song(track_id):
        s = store()
        if track_id not in s.song_by_track:
            abort(404, 'No song with that id')
        return jsonify(A.song(s, s.song_by_track[track_id]))

    @app.route('/api/search')
    def search():
        return jsonify(A.search(store(), request.args.get('q', '')[:100]))

    return app
