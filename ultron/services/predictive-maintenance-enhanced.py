#!/usr/bin/env python3
"""
Agent服务健康预测增强系统
端口: 18152
- 与智能告警服务集成获取真实服务列表
- 增强的预测算法 (趋势分析 + 异常检测)
- 健康评分与建议
"""

import json
import time
import threading
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from collections import deque
import requests

app = Flask(__name__)

# ===== 配置 =====
SMART_ALERT_PORT = 18151  # 智能告警服务
DB_PATH = '/root/.openclaw/workspace/ultron/data/health_prediction.db'

# ===== 增强的故障预测引擎 =====
class EnhancedPredictor:
    def __init__(self):
        self.history = {}  # service -> deque of metrics
        self.predictions = {}  # service -> prediction
        self.alerts = []
        self.anomaly_threshold = 2.0  # 标准差倍数
        
    def add_metric(self, service: str, metric: dict):
        """添加指标数据用于预测"""
        if service not in self.history:
            self.history[service] = deque(maxlen=200)
        
        self.history[service].append({
            'timestamp': time.time(),
            'cpu': metric.get('cpu', 0),
            'memory': metric.get('memory', 0),
            'response_time': metric.get('response_time', 0),
            'error_rate': metric.get('error_rate', 0),
            'status': metric.get('status', 'unknown')
        })
        
    def calculate_trend(self, values: list) -> float:
        """计算趋势斜率"""
        if len(values) < 3:
            return 0
        n = len(values)
        x = list(range(n))
        y = values
        try:
            slope = (n * sum(x[i] * y[i] for i in range(n)) - sum(x) * sum(y)) / \
                    (n * sum(x[i] ** 2 for i in range(n)) - sum(x) ** 2)
            return slope
        except:
            return 0
            
    def detect_anomaly(self, values: list) -> bool:
        """异常检测"""
        if len(values) < 5:
            return False
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = variance ** 0.5
        if std == 0:
            return False
        # 检查最新值是否异常
        return abs(values[-1] - mean) > self.anomaly_threshold * std
        
    def calculate_health_score(self, history: list) -> float:
        """计算健康评分 (0-100)"""
        if not history:
            return 50
        
        recent = list(history)[-10:]
        
        # 响应时间评分
        response_times = [h['response_time'] for h in recent if h.get('response_time')]
        if response_times:
            avg_response = sum(response_times) / len(response_times)
            response_score = max(0, 100 - (avg_response / 10))  # 1000ms = 0分
        else:
            response_score = 50
            
        # 错误率评分
        error_rates = [h.get('error_rate', 0) for h in recent]
        avg_error = sum(error_rates) / len(error_rates) if error_rates else 0
        error_score = max(0, 100 - (avg_error * 100))
        
        # CPU评分
        cpu_values = [h.get('cpu', 0) for h in recent]
        avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 50
        cpu_score = max(0, 100 - avg_cpu)
        
        # 内存评分
        memory_values = [h.get('memory', 0) for h in recent]
        avg_memory = sum(memory_values) / len(memory_values) if memory_values else 50
        memory_score = max(0, 100 - avg_memory)
        
        # 综合评分
        health_score = (
            response_score * 0.3 +
            error_score * 0.3 +
            cpu_score * 0.2 +
            memory_score * 0.2
        )
        
        return round(health_score, 1)
        
    def predict(self, service: str) -> dict:
        """增强的故障预测"""
        if service not in self.history or len(self.history[service]) < 3:
            return {
                'risk_level': 'unknown', 
                'confidence': 0,
                'health_score': 50,
                'message': '数据不足'
            }
        
        recent = list(self.history[service])[-15:]
        
        # 提取指标
        cpu_values = [h['cpu'] for h in recent if h.get('cpu')]
        memory_values = [h['memory'] for h in recent if h.get('memory')]
        error_rates = [h.get('error_rate', 0) for h in recent]
        response_times = [h['response_time'] for h in recent if h.get('response_time')]
        
        # 计算趋势
        cpu_trend = self.calculate_trend(cpu_values) if len(cpu_values) >= 3 else 0
        memory_trend = self.calculate_trend(memory_values) if len(memory_values) >= 3 else 0
        error_trend = self.calculate_trend(error_rates) if len(error_rates) >= 3 else 0
        
        # 异常检测
        cpu_anomaly = self.detect_anomaly(cpu_values)
        memory_anomaly = self.detect_anomaly(memory_values)
        
        # 风险评分
        risk_score = 0
        risk_factors = []
        
        avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
        avg_memory = sum(memory_values) / len(memory_values) if memory_values else 0
        avg_error = sum(error_rates) / len(error_rates) if error_rates else 0
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        
        # CPU风险
        if avg_cpu > 80:
            risk_score += 25
            risk_factors.append(f'CPU过高 ({avg_cpu:.1f}%)')
        if cpu_trend > 2:  # 上升趋势
            risk_score += 15
            risk_factors.append('CPU上升趋势')
        if cpu_anomaly:
            risk_score += 20
            risk_factors.append('CPU异常波动')
            
        # 内存风险
        if avg_memory > 85:
            risk_score += 30
            risk_factors.append(f'内存过高 ({avg_memory:.1f}%)')
        if memory_trend > 2:
            risk_score += 15
            risk_factors.append('内存上升趋势')
        if memory_anomaly:
            risk_score += 20
            risk_factors.append('内存异常波动')
            
        # 错误率风险
        if avg_error > 5:
            risk_score += 25
            risk_factors.append(f'错误率过高 ({avg_error:.1f}%)')
        if error_trend > 0.5:
            risk_score += 15
            risk_factors.append('错误率上升趋势')
            
        # 响应时间风险
        if avg_response > 1000:
            risk_score += 15
            risk_factors.append(f'响应延迟 ({avg_response:.0f}ms)')
            
        # 计算健康评分
        health_score = self.calculate_health_score(recent)
        
        # 判断风险等级
        if risk_score >= 70:
            risk_level = 'critical'
        elif risk_score >= 40:
            risk_level = 'warning'
        elif risk_score >= 20:
            risk_level = 'caution'
        else:
            risk_level = 'normal'
            
        # 生成建议
        recommendations = []
        if avg_cpu > 70:
            recommendations.append('考虑扩容或优化CPU使用')
        if avg_memory > 80:
            recommendations.append('建议增加内存或清理缓存')
        if avg_error > 1:
            recommendations.append('检查服务错误日志')
        if avg_response > 500:
            recommendations.append('优化响应性能')
        if cpu_trend > 1 or memory_trend > 1:
            recommendations.append('趋势显示资源使用增长，建议监控')
            
        return {
            'service': service,
            'risk_level': risk_level,
            'risk_score': min(100, risk_score),
            'confidence': min(95, len(recent) * 6),
            'health_score': health_score,
            'factors': risk_factors,
            'trends': {
                'cpu': round(cpu_trend, 2),
                'memory': round(memory_trend, 2),
                'error': round(error_trend, 2)
            },
            'anomalies': {
                'cpu': cpu_anomaly,
                'memory': memory_anomaly
            },
            'recommendations': recommendations,
            'predicted_at': datetime.now().isoformat()
        }
        
    def get_all_predictions(self, services: dict) -> dict:
        """获取所有服务的预测"""
        predictions = {}
        for port, info in services.items():
            predictions[info['name']] = self.predict(info['name'])
        return predictions

# ===== 指标收集器 =====
class MetricsCollector:
    def __init__(self):
        self.predictor = EnhancedPredictor()
        
    def get_services_from_alert(self) -> dict:
        """从智能告警服务获取服务列表"""
        try:
            resp = requests.get(f'http://localhost:{SMART_ALERT_PORT}/api/services', timeout=3)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return {}
        
    def get_real_metrics(self, port: int) -> dict:
        """获取真实指标"""
        try:
            resp = requests.get(f'http://localhost:{port}/health', timeout=2)
            elapsed = resp.elapsed.total_seconds() * 1000
            
            # 获取系统指标
            metrics = {
                'response_time': elapsed,
                'status': 'healthy' if resp.status_code == 200 else 'unhealthy',
                'error_rate': 0 if resp.status_code == 200 else 10
            }
            
            # 尝试获取更多指标
            try:
                sys_resp = requests.get(f'http://localhost:{port}/metrics', timeout=1)
                if sys_resp.status_code == 200:
                    data = sys_resp.json()
                    metrics.update(data)
            except:
                pass
                
            # 如果没有真实CPU/内存，使用基于响应时间的估算
            if 'cpu' not in metrics:
                metrics['cpu'] = min(95, 20 + (elapsed / 50))
            if 'memory' not in metrics:
                metrics['memory'] = min(90, 30 + (elapsed / 100))
                
            return metrics
        except requests.exceptions.ConnectionError:
            return {
                'response_time': 9999,
                'status': 'unavailable',
                'cpu': 0,
                'memory': 0,
                'error_rate': 100
            }
        except Exception as e:
            return {
                'response_time': 5000,
                'status': 'error',
                'error': str(e)
            }
            
    def collect_all(self):
        """收集所有服务指标"""
        services = self.get_services_from_alert()
        metrics = {}
        
        for port, info in services.items():
            try:
                port_int = int(port)
                m = self.get_real_metrics(port_int)
                m['name'] = info.get('name', f'service-{port}')
                m['port'] = port
                metrics[port] = m
                
                # 添加到预测器
                self.predictor.add_metric(info.get('name', f'service-{port}'), m)
            except:
                pass
                
        return metrics, services

# 全局实例
collector = MetricsCollector()
predictor = collector.predictor

# ===== API 端点 =====
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'health-prediction-enhanced', 'port': 18152})

@app.route('/api/services')
def services():
    """获取监控的服务列表"""
    _, services = collector.collect_all()
    return jsonify(services)

@app.route('/api/metrics')
def metrics():
    """获取当前指标"""
    metrics_data, _ = collector.collect_all()
    return jsonify(metrics_data)

@app.route('/api/predict/<service_name>')
def get_prediction(service_name):
    """获取指定服务的预测"""
    prediction = predictor.predict(service_name)
    return jsonify(prediction)

@app.route('/api/predictions')
def all_predictions():
    """获取所有服务的预测"""
    _, services = collector.collect_all()
    predictions = predictor.get_all_predictions(services)
    return jsonify(predictions)

@app.route('/api/health-score')
def health_scores():
    """获取所有服务的健康评分"""
    _, services = collector.collect_all()
    scores = {}
    for port, info in services.items():
        name = info.get('name', f'service-{port}')
        pred = predictor.predict(name)
        scores[name] = {
            'health_score': pred.get('health_score', 50),
            'risk_level': pred.get('risk_level', 'unknown'),
            'port': port
        }
    return jsonify(scores)

@app.route('/api/alerts')
def alerts():
    """获取当前告警"""
    _, services = collector.collect_all()
    current_alerts = []
    
    for port, info in services.items():
        name = info.get('name', f'service-{port}')
        pred = predictor.predict(name)
        
        if pred['risk_level'] in ['critical', 'warning']:
            current_alerts.append({
                'service': name,
                'port': port,
                'level': pred['risk_level'],
                'health_score': pred.get('health_score', 50),
                'risk_score': pred.get('risk_score', 0),
                'factors': pred.get('factors', []),
                'recommendations': pred.get('recommendations', []),
                'timestamp': datetime.now().isoformat()
            })
    
    return jsonify({'alerts': current_alerts, 'count': len(current_alerts)})

# ===== 定期收集 =====
def background_collector():
    """后台定期收集指标"""
    while True:
        try:
            collector.collect_all()
        except:
            pass
        time.sleep(20)  # 每20秒收集一次

if __name__ == '__main__':
    # 启动后台收集
    threading.Thread(target=background_collector, daemon=True).start()
    
    print('🔮 Agent服务健康预测增强系统启动 (端口 18152)')
    print('   - 与智能告警服务集成')
    print('   - 趋势分析与异常检测')
    print('   - 健康评分与建议')
    
    app.run(host='0.0.0.0', port=18152, debug=False)