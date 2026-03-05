#!/usr/bin/env python3
"""
Decision Agent Integration Layer
Bridges Decision Engine (18120) with Agent Network (18150) and other systems
"""
import json
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
import threading

PORT = 18220

class DecisionIntegrationHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'service': 'decision-integration',
                'version': '1.0',
                'integrations': {
                    'decision_engine': self.check_service('http://localhost:18120/health'),
                    'agent_network': self.check_service('http://localhost:18150/health'),
                    'task_queue': self.check_service('http://localhost:18101/health'),
                    'agent_lifecycle': self.check_service('http://localhost:18100/health')
                }
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
        elif self.path == '/api/stats':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'service': 'decision-integration',
                'integrated_systems': 4,
                'uptime': time.time()
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode()
        
        if self.path == '/api/execute':
            self.handle_execute(json.loads(body))
        elif self.path == '/api/delegate':
            self.handle_delegate(json.loads(body))
        elif self.path == '/api/integrate':
            self.handle_integrate(json.loads(body))
        else:
            self.send_response(404)
            self.end_headers()
    
    def check_service(self, url):
        try:
            req = Request(url)
            with urlopen(req, timeout=2) as response:
                return {'status': 'online', 'code': response.status}
        except:
            return {'status': 'offline'}
    
    def handle_execute(self, data):
        """Execute a decision through the Agent Network"""
        decision = data.get('decision', {})
        context = data.get('context', {})
        
        # Submit task to Agent Network
        task_payload = {
            'task_type': 'execute_decision',
            'priority': data.get('priority', 5),
            'data': {
                'decision': decision,
                'context': context,
                'source': 'decision_engine'
            },
            'required_capabilities': decision.get('capabilities', []),
            'timeout': data.get('timeout', 300)
        }
        
        try:
            req = Request('http://localhost:18150/api/tasks', 
                         data=json.dumps(task_payload).encode(),
                         headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=10) as response:
                task_result = json.loads(response.read().decode())
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'task_id': task_result.get('task_id'),
                'status': 'delegated_to_agent_network'
            }).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def handle_delegate(self, data):
        """Delegate complex decision to appropriate agent"""
        agent_type = data.get('agent_type', 'analyzer')
        task = data.get('task', {})
        
        try:
            req = Request(f'http://localhost:18150/api/agents/{agent_type}/task',
                         data=json.dumps(task).encode(),
                         headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def handle_integrate(self, data):
        """Integrate decision with external systems"""
        target_system = data.get('system')
        action = data.get('action')
        payload = data.get('payload', {})
        
        endpoints = {
            'task_queue': 'http://localhost:18101/api/enqueue',
            'agent_lifecycle': 'http://localhost:18100/api/tasks',
            'metrics': 'http://localhost:18099/api/metrics'
        }
        
        if target_system not in endpoints:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Unknown system'}).encode())
            return
        
        try:
            req = Request(endpoints[target_system],
                         data=json.dumps(payload).encode(),
                         headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode())
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'system': target_system,
                'result': result
            }).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())

def start_server():
    server = HTTPServer(('0.0.0.0', PORT), DecisionIntegrationHandler)
    print(f"Decision Integration Layer running on port {PORT}")
    server.serve_forever()

if __name__ == '__main__':
    start_server()