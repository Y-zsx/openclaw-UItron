#!/usr/bin/env python3
"""
Alert Escalation Dashboard Server
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

os.chdir('/root/.openclaw/workspace/ultron')
server = HTTPServer(('0.0.0.0', 18237), CORSRequestHandler)
print("[Dashboard] Alert Escalation Dashboard running on http://localhost:18237/alert_escalation_dashboard.html")
server.serve_forever()