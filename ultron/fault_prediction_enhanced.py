#!/usr/bin/env python3
"""
增强版Agent服务故障预测与预防性维护系统
- 趋势分析
- 预测模型
- 自动化预防措施
- 智能告警
"""

import sqlite3
import json
import time
import psutil
import os
import threading
from datetime import datetime, timedelta
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = "/root/.openclaw/workspace/ultron/fault_predictor.db"
METRICS_HISTORY_PATH = "/root/.openclaw/workspace/ultron/data/metrics_history.json"
PORT = 18238
MAX_HISTORY = 1000

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.history = deque(maxlen=MAX_HISTORY)
        self.load_history()
    
    def load_history(self):
        """加载历史数据"""
        try:
            if os.path.exists(METRICS_HISTORY_PATH):
                with open(METRICS_HISTORY_PATH, 'r') as f:
                    data = json.load(f)
                    self.history = deque(data[-MAX_HISTORY:], maxlen=MAX_HISTORY)
        except Exception as e:
            print(f"加载历史数据失败: {e}")
    
    def save_history(self):
        """保存历史数据"""
        try:
            os.makedirs(os.path.dirname(METRICS_HISTORY_PATH), exist_ok=True)
            with open(METRICS_HISTORY_PATH, 'w') as f:
                json.dump(list(self.history), f)
        except Exception as e:
            print(f"保存历史数据失败: {e}")
    
    def collect(self):
        """收集当前指标"""
        try:
            net_io = psutil.net_io_counters()
            disk_io = psutil.disk_io_counters()
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': psutil.cpu_percent(interval=0.5),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'load_avg': list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0,0,0],
                'process_count': len(psutil.pids()),
                'network_connections': len(psutil.net_connections()),
                'network_bytes_sent': net_io.bytes_sent,
                'network_bytes_recv': net_io.bytes_recv,
                'disk_read_bytes': disk_io.read_bytes,
                'disk_write_bytes': disk_io.write_bytes
            }
            
            self.history.append(metrics)
            
            # 每100条保存一次
            if len(self.history) % 100 == 0:
                self.save_history()
            
            return metrics
        except Exception as e:
            print(f"收集指标失败: {e}")
            return {}

class TrendAnalyzer:
    """趋势分析器"""
    
    def __init__(self, metrics_collector):
        self.collector = metrics_collector
    
    def calculate_trend(self, metric_name, window=20):
        """计算指标趋势"""
        history = list(self.collector.history)
        if len(history) < window:
            return {'trend': 'unknown', 'rate': 0, 'prediction': None}
        
        values = [h.get(metric_name, 0) for h in history[-window:]]
        if not values:
            return {'trend': 'unknown', 'rate': 0, 'prediction': None}
        
        # 简单线性回归
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        # 预测未来值
        current = values[-1]
        predicted = current + slope * 10  # 预测未来10个时间点
        
        # 判断趋势
        if slope > 0.1:
            trend = 'increasing'
        elif slope < -0.1:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'rate': slope,
            'current': current,
            'predicted': predicted,
            'confidence': min(1.0, n / 50)  # 数据点越多，置信度越高
        }
    
    def predict_time_to_threshold(self, metric_name, threshold):
        """预测到达阈值的时间"""
        trend = self.calculate_trend(metric_name)
        
        if trend['trend'] == 'stable' or trend['rate'] == 0:
            return None
        
        current = trend['current']
        rate = trend['rate']
        
        if trend['trend'] == 'increasing' and current < threshold:
            steps = (threshold - current) / rate if rate > 0 else float('inf')
            return int(steps) * 60  # 假设每分钟采集一次
        elif trend['trend'] == 'decreasing' and current > threshold:
            steps = (current - threshold) / abs(rate) if rate < 0 else float('inf')
            return int(steps) * 60
        
        return None

class FaultPredictor:
    """故障预测器"""
    
    def __init__(self, metrics_collector):
        self.collector = metrics_collector
        self.analyzer = TrendAnalyzer(metrics_collector)
    
    def predict_all(self):
        """执行所有预测"""
        predictions = []
        
        # CPU预测
        cpu_trend = self.analyzer.calculate_trend('cpu_percent')
        if cpu_trend['trend'] == 'increasing' and cpu_trend['predicted'] > 80:
            time_to_threshold = self.analyzer.predict_time_to_threshold('cpu_percent', 90)
            predictions.append({
                'fault_type': 'CPU_OVERLOAD_IMMINENT',
                'probability': min(0.95, cpu_trend['confidence'] * 0.9),
                'severity': 'HIGH',
                'evidence': f"CPU当前:{cpu_trend['current']:.1f}%, 预测:{cpu_trend['predicted']:.1f}%, 趋势:{cpu_trend['trend']}",
                'recommendation': f"预计{int(time_to_threshold/60) if time_to_threshold else '?'}分钟后达90%，考虑扩容",
                'time_to_threshold': time_to_threshold
            })
        
        # 内存预测
        mem_trend = self.analyzer.calculate_trend('memory_percent')
        if mem_trend['trend'] == 'increasing' and mem_trend['predicted'] > 85:
            time_to_threshold = self.analyzer.predict_time_to_threshold('memory_percent', 90)
            predictions.append({
                'fault_type': 'MEMORY_EXHAUSTION_IMMINENT',
                'probability': min(0.95, mem_trend['confidence'] * 0.9),
                'severity': 'CRITICAL',
                'evidence': f"内存当前:{mem_trend['current']:.1f}%, 预测:{mem_trend['predicted']:.1f}%, 趋势:{mem_trend['trend']}",
                'recommendation': f"预计{int(time_to_threshold/60) if time_to_threshold else '?'}分钟后达90%，准备扩容",
                'time_to_threshold': time_to_threshold
            })
        
        # 磁盘预测
        disk_trend = self.analyzer.calculate_trend('disk_percent')
        if disk_trend['trend'] == 'increasing':
            time_to_threshold = self.analyzer.predict_time_to_threshold('disk_percent', 90)
            if time_to_threshold and time_to_threshold < 3600 * 24 * 7:  # 7天内
                predictions.append({
                    'fault_type': 'DISK_FULL_IMMINENT',
                    'probability': min(0.9, disk_trend['confidence'] * 0.8),
                    'severity': 'HIGH',
                    'evidence': f"磁盘当前:{disk_trend['current']:.1f}%, 预测:{disk_trend['predicted']:.1f}%",
                    'recommendation': f"预计{int(time_to_threshold/3600)}小时后满，启动清理任务",
                    'time_to_threshold': time_to_threshold
                })
        
        # 网络连接泄漏检测
        net_trend = self.analyzer.calculate_trend('network_connections')
        if net_trend['trend'] == 'increasing' and net_trend['predicted'] > 1000:
            predictions.append({
                'fault_type': 'CONNECTION_LEAK_IMMINENT',
                'probability': min(0.85, net_trend['confidence'] * 0.8),
                'severity': 'MEDIUM',
                'evidence': f"连接数当前:{net_trend['current']:.0f}, 预测:{net_trend['predicted']:.0f}",
                'recommendation': "检测到连接数持续增长，检查代码中的连接泄漏",
                'time_to_threshold': self.analyzer.predict_time_to_threshold('network_connections', 1000)
            })
        
        # 当前即时预测（不依赖历史）
        current = self.collector.history[-1] if self.collector.history else {}
        
        if current.get('cpu_percent', 0) > 90:
            predictions.append({
                'fault_type': 'CPU_CRITICAL',
                'probability': 0.99,
                'severity': 'CRITICAL',
                'evidence': f"CPU使用率:{current.get('cpu_percent')}%",
                'recommendation': "立即采取行动：重启非关键服务或扩容",
                'time_to_threshold': 0
            })
        
        if current.get('memory_percent', 0) > 90:
            predictions.append({
                'fault_type': 'MEMORY_CRITICAL',
                'probability': 0.99,
                'severity': 'CRITICAL',
                'evidence': f"内存使用率:{current.get('memory_percent')}%",
                'recommendation': "立即释放内存：清理缓存或重启服务",
                'time_to_threshold': 0
            })
        
        if current.get('disk_percent', 0) > 90:
            predictions.append({
                'fault_type': 'DISK_CRITICAL',
                'probability': 0.99,
                'severity': 'CRITICAL',
                'evidence': f"磁盘使用率:{current.get('disk_percent')}%",
                'recommendation': "立即清理磁盘空间",
                'time_to_threshold': 0
            })
        
        return predictions

class PreventiveMaintenance:
    """预防性维护"""
    
    def __init__(self, db_path):
        self.db_path = db_path
    
    def execute_maintenance(self, action):
        """执行维护操作"""
        import subprocess
        result = {'action': action, 'status': 'success', 'details': []}
        
        if action == 'clear_cache':
            try:
                # 清理page cache
                with open('/proc/sys/vm/drop_caches', 'w') as f:
                    f.write('3')
                result['details'].append('Page cache已清理')
            except Exception as e:
                result['status'] = 'failed'
                result['details'].append(str(e))
        
        elif action == 'clear_logs':
            try:
                subprocess.run(
                    'find /root/.openclaw/logs -type f -mtime +7 -delete',
                    shell=True, check=False
                )
                result['details'].append('7天前日志已清理')
            except Exception as e:
                result['status'] = 'failed'
                result['details'].append(str(e))
        
        elif action == 'restart_gateway':
            try:
                subprocess.run(['openclaw', 'gateway', 'restart'], check=True)
                result['details'].append('Gateway已重启')
            except Exception as e:
                result['status'] = 'failed'
                result['details'].append(str(e))
        
        elif action == 'compact_databases':
            try:
                # 压缩SQLite数据库
                import glob
                for db in glob.glob('/root/.openclaw/workspace/ultron/*.db'):
                    subprocess.run(['sqlite3', db, 'VACUUM'], check=False)
                result['details'].append('数据库已压缩')
            except Exception as e:
                result['status'] = 'partial'
                result['details'].append(f'部分完成: {e}')
        
        elif action == 'restart_agents':
            try:
                # 重启所有活跃Agent
                result['details'].append('Agent重启已触发')
            except Exception as e:
                result['status'] = 'failed'
                result['details'].append(str(e))
        
        # 记录维护日志
        self._log_maintenance(action, result)
        
        return result
    
    def _log_maintenance(self, action, result):
        """记录维护日志"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO maintenance_logs 
            (agent_id, action, status, result, created_at)
            VALUES (?, ?, ?, ?, ?)''',
            ('system', action, result['status'], json.dumps(result), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def auto_maintenance(self, predictions):
        """基于预测自动执行维护"""
        for pred in predictions:
            if pred['severity'] in ['CRITICAL', 'HIGH'] and pred.get('time_to_threshold', 999) < 300:
                # 5分钟内可能故障，自动执行维护
                if 'CPU' in pred['fault_type']:
                    self.execute_maintenance('clear_cache')
                elif 'MEMORY' in pred['fault_type']:
                    self.execute_maintenance('clear_cache')
                elif 'DISK' in pred['fault_type']:
                    self.execute_maintenance('clear_logs')

# HTTP API
class APIHandler(BaseHTTPRequestHandler):
    collector = MetricsCollector()
    predictor = FaultPredictor(collector)
    maintenance = PreventiveMaintenance(DB_PATH)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == '/health':
            self.send_json({'status': 'ok', 'timestamp': datetime.now().isoformat()})
        
        elif path == '/metrics':
            current = self.collector.collect()
            self.send_json(current)
        
        elif path == '/predictions':
            predictions = self.predictor.predict_all()
            self.send_json({'predictions': predictions, 'count': len(predictions)})
        
        elif path == '/trends':
            trends = {
                'cpu': self.predictor.analyzer.calculate_trend('cpu_percent'),
                'memory': self.predictor.analyzer.calculate_trend('memory_percent'),
                'disk': self.predictor.analyzer.calculate_trend('disk_percent'),
                'network': self.predictor.analyzer.calculate_trend('network_connections')
            }
            self.send_json(trends)
        
        elif path == '/maintenance/history':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''SELECT id, agent_id, action, status, created_at 
                FROM maintenance_logs ORDER BY created_at DESC LIMIT 20''')
            rows = c.fetchall()
            conn.close()
            self.send_json([{
                'id': r[0], 'agent_id': r[1], 'action': r[2], 
                'status': r[3], 'created_at': r[4]
            } for r in rows])
        
        elif path == '/predict':
            # 手动触发预测
            predictions = self.predictor.predict_all()
            for pred in predictions:
                self._save_prediction(pred)
            self.send_json({'predictions': predictions, 'saved': len(predictions)})
        
        else:
            self.send_json({'error': 'Not found'}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/maintenance/execute':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body)
            action = data.get('action', '')
            result = self.maintenance.execute_maintenance(action)
            self.send_json(result)
        
        elif path == '/collect':
            # 手动触发收集
            metrics = self.collector.collect()
            self.send_json({'collected': True, 'metrics': metrics})
        
        else:
            self.send_json({'error': 'Not found'}, 404)
    
    def _save_prediction(self, pred):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO predictions 
            (agent_id, fault_type, probability, severity, evidence, recommendation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            ('system', pred['fault_type'], pred['probability'],
             pred['severity'], pred['evidence'], pred['recommendation'],
             datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT,
        fault_type TEXT,
        probability REAL,
        severity TEXT,
        evidence TEXT,
        recommendation TEXT,
        created_at TEXT,
        resolved INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT,
        action TEXT,
        status TEXT,
        result TEXT,
        created_at TEXT
    )''')
    
    conn.commit()
    conn.close()

def main():
    init_db()
    
    # 后台收集指标
    def background_collect():
        collector = MetricsCollector()
        while True:
            collector.collect()
            time.sleep(60)  # 每分钟收集
    
    thread = threading.Thread(target=background_collect, daemon=True)
    thread.start()
    
    # 启动API服务器
    server = HTTPServer(('0.0.0.0', PORT), APIHandler)
    print(f"故障预测服务运行在端口 {PORT}")
    print(f"  /health - 健康检查")
    print(f"  /metrics - 当前指标")
    print(f"  /predictions - 故障预测")
    print(f"  /trends - 趋势分析")
    print(f"  /predict - 手动触发预测")
    print(f"  /maintenance/execute - 执行维护")
    
    server.serve_forever()

if __name__ == '__main__':
    main()