#!/usr/bin/env python3
"""
告警历史展示API
提供告警历史的查询和展示功能
"""
import os, json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

WORKSPACE = '/root/.openclaw/workspace'
ALERT_HISTORY_FILE = f'{WORKSPACE}/ultron-workflow/logs/alert_history.json'
PORT = 8891

def load_alerts():
    """加载告警历史"""
    if os.path.exists(ALERT_HISTORY_FILE):
        with open(ALERT_HISTORY_FILE) as f:
            return json.load(f)
    return []

def get_alert_summary(alerts):
    """获取告警摘要"""
    if not alerts:
        return {'total': 0, 'critical': 0, 'warning': 0, 'info': 0}
    
    return {
        'total': len(alerts),
        'critical': len([a for a in alerts if a.get('level') == 'critical']),
        'warning': len([a for a in alerts if a.get('level') == 'warning']),
        'info': len([a for a in alerts if a.get('level') == 'info'])
    }

def filter_alerts(alerts, level=None, limit=20):
    """过滤告警"""
    if level:
        alerts = [a for a in alerts if a.get('level') == level]
    return alerts[-limit:]

class AlertHistoryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/' or path == '/alerts':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            alerts = load_alerts()
            summary = get_alert_summary(alerts)
            
            response = {
                'summary': summary,
                'alerts': filter_alerts(alerts, limit=20)
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
        
        elif path == '/summary':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            alerts = load_alerts()
            self.wfile.write(json.dumps(get_alert_summary(alerts), indent=2).encode())
        
        elif path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'service': 'alert-history-api'}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_server(port=PORT):
    server = HTTPServer(('0.0.0.0', port), AlertHistoryHandler)
    print(f'告警历史API运行在端口 {port}')
    server.serve_forever()

if __name__ == '__main__':
    # 测试数据查询
    alerts = load_alerts()
    summary = get_alert_summary(alerts)
    print(f'告警历史: {summary}')
    
    # 可以启动服务
    # run_server()
