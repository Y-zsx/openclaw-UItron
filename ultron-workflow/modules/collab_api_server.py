#!/usr/bin/env python3
"""
协作中心API服务
提供Agent协作状态的RESTful API
"""
import os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs

WORKSPACE = '/root/.openclaw/workspace'
COLLAB_FILE = f'{WORKSPACE}/ultron-workflow/logs/agent_collaboration.json'
PORT = 8892

def load_collaboration():
    if os.path.exists(COLLAB_FILE):
        with open(COLLAB_FILE) as f:
            return json.load(f)
    return {'agents': [], 'links': [], 'messages': []}

class CollabAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/' or path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'service': 'collab-api', 'version': '1.0'}).encode())
        
        elif path == '/agents':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = load_collaboration()
            self.wfile.write(json.dumps({'agents': data.get('agents', [])}, indent=2).encode())
        
        elif path == '/links':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = load_collaboration()
            self.wfile.write(json.dumps({'links': data.get('links', [])}, indent=2).encode())
        
        elif path == '/messages':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = load_collaboration()
            msgs = data.get('messages', [])
            self.wfile.write(json.dumps({'messages': msgs[-20:]}, indent=2).encode())
        
        elif path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = load_collaboration()
            self.wfile.write(json.dumps({
                'total_agents': len(data.get('agents', [])),
                'total_links': len(data.get('links', [])),
                'total_messages': len(data.get('messages', []))
            }, indent=2).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_server(port=PORT):
    server = HTTPServer(('0.0.0.0', port), CollabAPIHandler)
    print(f'协作中心API服务运行在端口 {port}')
    server.serve_forever()

if __name__ == '__main__':
    # 测试API端点
    print('协作中心API服务已就绪')
    print('端点:')
    print('  /health - 健康检查')
    print('  /agents - Agent列表')
    print('  /links - 协作链接')
    print('  /messages - 消息历史')
    print('  /status - 状态概览')
