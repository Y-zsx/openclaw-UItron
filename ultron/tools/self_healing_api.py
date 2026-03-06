#!/usr/bin/env python3
"""
系统自愈与自动修复API服务
端口: 18226
提供自动检测、诊断、修复系统问题的REST API
"""
import json
import subprocess
import time
import psutil
import requests
import socket
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
from threading import Thread, Lock

app = Flask(__name__)

# ============ 配置 ============
DATA_DIR = Path("/root/.openclaw/workspace/ultron/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "self_healing.db"

# 监控端口
MONITORED_PORTS = {
    18100: "workflow_engine",
    18120: "decision_engine",
    18128: "automation",
    18150: "agent_network",
    18160: "agent_executor",
    18170: "alert_integration",
    18200: "ops_dashboard",
    18210: "executor_api",
    18224: "alert_report",
    18225: "alert_prediction",
}

# 关键服务
CRITICAL_SERVICES = [
    "openclaw",
    "nginx",
    "docker",
]

# 告警阈值
THRESHOLDS = {
    "cpu": 80.0,
    "memory": 85.0,
    "disk": 90.0,
}

# 线程锁
lock = Lock()
healing_history = []

# ============ 数据库 ============
def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS healing_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  issue_type TEXT,
                  issue_detail TEXT,
                  action_taken TEXT,
                  status TEXT,
                  result TEXT)''')
    conn.commit()
    conn.close()

def log_healing(issue_type, issue_detail, action_taken, status, result):
    timestamp = datetime.now().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("INSERT INTO healing_history (timestamp, issue_type, issue_detail, action_taken, status, result) VALUES (?, ?, ?, ?, ?, ?)",
              (timestamp, issue_type, issue_detail, action_taken, status, result))
    conn.commit()
    conn.close()
    return {
        "timestamp": timestamp,
        "issue_type": issue_type,
        "issue_detail": issue_detail,
        "action_taken": action_taken,
        "status": status,
        "result": result
    }

# ============ 检测函数 ============
def check_port(port):
    """检查端口是否在监听"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def check_service(service_name):
    """检查systemd服务状态"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == "active"
    except:
        return False

def check_process(process_name):
    """检查进程是否在运行"""
    for proc in psutil.process_iter(['name']):
        try:
            if process_name in proc.info['name']:
                return True
        except:
            pass
    return False

def get_system_health():
    """获取系统健康状态"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
    }

def get_port_status():
    """获取所有监控端口状态"""
    status = {}
    for port, name in MONITORED_PORTS.items():
        status[name] = {
            "port": port,
            "healthy": check_port(port),
            "timestamp": datetime.now().isoformat()
        }
    return status

# ============ 修复函数 ============
def restart_service(service_name):
    """重启systemd服务"""
    try:
        subprocess.run(["systemctl", "restart", service_name], timeout=30)
        time.sleep(2)
        return check_service(service_name)
    except Exception as e:
        return False, str(e)

def kill_and_restart_process(process_name, start_cmd):
    """杀掉并重启进程"""
    try:
        # 杀掉进程
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if process_name in proc.info['name']:
                    proc.kill()
            except:
                pass
        time.sleep(1)
        # 启动新进程
        subprocess.Popen(start_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        return True
    except Exception as e:
        return False, str(e)

def restart_port_service(port, service_name):
    """重启端口对应的服务"""
    # 尝试通过systemctl重启
    service_map = {
        "workflow_engine": "workflow-engine",
        "decision_engine": "decision-engine",
        "automation": "decision-automation",
        "agent_network": "agent-gateway",
    }
    svc = service_map.get(service_name, service_name)
    if check_service(svc):
        return restart_service(svc)
    return False, "Service not found in systemd"

def clear_temp_files():
    """清理临时文件"""
    try:
        subprocess.run(["find", "/tmp", "-type", "f", "-mtime", "+1", "-delete"], timeout=30)
        return True
    except:
        return False

def free_memory():
    """释放内存"""
    try:
        # 清理缓存
        subprocess.run(["sync"], capture_output=True)
        subprocess.run(["echo", "3", ">", "/proc/sys/vm/drop_caches"], shell=True, capture_output=True)
        return True
    except:
        return False

# ============ 自愈引擎 ============
class SelfHealingEngine:
    def __init__(self):
        self.issues_found = []
        self.actions_taken = []
    
    def heal_port_issue(self, port, name):
        """修复端口问题"""
        action = f"Attempting to restart {name} on port {port}"
        healthy = check_port(port)
        if not healthy:
            # 尝试重启相关服务
            result = restart_port_service(port, name)
            if result is True:
                return log_healing("port_down", f"Port {port} ({name})", action, "success", "Service restarted")
            else:
                return log_healing("port_down", f"Port {port} ({name})", action, "failed", str(result))
        return None
    
    def heal_high_cpu(self):
        """处理高CPU使用率"""
        cpu = psutil.cpu_percent(interval=1)
        if cpu > THRESHOLDS["cpu"]:
            # 查找高CPU进程
            high_cpu_procs = []
            for proc in psutil.process_iter(['name', 'cpu_percent']):
                try:
                    if proc.info['cpu_percent'] and proc.info['cpu_percent'] > 50:
                        high_cpu_procs.append(proc.info['name'])
                except:
                    pass
            
            action = f"CPU usage high: {cpu}%, killing high CPU processes: {high_cpu_procs[:3]}"
            # 不直接杀死进程，记录告警
            return log_healing("high_cpu", f"CPU {cpu}%", action, "alerted", "Not auto-healing high CPU, manual intervention needed")
        return None
    
    def heal_high_memory(self):
        """处理高内存使用率"""
        mem = psutil.virtual_memory().percent
        if mem > THRESHOLDS["memory"]:
            action = f"Memory usage high: {mem}%, attempting to free memory"
            if free_memory():
                return log_healing("high_memory", f"Memory {mem}%", action, "success", "Memory freed")
            return log_healing("high_memory", f"Memory {mem}%", action, "failed", "Could not free memory")
        return None
    
    def heal_high_disk(self):
        """处理高磁盘使用率"""
        disk = psutil.disk_usage('/').percent
        if disk > THRESHOLDS["disk"]:
            action = f"Disk usage high: {disk}%, attempting cleanup"
            if clear_temp_files():
                return log_healing("high_disk", f"Disk {disk}%", action, "success", "Temp files cleared")
            return log_healing("high_disk", f"Disk {disk}%", action, "failed", "Cleanup failed")
        return None
    
    def run_healing_cycle(self):
        """运行完整的自愈检查周期"""
        results = []
        
        # 检查端口
        for port, name in MONITORED_PORTS.items():
            if not check_port(port):
                result = self.heal_port_issue(port, name)
                if result:
                    results.append(result)
        
        # 检查系统资源
        cpu_result = self.heal_high_cpu()
        if cpu_result:
            results.append(cpu_result)
        
        mem_result = self.heal_high_memory()
        if mem_result:
            results.append(mem_result)
        
        disk_result = self.heal_high_disk()
        if disk_result:
            results.append(disk_result)
        
        return results

# 全局引擎
engine = SelfHealingEngine()

# ============ API 端点 ============
@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "service": "self_healing_api",
        "port": 18226,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/health', methods=['GET'])
def api_health():
    """获取系统健康状态"""
    health = get_system_health()
    port_status = get_port_status()
    
    # 汇总健康状态
    healthy_ports = sum(1 for p in port_status.values() if p['healthy'])
    total_ports = len(port_status)
    
    return jsonify({
        "system": health,
        "ports": port_status,
        "summary": {
            "cpu_status": "ok" if health["cpu_percent"] < THRESHOLDS["cpu"] else "warning",
            "memory_status": "ok" if health["memory_percent"] < THRESHOLDS["memory"] else "warning",
            "disk_status": "ok" if health["disk_percent"] < THRESHOLDS["disk"] else "warning",
            "ports_healthy": f"{healthy_ports}/{total_ports}",
            "overall": "healthy" if healthy_ports == total_ports else "degraded"
        }
    })

@app.route('/api/heal', methods=['POST'])
def trigger_heal():
    """触发自愈操作"""
    with lock:
        data = request.get_json() or {}
        heal_type = data.get('type', 'all')
        
        if heal_type == 'all':
            results = engine.run_healing_cycle()
        elif heal_type == 'ports':
            results = []
            for port, name in MONITORED_PORTS.items():
                if not check_port(port):
                    result = engine.heal_port_issue(port, name)
                    if result:
                        results.append(result)
        elif heal_type == 'cpu':
            result = engine.heal_high_cpu()
            results = [result] if result else []
        elif heal_type == 'memory':
            result = engine.heal_high_memory()
            results = [result] if result else []
        elif heal_type == 'disk':
            result = engine.heal_high_disk()
            results = [result] if result else []
        else:
            results = [{"error": f"Unknown heal type: {heal_type}"}]
        
        return jsonify({
            "heal_type": heal_type,
            "results": results,
            "timestamp": datetime.now().isoformat()
        })

@app.route('/api/ports', methods=['GET'])
def list_ports():
    """列出所有监控端口状态"""
    return jsonify(get_port_status())

@app.route('/api/ports/<int:port>', methods=['POST'])
def heal_port(port):
    """修复特定端口"""
    name = MONITORED_PORTS.get(port, "unknown")
    with lock:
        result = engine.heal_port_issue(port, name)
        if result:
            return jsonify(result)
        return jsonify({
            "status": "ok",
            "message": f"Port {port} is healthy"
        })

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取修复历史"""
    limit = request.args.get('limit', 20, type=int)
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT timestamp, issue_type, issue_detail, action_taken, status, result FROM healing_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    history = [
        {
            "timestamp": r[0],
            "issue_type": r[1],
            "issue_detail": r[2],
            "action_taken": r[3],
            "status": r[4],
            "result": r[5]
        }
        for r in rows
    ]
    return jsonify(history)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取自愈统计"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM healing_history")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM healing_history WHERE status = 'success'")
    success = c.fetchone()[0]
    
    c.execute("SELECT issue_type, COUNT(*) FROM healing_history GROUP BY issue_type")
    by_type = dict(c.fetchall())
    
    c.execute("SELECT DATE(timestamp) as date, COUNT(*) FROM healing_history GROUP BY date ORDER BY date DESC LIMIT 7")
    by_date = dict(c.fetchall())
    
    conn.close()
    
    return jsonify({
        "total_heals": total,
        "successful_heals": success,
        "success_rate": f"{(success/total*100):.1f}%" if total > 0 else "N/A",
        "by_type": by_type,
        "by_date": by_date
    })

@app.route('/api/thresholds', methods=['GET', 'POST'])
def thresholds():
    """获取或设置阈值"""
    global THRESHOLDS
    
    if request.method == 'POST':
        data = request.get_json()
        for key in ['cpu', 'memory', 'disk']:
            if key in data:
                THRESHOLDS[key] = float(data[key])
        return jsonify({"thresholds": THRESHOLDS})
    
    return jsonify({"thresholds": THRESHOLDS})

# ============ 主程序 ============
if __name__ == '__main__':
    init_db()
    print(f"Starting Self-Healing API on port 18226...")
    app.run(host='0.0.0.0', port=18226, debug=False)