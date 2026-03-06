#!/usr/bin/env python3
"""
系统监控增强版API
为system-monitor-dashboard-enhanced.html提供数据
端口: 18107
"""

import json
import psutil
import logging
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_PORT = 18107
DASHBOARD_FILE = '/root/.openclaw/workspace/ultron/system-monitor-dashboard-enhanced.html'

class SystemMonitorAPI(BaseHTTPRequestHandler):
    """系统监控API处理器"""
    
    def log_message(self, format, *args):
        logger.debug(format % args)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/' or path == '/status':
            self.send_json_response({
                'status': 'ok',
                'service': 'system-monitor-api',
                'port': API_PORT,
                'dashboard': f'http://localhost:{API_PORT}/dashboard.html',
                'timestamp': datetime.now().isoformat()
            })
        
        elif path == '/dashboard.html' or path == '/dashboard':
            # Serve the dashboard HTML
            try:
                with open(DASHBOARD_FILE, 'r') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content.encode())
            except FileNotFoundError:
                self.send_error_response(404, 'Dashboard not found')
            return
        
        elif path == '/api/metrics':
            # Get system metrics
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()
            
            self.send_json_response({
                'cpu': cpu,
                'memory': mem.percent,
                'disk': disk.percent,
                'network': {
                    'sent': net.bytes_sent,
                    'recv': net.bytes_recv,
                    'connections': len(psutil.net_connections())
                },
                'timestamp': datetime.now().isoformat()
            })
        
        elif path == '/api/processes':
            # Get top processes
            processes = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    processes.append({
                        'pid': p.info['pid'],
                        'name': p.info['name'],
                        'cpu': p.info['cpu_percent'] or 0,
                        'mem': p.info['memory_percent'] or 0,
                        'status': p.info['status']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort by CPU and get top 15
            processes.sort(key=lambda x: x['cpu'], reverse=True)
            
            self.send_json_response({
                'processes': processes[:15],
                'timestamp': datetime.now().isoformat()
            })
        
        elif path == '/api/health':
            # Get health check data
            self.send_json_response({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat()
            })
        
        else:
            self.send_error_response(404, 'Not Found')
    
    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode())


def main():
    server = HTTPServer(('0.0.0.0', API_PORT), SystemMonitorAPI)
    logger.info(f'Starting System Monitor API on port {API_PORT}')
    logger.info(f'Access dashboard at: http://your-server:{API_PORT}/dashboard.html')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        server.shutdown()


if __name__ == '__main__':
    main()