#!/usr/bin/env python3
"""
增强版健康检查API服务 V2 - 性能优化版
- 内存缓存: 避免重复文件IO
- 增量更新: 只在必要时刷新数据
- 预加载: 服务启动时预热缓存
"""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import os
import threading

PORT = 8890
WORKSPACE = '/root/.openclaw/workspace'
CACHE_TTL = 30  # 缓存30秒

# 全局缓存
_cache = {
    'health_data': {'data': None, 'time': 0},
    'metrics_data': {'data': None, 'time': 0},
    'enhanced_metrics': {'data': None, 'time': 0}
}
_cache_lock = threading.Lock()


def get_cached_data(cache_key, file_path, max_age=CACHE_TTL):
    """带缓存的数据获取"""
    now = datetime.now().timestamp()
    cache_entry = _cache.get(cache_key)
    
    if cache_entry and cache_entry['data'] and (now - cache_entry['time']) < max_age:
        return cache_entry['data']
    
    # 缓存过期或不存在，重新加载
    if os.path.exists(file_path):
        with open(file_path) as f:
            data = json.load(f)
    else:
        data = None
    
    with _cache_lock:
        _cache[cache_key] = {'data': data, 'time': now}
    
    return data


def invalidate_cache(cache_key=None):
    """清除缓存"""
    if cache_key:
        with _cache_lock:
            _cache[cache_key] = {'data': None, 'time': 0}
    else:
        with _cache_lock:
            for key in _cache:
                _cache[key] = {'data': None, 'time': 0}


class HealthAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        
        if path == '/' or path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=10')
            self.end_headers()
            response = {
                'status': 'ok',
                'service': 'ultron-health-api',
                'version': '2.1-optimized',
                'timestamp': datetime.now().isoformat(),
                'cache_enabled': True
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=10')
            self.end_headers()
            
            log_file = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'
            health_data = get_cached_data('health_data', log_file)
            if not health_data:
                health_data = {'checks': [], 'summary': {'total': 0, 'healthy': 0, 'warning': 0}}
            
            response = {
                'system': 'healthy',
                'last_check': health_data['checks'][-1] if health_data.get('checks') else None,
                'summary': health_data.get('summary', {'total': 0, 'healthy': 0, 'warning': 0})
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=10')
            self.end_headers()
            
            log_file = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'
            health_data = get_cached_data('health_data', log_file)
            if not health_data:
                health_data = {'checks': [], 'summary': {'total': 0, 'healthy': 0, 'warning': 0}}
            
            summary = health_data.get('summary', {'total': 0, 'healthy': 0, 'warning': 0})
            response = {
                'total_checks': summary.get('total', 0),
                'healthy_checks': summary.get('healthy', 0),
                'warning_checks': summary.get('warning', 0),
                'health_rate': summary.get('healthy', 0) / max(summary.get('total', 1), 1) * 100
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif path == '/api/enhanced-metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=10')
            self.end_headers()
            
            metrics_file = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'
            metrics_data = get_cached_data('enhanced_metrics', metrics_file)
            if not metrics_data:
                metrics_data = []
            
            latest = metrics_data[-1] if metrics_data else {}
            response = {
                'system': latest.get('system', {}),
                'services': latest.get('services', {}),
                'network': latest.get('network', {}),
                'history_count': len(metrics_data)
            }
            self.wfile.write(json.dumps(response).encode())
    
        elif path == '/api/charts/load':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=10')
            self.end_headers()
            
            metrics_file = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'
            metrics_data = get_cached_data('enhanced_metrics', metrics_file)
            if not metrics_data:
                metrics_data = []
            
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
            self.wfile.write(json.dumps(response).encode())
    
        elif path == '/api/charts/memory':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=10')
            self.end_headers()
            
            metrics_file = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'
            metrics_data = get_cached_data('enhanced_metrics', metrics_file)
            if not metrics_data:
                metrics_data = []
            
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
            self.wfile.write(json.dumps(response).encode())

        elif path == '/api/cache/clear':
            # 手动清除缓存端点
            invalidate_cache()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'cache_cleared'}).encode())
            
        elif path == '/api/cache/stats':
            # 查看缓存状态
            now = datetime.now().timestamp()
            stats = {}
            for key, entry in _cache.items():
                age = now - entry['time'] if entry['time'] > 0 else -1
                stats[key] = {
                    'cached': entry['data'] is not None,
                    'age_seconds': round(age, 1) if age >= 0 else 'never',
                    'ttl': CACHE_TTL
                }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
            
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())
    
    def log_message(self, format, *args):
        pass


def run_server(port=PORT):
    # 预热缓存
    print("正在预热缓存...")
    log_file = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'
    metrics_file = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'
    get_cached_data('health_data', log_file)
    get_cached_data('enhanced_metrics', metrics_file)
    print("缓存预热完成")
    
    server = HTTPServer(('0.0.0.0', port), HealthAPIHandler)
    print(f'健康检查API服务运行在端口 {port} (优化版 v2.1)')
    server.serve_forever()


if __name__ == '__main__':
    run_server()