#!/usr/bin/env python3
"""
Agent服务故障预测与预防性维护系统
端口: 18149
功能:
1. 故障预测 - 基于历史监控数据预测潜在故障
2. 预防性维护 - 自动生成维护任务
3. 趋势分析 - 分析指标趋势预测未来状态
4. 健康评分 - 服务健康状况评分
"""
import os
import sys
import time
import socket
import psutil
import json
import threading
import sqlite3
import statistics
from datetime import datetime, timedelta
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# 配置
PORT = 18149
DATA_DIR = Path("/root/.openclaw/workspace/ultron/data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "predictive_maintenance.db"

# 预测配置
CONFIG = {
    "cpu_warning": 70.0,
    "cpu_critical": 85.0,
    "memory_warning": 75.0,
    "memory_critical": 90.0,
    "prediction_window": 30,  # 预测时间窗口(分钟)
    "trend_threshold": 0.1,   # 趋势变化阈值
    "history_size": 100,      # 历史数据大小
}

# 服务端口列表
AGENT_PORTS = {
    18120: 'Decision Engine',
    18122: 'Alert Rules',
    18123: 'Monitor Panel',
    18124: 'Notifier',
    18125: 'Predictor',
    18132: 'Workflow',
    18135: 'Decision-Action',
    18143: 'Auto Scale',
    18144: 'Load Balancer',
    18145: 'Admin Panel'
}

# 历史数据
metrics_history = deque(maxlen=CONFIG["history_size"])
predictions = []
maintenance_tasks = []

class PredictiveMaintenanceDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 预测历史
            conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT,
                    prediction_type TEXT,
                    severity TEXT,
                    probability REAL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 维护任务
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    service_name TEXT,
                    task_type TEXT,
                    description TEXT,
                    scheduled_at TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 指标历史
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    disk_percent REAL,
                    load_avg REAL,
                    process_count INTEGER
                )
            """)

db = PredictiveMaintenanceDB(DB_PATH)

class PMHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/health' or path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            resp = {'status': 'ok', 'service': 'predictive-maintenance', 'port': PORT}
            self.wfile.write(json.dumps(resp).encode())
            
        elif path == '/predictions':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            resp = {
                'predictions': predictions[-20:],
                'count': len(predictions)
            }
            self.wfile.write(json.dumps(resp, indent=2).encode())
            
        elif path == '/maintenance-tasks':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            resp = {
                'tasks': maintenance_tasks[-20:],
                'count': len(maintenance_tasks)
            }
            self.wfile.write(json.dumps(resp, indent=2).encode())
            
        elif path == '/health-score':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            score = calculate_health_score()
            self.wfile.write(json.dumps(score, indent=2).encode())
            
        elif path == '/trends':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            trends = analyze_trends()
            self.wfile.write(json.dumps(trends, indent=2).encode())
            
        elif path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            resp = {
                'service': 'predictive-maintenance',
                'port': PORT,
                'predictions_count': len(predictions),
                'maintenance_tasks_count': len(maintenance_tasks),
                'history_size': len(metrics_history)
            }
            self.wfile.write(json.dumps(resp, indent=2).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
            
    def log_message(self, format, *args):
        pass

def check_port(port):
    """检查端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False

def get_metrics():
    """获取系统指标"""
    load_avg = [0, 0, 0]
    try:
        if hasattr(os, 'getloadavg'):
            load_avg = list(os.getloadavg())
    except:
        pass
    
    return {
        'timestamp': time.time(),
        'datetime': datetime.now().isoformat(),
        'cpu_percent': psutil.cpu_percent(interval=0.5),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'load_avg': load_avg,
        'process_count': len(psutil.pids())
    }

def get_service_status():
    """获取所有Agent服务状态"""
    status = {}
    for port, name in AGENT_PORTS.items():
        is_up = check_port(port)
        status[port] = {
            'name': name,
            'port': port,
            'up': is_up
        }
    return status

def calculate_health_score():
    """计算健康评分"""
    metrics = get_metrics()
    service_status = get_service_status()
    
    # 计算服务可用性
    total_services = len(service_status)
    up_services = sum(1 for s in service_status.values() if s['up'])
    availability = (up_services / total_services) * 100 if total_services > 0 else 0
    
    # 计算资源健康
    cpu_score = max(0, 100 - metrics['cpu_percent'])
    memory_score = max(0, 100 - metrics['memory_percent'])
    disk_score = max(0, 100 - metrics['disk_percent'])
    
    # 综合健康分 (加权平均)
    overall = (availability * 0.4 + 
               cpu_score * 0.2 + 
               memory_score * 0.2 + 
               disk_score * 0.2)
    
    # 趋势分析
    trends = analyze_trends()
    
    return {
        'overall_score': round(overall, 1),
        'availability': round(availability, 1),
        'cpu_score': round(cpu_score, 1),
        'memory_score': round(memory_score, 1),
        'disk_score': round(disk_score, 1),
        'metrics': metrics,
        'service_count': {'total': total_services, 'up': up_services},
        'trends': trends,
        'timestamp': datetime.now().isoformat()
    }

def analyze_trends():
    """分析指标趋势"""
    if len(metrics_history) < 10:
        return {'status': 'insufficient_data'}
    
    recent = list(metrics_history)[-10:]
    
    # 提取指标
    cpu_values = [m['cpu_percent'] for m in recent]
    memory_values = [m['memory_percent'] for m in recent]
    
    # 计算趋势 (简单线性回归斜率)
    def calc_trend(values):
        if len(values) < 2:
            return 0
        n = len(values)
        x = list(range(n))
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_xx = sum(x[i] * x[i] for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x) if (n * sum_xx - sum_x * sum_x) != 0 else 0
        return slope
    
    cpu_trend = calc_trend(cpu_values)
    memory_trend = calc_trend(memory_values)
    
    # 预测方向
    cpu_direction = 'rising' if cpu_trend > CONFIG["trend_threshold"] else ('falling' if cpu_trend < -CONFIG["trend_threshold"] else 'stable')
    memory_direction = 'rising' if memory_trend > CONFIG["trend_threshold"] else ('falling' if memory_trend < -CONFIG["trend_threshold"] else 'stable')
    
    return {
        'cpu_trend': round(cpu_trend, 2),
        'cpu_direction': cpu_direction,
        'memory_trend': round(memory_trend, 2),
        'memory_direction': memory_direction,
        'sample_count': len(recent)
    }

def predict_failures():
    """预测潜在故障"""
    global predictions
    
    metrics = get_metrics()
    trends = analyze_trends()
    
    # CPU 预测
    if metrics['cpu_percent'] > CONFIG["cpu_warning"]:
        severity = 'critical' if metrics['cpu_percent'] > CONFIG["cpu_critical"] else 'warning'
        prediction = {
            'type': 'cpu_overload',
            'service': 'system',
            'severity': severity,
            'probability': min(1.0, metrics['cpu_percent'] / 100),
            'description': f"CPU使用率 {metrics['cpu_percent']:.1f}% 超过阈值",
            'recommendation': '考虑扩容或优化CPU密集型任务',
            'timestamp': datetime.now().isoformat()
        }
        predictions.append(prediction)
    
    # 内存预测
    if metrics['memory_percent'] > CONFIG["memory_warning"]:
        severity = 'critical' if metrics['memory_percent'] > CONFIG["memory_critical"] else 'warning'
        prediction = {
            'type': 'memory_overload',
            'service': 'system',
            'severity': severity,
            'probability': min(1.0, metrics['memory_percent'] / 100),
            'description': f"内存使用率 {metrics['memory_percent']:.1f}% 超过阈值",
            'recommendation': '考虑释放内存或增加内存',
            'timestamp': datetime.now().isoformat()
        }
        predictions.append(prediction)
    
    # 趋势预测
    if trends.get('cpu_direction') == 'rising' and trends.get('cpu_trend', 0) > 0.5:
        prediction = {
            'type': 'cpu_trend_alert',
            'service': 'system',
            'severity': 'warning',
            'probability': 0.7,
            'description': "CPU使用率持续上升趋势",
            'recommendation': "监控CPU趋势，准备扩容",
            'timestamp': datetime.now().isoformat()
        }
        predictions.append(prediction)
    
    # 服务端口预测
    service_status = get_service_status()
    for port, info in service_status.items():
        if not info['up']:
            prediction = {
                'type': 'service_down',
                'service': info['name'],
                'severity': 'critical',
                'probability': 1.0,
                'description': f"服务 {info['name']} (端口{port}) 不可用",
                'recommendation': f"立即检查服务状态，重启服务",
                'timestamp': datetime.now().isoformat()
            }
            predictions.append(prediction)
    
    # 保持预测历史
    if len(predictions) > 100:
        predictions = predictions[-100:]

def schedule_maintenance():
    """生成预防性维护任务"""
    global maintenance_tasks
    
    metrics = get_metrics()
    health_score = calculate_health_score()
    
    # 基于健康评分生成维护任务
    if health_score['overall_score'] < 70:
        task = {
            'task_id': f"maint_{int(time.time())}",
            'type': 'health_check',
            'description': '系统健康评分低于70%，进行全面检查',
            'priority': 'high',
            'status': 'pending',
            'timestamp': datetime.now().isoformat()
        }
        maintenance_tasks.append(task)
    
    # 基于CPU使用率生成维护任务
    if metrics['cpu_percent'] > 80:
        task = {
            'task_id': f"maint_{int(time.time())}",
            'type': 'cpu_optimization',
            'description': f'CPU使用率过高 ({metrics["cpu_percent"]:.1f}%)，执行优化',
            'priority': 'medium',
            'status': 'pending',
            'timestamp': datetime.now().isoformat()
        }
        maintenance_tasks.append(task)
    
    # 基于内存使用率生成维护任务
    if metrics['memory_percent'] > 85:
        task = {
            'task_id': f"maint_{int(time.time())}",
            'type': 'memory_cleanup',
            'description': f'内存使用率过高 ({metrics["memory_percent"]:.1f}%)，执行清理',
            'priority': 'high',
            'status': 'pending',
            'timestamp': datetime.now().isoformat()
        }
        maintenance_tasks.append(task)
    
    # 保持任务历史
    if len(maintenance_tasks) > 50:
        maintenance_tasks = maintenance_tasks[-50:]

def background_predictor(interval=60):
    """后台预测线程"""
    while True:
        # 收集指标
        metrics = get_metrics()
        metrics_history.append(metrics)
        
        # 执行预测
        predict_failures()
        
        # 生成维护任务
        schedule_maintenance()
        
        time.sleep(interval)

if __name__ == '__main__':
    # 启动后台预测线程
    predictor_thread = threading.Thread(target=background_predictor, daemon=True)
    predictor_thread.start()
    
    # 启动HTTP服务
    server = HTTPServer(('0.0.0.0', PORT), PMHandler)
    print(f"Predictive Maintenance Service started on port {PORT}")
    print(f"Endpoints:")
    print(f"  /health            - 健康检查")
    print(f"  /predictions       - 故障预测")
    print(f"  /maintenance-tasks - 维护任务")
    print(f"  /health-score      - 健康评分")
    print(f"  /trends            - 趋势分析")
    print(f"  /status            - 服务状态")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()