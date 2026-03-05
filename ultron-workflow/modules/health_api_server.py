#!/usr/bin/env python3
"""
增强版健康检查API服务
提供RESTful API访问健康检查数据
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import os

PORT = 8890
WORKSPACE = '/root/.openclaw/workspace'

class HealthAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        
        if path == '/' or path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'ok',
                'service': 'ultron-health-api',
                'version': '2.0',
                'timestamp': datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            log_file = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'
            health_data = {'checks': [], 'summary': {'total': 0, 'healthy': 0, 'warning': 0}}
            if os.path.exists(log_file):
                with open(log_file) as f:
                    health_data = json.load(f)
            
            response = {
                'system': 'healthy',
                'last_check': health_data['checks'][-1] if health_data['checks'] else None,
                'summary': health_data['summary']
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        elif path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            log_file = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'
            health_data = {'checks': [], 'summary': {'total': 0, 'healthy': 0, 'warning': 0}}
            if os.path.exists(log_file):
                with open(log_file) as f:
                    health_data = json.load(f)
            
            response = {
                'total_checks': health_data['summary']['total'],
                'healthy_checks': health_data['summary']['healthy'],
                'warning_checks': health_data['summary']['warning'],
                'health_rate': health_data['summary']['healthy'] / max(health_data['summary']['total'], 1) * 100
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        elif path == '/api/enhanced-metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            metrics_file = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'
            metrics_data = []
            if os.path.exists(metrics_file):
                with open(metrics_file) as f:
                    metrics_data = json.load(f)
            
            latest = metrics_data[-1] if metrics_data else {}
            response = {
                'system': latest.get('system', {}),
                'services': latest.get('services', {}),
                'network': latest.get('network', {}),
                'history_count': len(metrics_data)
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
    
        elif path == '/api/charts/load':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            metrics_file = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'
            metrics_data = []
            if os.path.exists(metrics_file):
                with open(metrics_file) as f:
                    metrics_data = json.load(f)
            
            labels = []
            data_1m = []
            data_5m = []
            data_15m = []
            
            for m in metrics_data[-20:]:
                ts = m.get('timestamp', '')[:16]
                labels.append(ts[-5:])
                load = m.get('system', {}).get('load', {})
                data_1m.append(load.get('1m', 0))
                data_5m.append(load.get('5m', 0))
                data_15m.append(load.get('15m', 0))
            
            response = {
                'labels': labels,
                'datasets': {'1m': data_1m, '5m': data_5m, '15m': data_15m}
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
    
        elif path == '/api/charts/memory':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            metrics_file = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'
            metrics_data = []
            if os.path.exists(metrics_file):
                with open(metrics_file) as f:
                    metrics_data = json.load(f)
            
            labels = []
            used = []
            available = []
            
            for m in metrics_data[-20:]:
                ts = m.get('timestamp', '')[:16]
                labels.append(ts[-5:])
                mem = m.get('system', {}).get('memory', {})
                used.append(mem.get('used', 0))
                available.append(mem.get('available', 0))
            
            response = {
                'labels': labels,
                'datasets': {'used': used, 'available': available}
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())
    
    def log_message(self, format, *args):
        pass

def run_server(port=PORT):
    server = HTTPServer(('0.0.0.0', port), HealthAPIHandler)
    print(f'健康检查API服务运行在端口 {port}')
    server.serve_forever()

if __name__ == '__main__':
    run_server()