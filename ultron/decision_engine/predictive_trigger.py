#!/usr/bin/env python3
"""
Predictive Decision Trigger System
决策自动化增强 - 预测性触发器

基于机器学习的预测性触发，在问题发生前提前预警和自动决策
"""

import json
import time
import threading
import requests
from datetime import datetime, timedelta
from collections import deque
from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# 配置
CONFIG = {
    "port": 18260,
    "prediction_window": 300,  # 5分钟预测窗口
    "cpu_threshold": 80,
    "memory_threshold": 85,
    "history_size": 100
}

# 存储历史数据
class MetricsStore:
    def __init__(self):
        self.cpu_history = deque(maxlen=CONFIG["history_size"])
        self.memory_history = deque(maxlen=CONFIG["history_size"])
        self.disk_history = deque(maxlen=CONFIG["history_size"])
        self.predictions = deque(maxlen=50)
        self.db_path = "/root/.openclaw/workspace/ultron/decision_engine/predictive_triggers.db"
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS predictions
                    (id INTEGER PRIMARY KEY, timestamp TEXT, metric TEXT,
                     current_value REAL, predicted_value REAL, confidence REAL,
                     trigger_action TEXT, triggered INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS trigger_executions
                    (id INTEGER PRIMARY KEY, timestamp TEXT, trigger_id TEXT,
                     prediction_id INTEGER, action TEXT, result TEXT)''')
        conn.commit()
        conn.close()
    
    def add_metrics(self, cpu, memory, disk):
        now = datetime.now().isoformat()
        self.cpu_history.append({"timestamp": now, "value": cpu})
        self.memory_history.append({"timestamp": now, "value": memory})
        self.disk_history.append({"timestamp": now, "value": disk})
    
    def predict_cpu(self):
        """简单线性回归预测CPU使用率"""
        if len(self.cpu_history) < 10:
            return None, 0
        
        values = [m["value"] for m in self.cpu_history]
        n = len(values)
        
        # 简单移动平均 + 趋势预测
        avg = sum(values[-5:]) / 5
        trend = (values[-1] - values[0]) / n if n > 1 else 0
        
        # 预测未来5分钟
        predicted = avg + trend * 3
        
        # 计算置信度
        variance = sum((v - avg) ** 2 for v in values[-5:]) / 5
        confidence = max(0, min(100, 100 - variance))
        
        return predicted, confidence
    
    def predict_memory(self):
        """预测内存使用率"""
        if len(self.memory_history) < 10:
            return None, 0
        
        values = [m["value"] for m in self.memory_history]
        n = len(values)
        
        avg = sum(values[-5:]) / 5
        trend = (values[-1] - values[0]) / n if n > 1 else 0
        predicted = avg + trend * 3
        
        variance = sum((v - avg) ** 2 for v in values[-5:]) / 5
        confidence = max(0, min(100, 100 - variance))
        
        return predicted, confidence
    
    def save_prediction(self, metric, current, predicted, confidence, action):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO predictions 
                    (timestamp, metric, current_value, predicted_value, confidence, trigger_action)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (datetime.now().isoformat(), metric, current, predicted, confidence, action))
        pred_id = c.lastrowid
        conn.commit()
        conn.close()
        return pred_id
    
    def record_execution(self, trigger_id, prediction_id, action, result):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO trigger_executions 
                    (timestamp, trigger_id, prediction_id, action, result)
                    VALUES (?, ?, ?, ?, ?)''',
                 (datetime.now().isoformat(), trigger_id, prediction_id, action, result))
        conn.commit()
        conn.close()

store = MetricsStore()

def get_system_metrics():
    """获取当前系统指标"""
    try:
        # 从健康检查API获取
        resp = requests.get("http://localhost:18105/api/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "cpu": data.get("cpu_percent", 0),
                "memory": data.get("memory_percent", 0),
                "disk": data.get("disk_percent", 0)
            }
    except:
        pass
    
    # 备用方案: 直接从系统获取
    try:
        import psutil
        return {
            "cpu": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent
        }
    except:
        return {"cpu": 0, "memory": 0, "disk": 0}

def trigger_decision(metric, predicted_value, confidence):
    """触发决策引擎"""
    try:
        payload = {
            "context": f"predictive_{metric}_alert",
            "data": {
                "metric": metric,
                "predicted_value": predicted_value,
                "confidence": confidence,
                "trigger_type": "predictive"
            },
            "auto_approve": confidence > 70
        }
        resp = requests.post("http://localhost:18120/api/decide", 
                           json=payload, timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except Exception as e:
        print(f"Decision trigger failed: {e}")
        return None

def check_and_trigger():
    """检查预测并触发决策"""
    metrics = get_system_metrics()
    store.add_metrics(metrics["cpu"], metrics["memory"], metrics["disk"])
    
    # 预测CPU
    pred_cpu, conf_cpu = store.predict_cpu()
    if pred_cpu and pred_cpu > CONFIG["cpu_threshold"] and conf_cpu > 50:
        action = f"predictive_cpu_high_{int(pred_cpu)}"
        pred_id = store.save_prediction("cpu", metrics["cpu"], pred_cpu, conf_cpu, action)
        result = trigger_decision("cpu", pred_cpu, conf_cpu)
        store.record_execution("predictive-cpu", pred_id, action, json.dumps(result) if result else "failed")
        print(f"[PREDICTIVE] CPU预测高位: {pred_cpu:.1f}%, 置信度: {conf_cpu:.1f}%")
    
    # 预测内存
    pred_mem, conf_mem = store.predict_memory()
    if pred_mem and pred_mem > CONFIG["memory_threshold"] and conf_mem > 50:
        action = f"predictive_memory_high_{int(pred_mem)}"
        pred_id = store.save_prediction("memory", metrics["memory"], pred_mem, conf_mem, action)
        result = trigger_decision("memory", pred_mem, conf_mem)
        store.record_execution("predictive-memory", pred_id, action, json.dumps(result) if result else "failed")
        print(f"[PREDICTIVE] 内存预测高位: {pred_mem:.1f}%, 置信度: {conf_mem:.1f}%")

def prediction_loop():
    """预测循环"""
    while True:
        try:
            check_and_trigger()
        except Exception as e:
            print(f"Prediction error: {e}")
        time.sleep(60)  # 每分钟预测一次

# API端点
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"service": "predictive-trigger", "status": "ok"})

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    return jsonify({
        "cpu": list(store.cpu_history),
        "memory": list(store.memory_history),
        "disk": list(store.disk_history)
    })

@app.route('/api/predict', methods=['GET'])
def predict():
    pred_cpu, conf_cpu = store.predict_cpu()
    pred_mem, conf_mem = store.predict_memory()
    
    return jsonify({
        "cpu": {"predicted": pred_cpu, "confidence": conf_cpu} if pred_cpu else None,
        "memory": {"predicted": pred_mem, "confidence": conf_mem} if pred_mem else None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    conn = sqlite3.connect(store.db_path)
    c = conn.cursor()
    c.execute("SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()
    
    predictions = []
    for r in rows:
        predictions.append({
            "id": r[0], "timestamp": r[1], "metric": r[2],
            "current": r[3], "predicted": r[4], "confidence": r[5],
            "action": r[6], "triggered": bool(r[7])
        })
    return jsonify(predictions)

@app.route('/api/trigger', methods=['POST'])
def manual_trigger():
    data = request.json
    metric = data.get("metric", "cpu")
    threshold = data.get("threshold", 80)
    
    if metric == "cpu":
        pred, conf = store.predict_cpu()
    else:
        pred, conf = store.predict_memory()
    
    if pred and pred > threshold:
        result = trigger_decision(metric, pred, conf)
        return jsonify({"predicted": pred, "confidence": conf, "decision": result})
    
    return jsonify({"predicted": pred, "confidence": conf, "triggered": False})

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        CONFIG.update(request.json)
        return jsonify({"status": "ok", "config": CONFIG})
    return jsonify(CONFIG)

if __name__ == '__main__':
    # 启动预测线程
    t = threading.Thread(target=prediction_loop, daemon=True)
    t.start()
    
    # 启动API服务
    app.run(host='0.0.0.0', port=CONFIG["port"], debug=False)