#!/usr/bin/env python3

import http.server
import socketserver
import json
from datetime import datetime
import threading

PORT = 8080
executed_jobs = []
lock = threading.Lock()

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/webhook':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            try:
                data = json.loads(body) if body else {}
                
                with lock:
                    executed_jobs.append({
                        'timestamp': datetime.now().isoformat(),
                        'data': data
                    })
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'success'}).encode())
                
            except Exception as e:
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == '/stats':
            with lock:
                stats = {
                    'total_executed': len(executed_jobs),
                    'first_job': executed_jobs[0] if executed_jobs else None,
                    'last_job': executed_jobs[-1] if executed_jobs else None
                }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(stats, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), WebhookHandler) as httpd:
        print(f"Webhook server listening on port {PORT}")
        print(f"Endpoint: http://localhost:{PORT}/webhook")
        print(f"Stats: http://localhost:{PORT}/stats")
        httpd.serve_forever()
