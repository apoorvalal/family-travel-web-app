#!/usr/bin/env python3
"""Small, persistent travel dashboard, with optional private-network reverse-proxy hosting."""
import argparse
import json
import mimetypes
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

PREFIX = '/apps/travel'
STATIC = Path(__file__).parent / 'static'
LOCK = threading.RLock()


def atomic_write(path, text):
    temp = path.with_name('.' + path.name + '.tmp')
    with temp.open('w', encoding='utf-8') as file:
        file.write(text)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, path)


def read_state():
    return json.loads(STATE.read_text(encoding='utf-8'))


def sync_todo(state):
    item = next(i for i in state['items'] if i['id'] == 'visitor-cards')
    path = DATA / 'todo.md'
    if path.exists():
        original = path.read_text(encoding='utf-8')
        updated = re.sub(r'^- \[[ xX]\]( \*\*28 May 2030 — File fictional visitor cards)',
                         '- [' + ('x' if item['done'] else ' ') + r']\1', original, count=1, flags=re.M)
        if updated != original:
            atomic_write(path, updated)


def export_markdown(state):
    lines = ['# ' + state['trip']['title'] + ' — shared travel checklist', '', state['trip']['dates'], '']
    for section in ('packing', 'admin'):
        lines += ['## ' + ('Packing' if section == 'packing' else 'Travel admin'), '']
        groups = list(dict.fromkeys(i['group'] for i in state['items'] if i['section'] == section))
        for group in groups:
            lines += ['### ' + group, '']
            for item in state['items']:
                if item['section'] == section and item['group'] == group:
                    lines.append('- [' + ('x' if item['done'] else ' ') + '] ' + item['text'])
                    if item.get('note'):
                        lines.append('  - ' + item['note'])
            lines.append('')
    return '\n'.join(lines)


class Handler(BaseHTTPRequestHandler):
    server_version = 'Travel/1.0'

    def log_message(self, fmt, *args):
        # Request bodies and booking references must not enter logs.
        pass

    def route(self):
        path = unquote(urlparse(self.path).path)
        if path == PREFIX:
            return '__redirect__'
        if path.startswith(PREFIX + '/'):
            path = path[len(PREFIX):]
        return path

    def send(self, status, data, content_type='application/json; charset=utf-8', filename=None):
        if isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'private, no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        if self.command != 'HEAD':
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def json(self, status, value):
        self.send(status, json.dumps(value, ensure_ascii=False))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        route = self.route()
        try:
            if route == '__redirect__':
                self.send_response(302)
                self.send_header('Location', PREFIX + '/')
                self.send_header('Content-Length', '0')
                self.end_headers()
            elif route == '/health':
                self.json(200, {'ok': True})
            elif route == '/api/state':
                with LOCK:
                    self.json(200, read_state())
            elif route in ('/', '/index.html', '/style.css', '/app.js', '/icon.svg'):
                path = STATIC / ('index.html' if route == '/' else route[1:])
                self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            elif route == '/export/checklist.md':
                with LOCK:
                    self.send(200, export_markdown(read_state()), 'text/markdown; charset=utf-8', 'travel-checklist.md')
            elif route == '/todo.md':
                self.send(200, (DATA / 'todo.md').read_bytes(), 'text/markdown; charset=utf-8', 'todo.md')
            elif route.startswith('/boarding-passes/'):
                name = route[len('/boarding-passes/'):]
                with LOCK:
                    passes = read_state()['trip'].get('boardingPasses', {})
                    names = {item['file'] for flight in passes.get('flights', []) for item in flight['passes']}
                    if passes.get('bundle'):
                        names.add(passes['bundle'])
                if name not in names or Path(name).name != name:
                    return self.json(404, {'error': 'Boarding pass not found'})
                self.send(200, (DATA / name).read_bytes(), 'application/pdf', name)
            elif route.startswith('/tickets/'):
                name = route[len('/tickets/'):]
                with LOCK:
                    names = {ticket['file'] for booking in read_state()['trip']['bookings'] for ticket in booking['tickets']}
                if name not in names or Path(name).name != name:
                    return self.json(404, {'error': 'Ticket not found'})
                self.send(200, (DATA / name).read_bytes(), 'application/pdf', name)
            else:
                self.json(404, {'error': 'Not found'})
        except (OSError, ValueError):
            self.json(500, {'error': 'The travel data could not be loaded. Please retry.'})

    def do_POST(self):
        if self.route() != '/api/items':
            return self.json(404, {'error': 'Not found'})
        if self.headers.get('Origin') not in ORIGINS or self.headers.get('X-Travel-App') != '1':
            return self.json(403, {'error': 'Please use the travel app to make changes.'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.json(415, {'error': 'JSON required'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8192:
                return self.json(413, {'error': 'Request too large'})
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError()
            with LOCK:
                state = read_state()
                action = body.get('action')
                if action == 'add':
                    text = body.get('text', '')
                    section = body.get('section')
                    if not isinstance(text, str) or not text.strip() or len(text) > 500 or section not in ('packing', 'admin'):
                        return self.json(400, {'error': 'Enter an item of 1–500 characters.'})
                    if len(state['items']) >= 500:
                        return self.json(400, {'error': 'Checklist is full.'})
                    state['items'].append({'id': 'custom-' + uuid.uuid4().hex, 'text': text.strip(), 'section': section,
                                           'group': 'Your additions', 'done': False, 'custom': True, 'source': 'family'})
                elif action in ('toggle', 'remove'):
                    item = next((i for i in state['items'] if i['id'] == body.get('id')), None)
                    if item is None:
                        return self.json(404, {'error': 'Item not found'})
                    if action == 'remove':
                        if not item.get('custom'):
                            return self.json(400, {'error': 'Only custom additions can be removed.'})
                        state['items'].remove(item)
                    else:
                        if type(body.get('done')) is not bool:
                            return self.json(400, {'error': 'A checked state is required.'})
                        item['done'] = body['done']
                else:
                    return self.json(400, {'error': 'Unknown action'})
                state['revision'] += 1
                state['updatedAt'] = datetime.now(timezone.utc).isoformat()
                atomic_write(STATE, json.dumps(state, ensure_ascii=False, indent=2) + '\n')
                if body.get('id') == 'visitor-cards':
                    sync_todo(state)
                self.json(200, state)
        except (ValueError, TypeError):
            self.json(400, {'error': 'Invalid request'})
        except OSError:
            self.json(500, {'error': 'Could not save this change. Please retry.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parent / 'demo-data')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--origin', action='append', default=[], help='Additional allowed browser origin, e.g. https://travel.example.com')
    args = parser.parse_args()
    DATA = args.data.resolve()
    from seed import initialize
    initialize(DATA)
    STATE = DATA / 'travel-app.json'
    ORIGINS = {f'http://127.0.0.1:{args.port}', f'http://localhost:{args.port}', *args.origin}
    with LOCK:
        sync_todo(read_state())
    print(f'Travel app listening on loopback port {args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
