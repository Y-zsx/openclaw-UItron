#!/usr/bin/env python3
"""
Agent任务调度Dashboard API服务
端口: 18180
"""

import http.server
import socketserver
import json
import os
from pathlib import Path
import urllib.parse

AGENT_DIR = Path(__file__).parent
PORT = 18182

class QueueDashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        
        # API路由
        if path == '/api/status':
            self.send_json(self.get_status())
        elif path == '/api/stats':
            self.send_json(self.get_stats())
        elif path == '/api/list/pending':
            self.send_json(self.get_list('pending'))
        elif path == '/api/list/running':
            self.send_json(self.get_list('running'))
        elif path == '/api/list/completed':
            self.send_json(self.get_list('completed'))
        elif path == '/api/list/failed':
            self.send_json(self.get_list('failed'))
        elif path == '/api/next':
            self.send_json(self.get_next())
        elif path.startswith('/api/task/'):
            task_id = path.split('/api/task/')[1]
            self.send_json(self.get_task(task_id))
        elif path == '/api/config':
            self.send_json(self.get_config())
        elif path == '/' or path == '/index.html' or path == '/dashboard':
            self.serve_html()
        else:
            self.send_error(404)
    
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body) if body else {}
        
        if path == '/api/create':
            self.send_json(self.create_task(data))
        elif path == '/api/config':
            self.send_json(self.update_config(data))
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def serve_html(self):
        html_file = AGENT_DIR / "queue_dashboard.html"
        if html_file.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(html_file.read_bytes())
        else:
            self.send_error(404)
    
    def get_status(self):
        import subprocess
        result = subprocess.run(
            ['python3', str(AGENT_DIR / 'queue_manager.py'), 'status'],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except:
            return {"error": "Failed to get status"}
    
    def get_stats(self):
        import subprocess
        result = subprocess.run(
            ['python3', str(AGENT_DIR / 'queue_manager.py'), 'stats'],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except:
            return {"error": "Failed to get stats"}
    
    def get_list(self, status):
        import subprocess
        result = subprocess.run(
            ['python3', str(AGENT_DIR / 'queue_manager.py'), 'list', status],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except:
            return []
    
    def get_next(self):
        import subprocess
        result = subprocess.run(
            ['python3', str(AGENT_DIR / 'queue_manager.py'), 'next'],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except:
            return {"status": "no_task"}
    
    def get_task(self, task_id):
        import subprocess
        result = subprocess.run(
            ['python3', str(AGENT_DIR / 'queue_manager.py'), 'task', task_id],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except:
            return {"error": "not_found"}
    
    def get_config(self):
        import subprocess
        result = subprocess.run(
            ['python3', str(AGENT_DIR / 'queue_manager.py'), 'config', 'get'],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except:
            return {"error": "Failed to get config"}
    
    def create_task(self, data):
        import subprocess
        result = subprocess.run(
            ['python3', str(AGENT_DIR / 'queue_manager.py'), 'create', json.dumps(data)],
            capture_output=True, text=True
        )
        try:
            return json.loads(result.stdout)
        except:
            return {"error": "Failed to create task"}
    
    def update_config(self, data):
        import subprocess
        result = subprocess.run(
            ['python3', str(AGENT_DIR / 'queue_manager.py'), 'config', 'update', json.dumps(data)],
            capture_output=True, text=True
        )
        return {"status": "updated"}
    
    def log_message(self, format, *args):
        pass  # 禁用日志

def main():
    with socketserver.TCPServer(("", PORT), QueueDashboardHandler) as httpd:
        print(f"Queue Dashboard API running on http://localhost:{PORT}")
        print(f"Dashboard: http://localhost:{PORT}/dashboard")
        httpd.serve_forever()

if __name__ == "__main__":
    main()