from http.server import BaseHTTPRequestHandler
import json
import sys

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "message": "BaseHTTPRequestHandler works on Vercel!",
            "python": sys.version,
            "path": self.path
        }).encode('utf-8'))
