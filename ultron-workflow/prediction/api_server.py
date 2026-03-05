#!/usr/bin/env python3
"""
预测分析模块 API 服务器
端口: 18127
"""

import json
import time
import random
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import deque
import statistics

class PredictionEngine:
    """预测引擎"""
    
    def __init__(self):
        self.data_streams = {}
        self.anomalies = []
        self.lock = threading.Lock()
    
    def add_data_point(self, stream_id: str, value: float, timestamp: str = None):
        """添加数据点"""
        with self.lock:
            if stream_id not in self.data_streams:
                self.data_streams[stream_id] = deque(maxlen=100)
            
            ts = timestamp or datetime.now().isoformat()
            self.data_streams[stream_id].append({
                'value': value,
                'timestamp': ts
            })
            
            # 检测异常
            self._detect_anomaly(stream_id, value)
    
    def _detect_anomaly(self, stream_id: str, value: float):
        """简单异常检测"""
        data = self.data_streams[stream_id]
        if len(data) < 5:
            return
        
        values = [d['value'] for d in data]
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 1
        
        if abs(value - mean) > 3 * std:
            self.anomalies.append({
                'stream': stream_id,
                'value': value,
                'expected': mean,
                'deviation': abs(value - mean) / std if std > 0 else 0,
                'timestamp': datetime.now().isoformat()
            })
    
    def predict_linear(self, stream_id: str, steps: int = 5):
        """线性预测"""
        with self.lock:
            data = self.data_streams.get(stream_id, [])
            if len(data) < 2:
                return None
            
            values = [d['value'] for d in data]
            n = len(values)
            x_mean = (n - 1) / 2
            y_mean = statistics.mean(values)
            
            numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            
            slope = numerator / denominator if denominator != 0 else 0
            intercept = y_mean - slope * x_mean
            
            predictions = []
            for i in range(steps):
                pred_value = slope * (n + i) + intercept
                predictions.append({
                    'step': i + 1,
                    'value': round(pred_value, 2),
                    'timestamp': (datetime.now() + timedelta(minutes=i+1)).isoformat()
                })
            
            return {
                'stream': stream_id,
                'slope': round(slope, 4),
                'intercept': round(intercept, 2),
                'predictions': predictions
            }
    
    def get_trend(self, stream_id: str):
        """获取趋势分析"""
        with self.lock:
            data = self.data_streams.get(stream_id, [])
            if len(data) < 3:
                return None
            
            values = [d['value'] for d in data]
            first_half = statistics.mean(values[:len(values)//2])
            second_half = statistics.mean(values[len(values)//2:])
            
            change_rate = (second_half - first_half) / first_half if first_half != 0 else 0
            
            if change_rate > 0.1:
                trend = 'rising'
            elif change_rate < -0.1:
                trend = 'falling'
            else:
                trend = 'stable'
            
            return {
                'stream': stream_id,
                'trend': trend,
                'change_rate': round(change_rate * 100, 2),
                'current': round(values[-1], 2),
                'avg': round(statistics.mean(values), 2),
                'min': round(min(values), 2),
                'max': round(max(values), 2)
            }
    
    def get_anomalies(self, limit: int = 10):
        return self.anomalies[-limit:]
    
    def get_status(self):
        return {
            'streams': len(self.data_streams),
            'total_points': sum(len(d) for d in self.data_streams.values()),
            'anomalies': len(self.anomalies),
            'uptime': time.time()
        }


engine = PredictionEngine()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())
        
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(engine.get_status()).encode())
        
        elif self.path == '/anomalies':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(engine.get_anomalies()).encode())
        
        elif self.path.startswith('/predict/'):
            stream_id = self.path.split('/')[-1]
            result = engine.predict_linear(stream_id)
            self.send_response(200 if result else 404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result or {'error': 'not found'}).encode())
        
        elif self.path.startswith('/trend/'):
            stream_id = self.path.split('/')[-1]
            result = engine.get_trend(stream_id)
            self.send_response(200 if result else 404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result or {'error': 'not found'}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/data':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                stream_id = data.get('stream', 'default')
                value = data.get('value', 0)
                engine.add_data_point(stream_id, float(value))
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode())
            except:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass


def run_server(port=18128):
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"预测分析服务运行在端口 {port}")
    server.serve_forever()


if __name__ == '__main__':
    # 添加模拟数据
    for i in range(20):
        engine.add_data_point('cpu', 50 + random.gauss(0, 10) + i * 0.5)
        engine.add_data_point('memory', 60 + random.gauss(0, 5))
        time.sleep(0.05)
    
    engine.add_data_point('cpu', 150)  # 模拟异常
    
    print("预测分析模块初始化完成")
    print(engine.get_status())
    print("\n趋势分析:", engine.get_trend('cpu'))
    print("\n线性预测:", engine.predict_linear('cpu', 3))
    print("\n异常检测:", engine.get_anomalies())
    
    run_server()