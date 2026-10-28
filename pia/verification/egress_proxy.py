"""Tiny outbound-connection logger (verification only).

Point HTTP_PROXY / HTTPS_PROXY of the Open WebUI process at this proxy. It records
every destination host the process tries to reach (JSONL) and answers 403, so
nothing actually leaves the machine. Loopback targets should be listed in NO_PROXY.

Usage: python egress_proxy.py <port> <log.jsonl>
"""
import json
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3128
LOG = sys.argv[2] if len(sys.argv) > 2 else 'egress.jsonl'
LOCK = threading.Lock()


def log(entry: dict) -> None:
    entry['t'] = time.time()
    with LOCK, open(LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')


class Handler(BaseHTTPRequestHandler):
    def _deny(self):
        self.send_response(403)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_CONNECT(self):
        log({'method': 'CONNECT', 'target': self.path})
        self._deny()

    def do_GET(self):
        log({'method': 'GET', 'target': self.path, 'user_agent': self.headers.get('User-Agent')})
        self._deny()

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        size = len(self.rfile.read(n)) if n else 0
        log({'method': 'POST', 'target': self.path, 'body_bytes': size, 'user_agent': self.headers.get('User-Agent')})
        self._deny()

    do_PUT = do_DELETE = do_HEAD = do_OPTIONS = do_GET

    def log_message(self, *a):
        pass


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    with Server(('127.0.0.1', PORT), Handler) as s:
        s.serve_forever()
