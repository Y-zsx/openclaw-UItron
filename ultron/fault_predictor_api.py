#!/usr/bin/env python3
"""
Agent服务故障预测与预防性维护系统
故障预测API - 端口18238
"""

import sqlite3
import json
import time
import psutil
import os
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

DB_PATH = "/root/.openclaw/workspace/ultron/fault_predictor.db"
PORT = 18238

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 故障预测记录
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
    
    # 预防性维护记录
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT,
        action TEXT,
        status TEXT,
        result TEXT,
        created_at TEXT
    )''')
    
    # 系统基线指标
    c.execute('''CREATE TABLE IF NOT EXISTS baselines (
        metric_name TEXT PRIMARY KEY,
        avg_value REAL,
        min_value REAL,
        max_value REAL,
        std_dev REAL,
        updated_at TEXT
    )''')
    
    conn.commit()
    conn.close()

def get_system_metrics():
    """获取系统指标"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
        "process_count": len(psutil.pids()),
        "network_connections": len(psutil.net_connections())
    }

def analyze_agent_health():
    """分析Agent健康状态并预测故障"""
    predictions = []
    
    # CPU使用率预测
    cpu = psutil.cpu_percent(interval=1)
    if cpu > 80:
        predictions.append({
            "fault_type": "HIGH_CPU_USAGE",
            "probability": min(0.95, (cpu - 80) / 20 + 0.5),
            "severity": "HIGH" if cpu > 90 else "MEDIUM",
            "evidence": f"CPU使用率: {cpu}%",
            "recommendation": "考虑扩容或优化CPU密集型任务"
        })
    elif cpu > 60:
        predictions.append({
            "fault_type": "ELEVATED_CPU",
            "probability": min(0.7, (cpu - 60) / 40 + 0.3),
            "severity": "LOW",
            "evidence": f"CPU使用率: {cpu}%",
            "recommendation": "监控CPU趋势，准备扩容方案"
        })
    
    # 内存预测
    mem = psutil.virtual_memory()
    if mem.percent > 90:
        predictions.append({
            "fault_type": "MEMORY_EXHAUSTION",
            "probability": 0.95,
            "severity": "CRITICAL",
            "evidence": f"内存使用: {mem.percent}%, 可用: {mem.available / (1024**3):.2f}GB",
            "recommendation": "立即清理内存或重启非关键服务"
        })
    elif mem.percent > 75:
        predictions.append({
            "fault_type": "HIGH_MEMORY",
            "probability": min(0.8, (mem.percent - 75) / 25 + 0.4),
            "severity": "MEDIUM",
            "evidence": f"内存使用: {mem.percent}%",
            "recommendation": "监控内存增长趋势，考虑增加swap"
        })
    
    # 磁盘预测
    disk = psutil.disk_usage('/')
    if disk.percent > 90:
        predictions.append({
            "fault_type": "DISK_FULL",
            "probability": 0.95,
            "severity": "CRITICAL",
            "evidence": f"磁盘使用: {disk.percent}%, 可用: {disk.free / (1024**3):.2f}GB",
            "recommendation": "立即清理磁盘空间"
        })
    elif disk.percent > 80:
        predictions.append({
            "fault_type": "DISK_WARNING",
            "probability": min(0.7, (disk.percent - 80) / 20 + 0.3),
            "severity": "MEDIUM",
            "evidence": f"磁盘使用: {disk.percent}%",
            "recommendation": "清理日志和临时文件"
        })
    
    # 进程健康检查
    critical_processes = ["openclaw-gateway", "python3"]
    for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            pinfo = proc.info
            if pinfo['name'] in critical_processes:
                if pinfo['cpu_percent'] and pinfo['cpu_percent'] > 50:
                    predictions.append({
                        "fault_type": "PROCESS_HIGH_CPU",
                        "probability": min(0.85, pinfo['cpu_percent'] / 100),
                        "severity": "MEDIUM",
                        "evidence": f"进程 {pinfo['name']} CPU: {pinfo['cpu_percent']}%",
                        "recommendation": f"检查进程 {pinfo['name']} 是否正常"
                    })
                if pinfo['memory_percent'] and pinfo['memory_percent'] > 30:
                    predictions.append({
                        "fault_type": "PROCESS_HIGH_MEM",
                        "probability": min(0.8, pinfo['memory_percent'] / 50),
                        "severity": "MEDIUM",
                        "evidence": f"进程 {pinfo['name']} 内存: {pinfo['memory_percent']}%",
                        "recommendation": f"监控进程 {pinfo['name']} 内存泄漏"
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # 网络连接数异常检测
    net_conns = len(psutil.net_connections())
    if net_conns > 1000:
        predictions.append({
            "fault_type": "NETWORK_CONNECTION_LEAK",
            "probability": min(0.9, net_conns / 2000),
            "severity": "HIGH",
            "evidence": f"网络连接数: {net_conns}",
            "recommendation": "检查是否存在连接泄漏"
        })
    
    return predictions

def save_prediction(prediction):
    """保存预测结果"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO predictions 
        (agent_id, fault_type, probability, severity, evidence, recommendation, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        ("system", prediction["fault_type"], prediction["probability"],
         prediction["severity"], prediction["evidence"], prediction["recommendation"],
         datetime.now().isoformat()))
    conn.commit()
    pred_id = c.lastrowid
    conn.close()
    return pred_id

def get_predictions(limit=20):
    """获取预测列表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, agent_id, fault_type, probability, severity, 
        evidence, recommendation, created_at, resolved 
        FROM predictions ORDER BY created_at DESC LIMIT ?''', (limit,))
    rows = c.fetchall()
    conn.close()
    
    return [{
        "id": r[0], "agent_id": r[1], "fault_type": r[2],
        "probability": r[3], "severity": r[4], "evidence": r[5],
        "recommendation": r[6], "created_at": r[7], "resolved": bool(r[8])
    } for r in rows]

def perform_maintenance(action, target="system"):
    """执行预防性维护"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    result = {"action": action, "target": target, "status": "success", "details": []}
    
    if action == "clear_cache":
        # 清理缓存
        import subprocess
        try:
            subprocess.run(["sync"], check=False)
            subprocess.run(["echo", "3", ">", "/proc/sys/vm/drop_caches"], shell=True, check=False)
            result["details"].append("系统缓存已清理")
        except Exception as e:
            result["status"] = "failed"
            result["details"].append(f"清理失败: {str(e)}")
    
    elif action == "restart_gateway":
        # 重启Gateway
        import subprocess
        try:
            subprocess.run(["openclaw", "gateway", "restart"], check=True)
            result["details"].append("Gateway已重启")
        except Exception as e:
            result["status"] = "failed"
            result["details"].append(f"重启失败: {str(e)}")
    
    elif action == "clear_old_logs":
        # 清理旧日志
        import subprocess
        try:
            subprocess.run(["find", "/root/.openclaw/logs", "-type", "f", "-mtime", "+7", "-delete"], check=False)
            result["details"].append("7天前的日志已清理")
        except Exception as e:
            result["status"] = "failed"
            result["details"].append(f"清理失败: {str(e)}")
    
    # 记录维护操作
    c.execute('''INSERT INTO maintenance_logs (agent_id, action, status, result, created_at)
        VALUES (?, ?, ?, ?, ?)''',
        (target, action, result["status"], json.dumps(result), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return result

def get_maintenance_history(limit=20):
    """获取维护历史"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT id, agent_id, action, status, result, created_at
        FROM maintenance_logs ORDER BY created_at DESC LIMIT ?''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "agent_id": r[1], "action": r[2], "status": r[3],
             "result": json.loads(r[4]), "created_at": r[5]} for r in rows]

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        if path == '/health':
            resp = {"status": "ok", "service": "fault-predictor", "port": PORT}
        elif path == '/metrics':
            resp = get_system_metrics()
        elif path == '/analyze':
            preds = analyze_agent_health()
            # 保存预测
            for p in preds:
                save_prediction(p)
            resp = {"predictions": preds, "count": len(preds)}
        elif path == '/predictions':
            limit = int(params.get('limit', [20])[0])
            resp = {"predictions": get_predictions(limit), "count": len(get_predictions(limit))}
        elif path == '/maintenance':
            resp = {"history": get_maintenance_history(), "count": len(get_maintenance_history())}
        else:
            resp = {"error": "Not found", "paths": ["/health", "/metrics", "/analyze", "/predictions", "/maintenance"]}
        
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode())
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode() if length > 0 else "{}"
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == '/maintenance':
            action = data.get('action', 'clear_cache')
            target = data.get('target', 'system')
            resp = perform_maintenance(action, target)
        elif path == '/resolve':
            pred_id = data.get('prediction_id')
            if pred_id:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE predictions SET resolved = 1 WHERE id = ?", (pred_id,))
                conn.commit()
                conn.close()
                resp = {"status": "resolved", "prediction_id": pred_id}
            else:
                resp = {"error": "prediction_id required"}
        else:
            resp = {"error": "Not found"}
        
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode())
    
    def log_message(self, format, *args):
        pass  # 禁用日志

def run_server():
    init_db()
    server = HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"故障预测API启动: http://0.0.0.0:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()