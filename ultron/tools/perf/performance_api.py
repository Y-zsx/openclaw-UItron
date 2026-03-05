#!/usr/bin/env python3
"""
Agent性能分析REST API
端口: 8095
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from performance_profiler import get_profiler, stop_profiler

PORT = 8095

class PerfHandler(BaseHTTPRequestHandler):
    profiler = get_profiler()
    
    def log_message(self, format, *args):
        pass  # 禁用日志
        
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())
        
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/health':
            self.send_json({'status': 'ok', 'port': PORT})
            
        elif path == '/stats':
            # 当前系统统计
            stats = self.profiler.get_current_stats()
            self.send_json(stats)
            
        elif path == '/cpu':
            limit = int(parse_qs(urlparse(self.path).query).get('limit', [60])[0])
            self.send_json(self.profiler.get_cpu_history(limit))
            
        elif path == '/memory':
            limit = int(parse_qs(urlparse(self.path).query).get('limit', [60])[0])
            self.send_json(self.profiler.get_memory_history(limit))
            
        elif path == '/disk-io':
            limit = int(parse_qs(urlparse(self.path).query).get('limit', [60])[0])
            self.send_json(self.profiler.get_disk_io_history(limit))
            
        elif path == '/network':
            limit = int(parse_qs(urlparse(self.path).query).get('limit', [60])[0])
            self.send_json(self.profiler.get_network_history(limit))
            
        elif path == '/analysis':
            # 性能分析
            analysis = self.profiler.analyze_performance()
            self.send_json(analysis)
            
        elif path == '/agents':
            # Agent指标
            agent_id = parse_qs(urlparse(self.path).query).get('agent_id', [None])[0]
            if agent_id:
                self.send_json(self.profiler.get_agent_metrics(agent_id))
            else:
                self.send_json(self.profiler.get_agent_metrics())
                
        elif path == '/snapshot':
            # 完整快照
            self.send_json(self.profiler.get_full_snapshot())
            
        elif path == '/':
            self.send_json({
                'name': 'Agent Performance API',
                'port': PORT,
                'endpoints': [
                    '/health - 健康检查',
                    '/stats - 当前系统统计',
                    '/cpu?limit=60 - CPU历史',
                    '/memory?limit=60 - 内存历史',
                    '/disk-io?limit=60 - 磁盘IO历史',
                    '/network?limit=60 - 网络IO历史',
                    '/analysis - 性能分析',
                    '/agents - Agent指标',
                    '/snapshot - 完整快照'
                ]
            })
        else:
            self.send_json({'error': 'Not Found'}, 404)
            
    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        
        try:
            data = json.loads(body)
        except:
            data = {}
            
        if path == '/agents/register':
            # 注册Agent
            agent_id = data.get('agent_id')
            metadata = data.get('metadata', {})
            if agent_id:
                self.profiler.register_agent(agent_id, metadata)
                self.send_json({'status': 'registered', 'agent_id': agent_id})
            else:
                self.send_json({'error': 'agent_id required'}, 400)
                
        elif path == '/agents/record':
            # 记录请求
            agent_id = data.get('agent_id')
            latency_ms = data.get('latency_ms', 0)
            error = data.get('error', False)
            if agent_id:
                self.profiler.record_agent_request(agent_id, latency_ms, error)
                self.send_json({'status': 'recorded'})
            else:
                self.send_json({'error': 'agent_id required'}, 400)
                
        elif path == '/agents/alert':
            # 添加告警
            agent_id = data.get('agent_id')
            alert_type = data.get('type', 'info')
            message = data.get('message', '')
            if agent_id:
                self.profiler.add_agent_alert(agent_id, alert_type, message)
                self.send_json({'status': 'alert_added'})
            else:
                self.send_json({'error': 'agent_id required'}, 400)
                
        else:
            self.send_json({'error': 'Not Found'}, 404)


def run_server():
    server = HTTPServer(('0.0.0.0', PORT), PerfHandler)
    print(f"Performance API running on port {PORT}")
    print(f"Endpoints: /stats, /cpu, /memory, /analysis, /agents, /snapshot")
    server.serve_forever()


if __name__ == '__main__':
    run_server()