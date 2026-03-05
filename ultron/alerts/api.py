#!/usr/bin/env python3
"""
告警API - 为Dashboard提供告警数据
"""

import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alert_store import AlertStore

store = AlertStore()

class AlertHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/alerts':
            # 返回告警列表
            alerts = store.get_recent(50)
            stats = store.get_stats()
            
            response = {
                "alerts": alerts,
                "stats": stats
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 禁用日志

def run_server(port=8765):
    server = HTTPServer(('0.0.0.0', port), AlertHandler)
    print(f"🚀 告警API服务启动: http://0.0.0.0:{port}/api/alerts")
    server.serve_forever()

if __name__ == "__main__":
    run_server()