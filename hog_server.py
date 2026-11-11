"""Run the private-room relay: python hog_server.py --host 127.0.0.1 --port 8765.

Use --certfile and --keyfile together for direct HTTPS. Rooms live in memory.
"""

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ssl
import threading
import time

from hog import VERSION
from hog_online import PROTOCOL, Rooms, RoomError

MAX_BODY = 8192


class RelayServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True

    def __init__(self, address, rooms=None):
        self.rooms = rooms or Rooms()
        self.slots = threading.BoundedSemaphore(32)
        self.rates = {}
        self.rate_lock = threading.Lock()
        super().__init__(address, RelayHandler)

    def process_request(self, connection, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(connection)
            return
        try:
            super().process_request(connection, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, connection, address):
        try:
            super().process_request_thread(connection, address)
        finally:
            self.slots.release()

    def service_actions(self):
        self.rooms.tick()

    def allowed(self, ip):
        now = time.monotonic()
        with self.rate_lock:
            if ip not in self.rates and len(self.rates) >= 4096:
                self.rates = {key: stamps for key, stamps in self.rates.items() if stamps and now - stamps[-1] < 10}
                if len(self.rates) >= 4096:
                    return False
            stamps = self.rates.setdefault(ip, deque())
            while stamps and now - stamps[0] > 10:
                stamps.popleft()
            if len(stamps) >= 100:
                return False
            stamps.append(now)
            return True


class RelayHandler(BaseHTTPRequestHandler):
    server_version = 'HogRelay/1'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, _format, *args):
        # Tokens and display names never enter default access logs.
        pass

    def reply(self, status, data):
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (OSError, TimeoutError):
            pass

    def do_GET(self):
        if self.path != '/health':
            self.reply(404, {'error': 'Not found.'})
            return
        self.reply(200, {'protocol': PROTOCOL, 'version': VERSION, 'status': 'ok'})

    def do_POST(self):
        if not self.server.allowed(self.client_address[0]):
            self.reply(429, {'error': 'Too many requests. Retry shortly.'})
            return
        try:
            if self.headers.get('Transfer-Encoding'):
                raise RoomError('Chunked requests are not supported.')
            if self.headers.get_content_type() != 'application/json':
                raise RoomError('Send application/json.', 415)
            length = int(self.headers.get('Content-Length', '-1'))
            if not 0 < length <= MAX_BODY:
                raise RoomError('Request body is missing or too large.', 413)
            body = self.rfile.read(length)
            if len(body) != length:
                raise RoomError('Incomplete request body.')
            payload = json.loads(body)
            if not self.path.startswith('/api/') or '/' in self.path[5:] or '?' in self.path:
                raise RoomError('Unknown endpoint.', 404)
            result = self.server.rooms.request(self.path[5:], payload)
            self.reply(200, result)
        except RoomError as error:
            self.reply(error.status, {'error': str(error)})
        except (ValueError, UnicodeError, TypeError):
            self.reply(400, {'error': 'Malformed JSON request.'})
        except (TimeoutError, OSError):
            self.close_connection = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--certfile')
    parser.add_argument('--keyfile')
    parser.add_argument('--max-rooms', type=int, default=100)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535 or not 1 <= args.max_rooms <= 1000:
        parser.error('Use a port from 0-65535 and 1-1000 rooms.')
    if bool(args.certfile) != bool(args.keyfile):
        parser.error('Provide --certfile and --keyfile together.')
    server = RelayServer((args.host, args.port), Rooms(max_rooms=args.max_rooms))
    scheme = 'http'
    if args.certfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(args.certfile, args.keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
        scheme = 'https'
    print(f'Hog relay {VERSION}: {scheme}://{args.host}:{server.server_address[1]}', flush=True)
    print('Private rooms are temporary; stopping this server removes them.', flush=True)
    try:
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
