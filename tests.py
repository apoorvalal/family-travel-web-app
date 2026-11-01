"""Integration checks using only disposable, generated fictional data."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from seed import initialize

ROOT = Path(__file__).resolve().parent


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.origin = f'http://127.0.0.1:{cls.port}'
        cls.start()

    @classmethod
    def start(cls):
        cls.process = subprocess.Popen([sys.executable, '-B', str(ROOT / 'server.py'), '--data', str(cls.data), '--port', str(cls.port)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                with urlopen(cls.origin + '/health', timeout=.5) as r:
                    if r.status == 200:
                        return
            except (OSError, URLError):
                if cls.process.poll() is not None:
                    raise RuntimeError(cls.process.stderr.read().decode())
                time.sleep(.04)
        raise RuntimeError('Demo server failed to start')

    @classmethod
    def stop(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.process.stderr.close()

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.tmp.cleanup()

    def get(self, path):
        with urlopen(self.origin + path, timeout=5) as r:
            return r.read(), r.headers

    def state(self):
        return json.loads(self.get('/api/state')[0])

    def post(self, body, origin=None):
        req = Request(self.origin + '/api/items', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Origin': origin or self.origin, 'X-Travel-App': '1'})
        with urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    def test_seed_is_fictional_complete_and_idempotent(self):
        s = self.state()
        self.assertEqual(s['trip']['people'], ['Homer', 'Marge', 'Bart', 'Lisa', 'Maggie'])
        self.assertEqual(len(s['trip']['flights']), 6)
        towns = [s['trip']['flights'][0]['fromCity']] + [f['toCity'] for f in s['trip']['flights']]
        self.assertEqual(towns, ['Springfield', 'Brockway', 'Terror Lake', 'Cypress Creek', 'Ogdenville', 'North Haverbrook', 'Springfield'])
        before = (self.data / 'travel-app.json').read_bytes()
        self.assertFalse(initialize(self.data))
        self.assertEqual(before, (self.data / 'travel-app.json').read_bytes())

    def test_all_ticket_and_boarding_pdfs_open_inline(self):
        s = self.state()
        paths = ['/tickets/' + i['file'] for b in s['trip']['bookings'] for i in b['tickets']]
        bp = s['trip']['boardingPasses']
        paths += ['/boarding-passes/' + i['file'] for b in bp['flights'] for i in b['passes']]
        self.assertEqual(len(paths), 20)
        paths.append('/boarding-passes/' + bp['bundle'])
        for prefix in ('', '/apps/travel'):
            for path in paths:
                with self.subTest(prefix=prefix, path=path):
                    raw, headers = self.get(prefix + path)
                    self.assertTrue(raw.startswith(b'%PDF-1.4'))
                    self.assertTrue(raw.rstrip().endswith(b'%%EOF'))
                    self.assertIn(b'FICTIONAL SAMPLE', raw)
                    self.assertEqual(headers['Content-Type'], 'application/pdf')
                    self.assertEqual(headers['Content-Disposition'], f'inline; filename="{path.rsplit("/", 1)[1]}"')
        bundle, _ = self.get('/boarding-passes/' + bp['bundle'])
        self.assertEqual(bundle.count(b'/Type /Page '), 10)

    def test_custom_add_escape_export_and_remove(self):
        literal = 'Spare donut <b>not markup</b>'
        added = self.post({'action': 'add', 'text': literal, 'section': 'packing'})
        item = next(i for i in added['items'] if i['text'] == literal)
        self.assertTrue(item['custom'])
        self.post({'action': 'toggle', 'id': item['id'], 'done': True})
        exported, headers = self.get('/export/checklist.md')
        self.assertIn(('- [x] ' + literal).encode(), exported)
        self.assertEqual(headers['Content-Disposition'], 'attachment; filename="travel-checklist.md"')
        removed = self.post({'action': 'remove', 'id': item['id']})
        self.assertFalse(any(i['id'] == item['id'] for i in removed['items']))

    def test_todo_checkbox_mirror_and_restore(self):
        for value in (True, False):
            self.post({'action': 'toggle', 'id': 'visitor-cards', 'done': value})
            note, headers = self.get('/todo.md')
            self.assertIn(f'- [{"x" if value else " "}] **28 May 2030'.encode(), note)
            self.assertEqual(headers['Content-Disposition'], 'attachment; filename="todo.md"')

    def test_restart_persistence_and_mirror_repair(self):
        original = next(i for i in self.state()['items'] if i['id'] == 'donuts')['done']
        self.post({'action': 'toggle', 'id': 'donuts', 'done': not original})
        self.stop()
        self.start()
        self.assertEqual(next(i for i in self.state()['items'] if i['id'] == 'donuts')['done'], not original)
        self.post({'action': 'toggle', 'id': 'donuts', 'done': original})
        # Startup repairs an interrupted secondary-note write from authoritative state.
        self.stop()
        p = self.data / 'todo.md'
        p.write_text(p.read_text(encoding='utf-8').replace('- [ ]', '- [x]'), encoding='utf-8')
        self.start()
        self.assertIn(b'- [ ] **28 May 2030', self.get('/todo.md')[0])

    def test_cross_origin_and_invalid_input(self):
        with self.assertRaises(HTTPError) as e:
            self.post({'action': 'toggle', 'id': 'donuts', 'done': True}, 'https://example.invalid')
        self.assertEqual(e.exception.code, 403)
        e.exception.close()
        for body in ({'action': 'toggle', 'id': 'donuts', 'done': 'true'}, {'action': 'add', 'text': '', 'section': 'packing'}, {'action': 'remove', 'id': 'donuts'}):
            with self.assertRaises(HTTPError) as e:
                self.post(body)
            self.assertEqual(e.exception.code, 400)
            e.exception.close()

    def test_restricted_routes_and_prefix(self):
        for path in ('/travel-app.json', '/tickets/server.py', '/boarding-passes/unknown.pdf', '/.git/config', '/tickets/../todo.md'):
            with self.assertRaises(HTTPError) as e:
                self.get(path)
            self.assertEqual(e.exception.code, 404)
            e.exception.close()
        self.assertEqual(json.loads(self.get('/apps/travel/api/state')[0])['trip']['people'][0], 'Homer')
        self.assertIn(b'Springfield', self.get('/apps/travel/')[0])
        _, headers = self.get('/')
        self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
        self.assertEqual(headers['Referrer-Policy'], 'no-referrer')


if __name__ == '__main__':
    unittest.main(verbosity=2)
