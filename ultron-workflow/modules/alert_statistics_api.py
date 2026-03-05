#!/usr/bin/env python3
"""
告警统计分析报表API
提供告警的时间分布、趋势分析、来源统计等功能
"""
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

WORKSPACE = '/root/.openclaw/workspace'
ALERT_HISTORY_FILE = f'{WORKSPACE}/ultron-workflow/logs/alert_history.json'
PORT = 8892

def load_alerts():
    """加载告警历史"""
    if os.path.exists(ALERT_HISTORY_FILE):
        with open(ALERT_HISTORY_FILE) as f:
            return json.load(f)
    return []

def parse_time(t):
    """解析时间字符串"""
    if isinstance(t, str):
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
            try:
                return datetime.strptime(t.replace('+00:00', ''), fmt)
            except:
                continue
    return None

def get_time_distribution(alerts, period='hour'):
    """获取时间分布统计"""
    distribution = defaultdict(int)
    for alert in alerts:
        ts = parse_time(alert.get('timestamp', ''))
        if not ts:
            continue
        if period == 'hour':
            key = ts.strftime('%Y-%m-%d %H:00')
        elif period == 'day':
            key = ts.strftime('%Y-%m-%d')
        elif period == 'week':
            key = ts.strftime('%Y-W%W')
        else:
            key = ts.strftime('%Y-%m-%d')
        distribution[key] += 1
    return dict(sorted(distribution.items()))

def get_level_distribution(alerts):
    """获取告警级别分布"""
    distribution = {'critical': 0, 'warning': 0, 'info': 0}
    for alert in alerts:
        level = alert.get('level', 'info')
        if level in distribution:
            distribution[level] += 1
    return distribution

def get_source_distribution(alerts):
    """获取告警来源分布"""
    distribution = defaultdict(int)
    for alert in alerts:
        source = alert.get('source', alert.get('source_type', 'unknown'))
        distribution[source] += 1
    return dict(distribution)

def get_trend_analysis(alerts, days=7):
    """获取趋势分析"""
    now = datetime.now()
    trends = []
    
    for i in range(days):
        date = (now - timedelta(days=days - i - 1)).strftime('%Y-%m-%d')
        day_alerts = []
        for a in alerts:
            ts = parse_time(a.get('timestamp', ''))
            if ts and ts.strftime('%Y-%m-%d') == date:
                day_alerts.append(a)
        trends.append({
            'date': date,
            'total': len(day_alerts),
            'critical': len([a for a in day_alerts if a.get('level') == 'critical']),
            'warning': len([a for a in day_alerts if a.get('level') == 'warning']),
            'info': len([a for a in day_alerts if a.get('level') == 'info'])
        })
    return trends

def get_mttr_stats(alerts):
    """获取平均修复时间统计 (Mean Time To Resolve)"""
    resolved = [a for a in alerts if a.get('resolved') and a.get('timestamp')]
    if not resolved:
        return {'mttr_minutes': 0, 'resolved_count': 0}
    
    total_time = 0
    count = 0
    for alert in resolved:
        start = parse_time(alert.get('timestamp', ''))
        end = parse_time(alert.get('resolved_at', ''))
        if start and end:
            total_time += (end - start).total_seconds() / 60
            count += 1
    
    return {
        'mttr_minutes': round(total_time / count, 2) if count else 0,
        'resolved_count': count
    }

def get_top_alerts(alerts, limit=10):
    """获取最频繁的告警"""
    alert_counts = defaultdict(int)
    for alert in alerts:
        name = alert.get('title', alert.get('message', 'unknown'))
        alert_counts[name] += 1
    
    sorted_alerts = sorted(alert_counts.items(), key=lambda x: x[1], reverse=True)
    return [{'title': title, 'count': count} for title, count in sorted_alerts[:limit]]

def get_full_report(period='day'):
    """生成完整报表"""
    alerts = load_alerts()
    
    return {
        'generated_at': datetime.now().isoformat(),
        'period': period,
        'summary': {
            'total_alerts': len(alerts),
            'time_distribution': get_time_distribution(alerts, period),
            'level_distribution': get_level_distribution(alerts),
            'source_distribution': get_source_distribution(alerts)
        },
        'trend': get_trend_analysis(alerts, days=7),
        'mttr': get_mttr_stats(alerts),
        'top_alerts': get_top_alerts(alerts)
    }

class AlertStatsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)
        
        if path == '/' or path == '/report':
            period = params.get('period', ['day'])[0]
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_full_report(period), indent=2).encode())
        
        elif path == '/distribution':
            period = params.get('period', ['day'])[0]
            alerts = load_alerts()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'time': get_time_distribution(alerts, period),
                'level': get_level_distribution(alerts),
                'source': get_source_distribution(alerts)
            }, indent=2).encode())
        
        elif path == '/trend':
            days = int(params.get('days', [7])[0])
            alerts = load_alerts()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_trend_analysis(alerts, days), indent=2).encode())
        
        elif path == '/mttr':
            alerts = load_alerts()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_mttr_stats(alerts), indent=2).encode())
        
        elif path == '/top':
            limit = int(params.get('limit', [10])[0])
            alerts = load_alerts()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_top_alerts(alerts, limit), indent=2).encode())
        
        elif path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'service': 'alert-stats-api'}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_server(port=PORT):
    server = HTTPServer(('0.0.0.0', port), AlertStatsHandler)
    print(f'告警统计分析API运行在端口 {port}')
    server.serve_forever()

if __name__ == '__main__':
    # 测试报表生成
    report = get_full_report()
    print(f"报表生成时间: {report['generated_at']}")
    print(f"告警总数: {report['summary']['total_alerts']}")
    print(f"级别分布: {report['summary']['level_distribution']}")
    print(f"趋势数据: {len(report['trend'])} 天")
    print(f"MTTR: {report['mttr']}")
    
    # 可以启动服务
    # run_server()