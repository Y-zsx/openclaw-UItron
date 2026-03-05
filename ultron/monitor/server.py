#!/usr/bin/env python3
"""奥创实时监控面板服务器"""
import http.server
import socketserver
import json
import urllib.request
import urllib.error
from functools import partial

PORT = 18123
ALERT_API = 'http://localhost:18122'

class MonitorHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            try:
                with urllib.request.urlopen(ALERT_API + '/stats', timeout=5) as resp:
                    data = resp.read()
                self.wfile.write(data)
            except Exception as e:
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        elif self.path == '/api/alerts':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            try:
                with urllib.request.urlopen(ALERT_API + '/alerts', timeout=5) as resp:
                    data = resp.read()
                self.wfile.write(data)
            except Exception as e:
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            super().do_GET()
    
    def log_message(self, format, *args):
        pass  # 禁用日志

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), MonitorHandler) as httpd:
        print(f"🦞 奥创监控面板: http://localhost:{PORT}")
        print(f"📊 告警API: {ALERT_API}")
        httpd.serve_forever()