#!/usr/bin/env python3
"""
系统自愈与自动修复服务
自动检测和修复系统问题
端口: 18226
"""

import json
import os
import subprocess
import time
import psutil
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

app = Flask(__name__)

CONFIG_FILE = "/root/.openclaw/workspace/ultron/data/self_heal_config.json"
LOG_FILE = "/root/.openclaw/workspace/ultron/logs/self_heal.log"

# 默认配置
DEFAULT_CONFIG = {
    "enabled": True,
    "check_interval": 60,  # 秒
    "auto_repair": True,
    "health_check": {
        "enabled": True,
        "services": [],
        "ports": [18190, 18192, 18195, 18217, 18218, 18219, 18221, 18222, 18223, 18224, 18225]
    },
    "resource_limits": {
        "cpu_warning": 80,
        "cpu_critical": 95,
        "memory_warning": 80,
        "memory_critical": 95,
        "disk_warning": 80,
        "disk_critical": 95
    },
    "repair_actions": {
        "restart_service": True,
        "clear_cache": True,
        "kill_zombie": True
    }
}

def init_dirs():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def load_config():
    init_dirs()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def log_action(action, details):
    """记录操作日志"""
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }) + "\n")

def check_service_health(port):
    """检查服务健康状态"""
    import requests
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=3)
        return {
            "port": port,
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "response_time": response.elapsed.total_seconds() * 1000
        }
    except Exception as e:
        return {
            "port": port,
            "status": "down",
            "error": str(e)[:50]
        }

def get_system_resources():
    """获取系统资源使用情况"""
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "cpu_percent": cpu,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024**3), 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 2)
    }

def find_unresponsive_processes():
    """查找不响应进程"""
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent', 'cmdline']):
        try:
            if p.info['status'] == psutil.STATUS_ZOMBIE:
                processes.append({
                    "pid": p.info['pid'],
                    "name": p.info['name'],
                    "type": "zombie",
                    "action": "需要手动清理"
                })
            elif p.info['cpu_percent'] and p.info['cpu_percent'] > 90:
                processes.append({
                    "pid": p.info['pid'],
                    "name": p.info['name'],
                    "type": "high_cpu",
                    "cpu": p.info['cpu_percent'],
                    "action": "建议重启"
                })
        except:
            pass
    return processes

def restart_service_by_port(port):
    """根据端口重启服务"""
    # 查找占用该端口的进程
    result = subprocess.run(
        ["lsof", "-t", f"-i:{port}"],
        capture_output=True,
        text=True
    )
    
    if result.stdout:
        pid = int(result.stdout.strip().split('\n')[0])
        try:
            process = psutil.Process(pid)
            cmdline = process.cmdline()
            
            log_action("restart_attempt", {"port": port, "pid": pid, "cmdline": cmdline[:2]})
            
            # 优雅停止
            process.terminate()
            time.sleep(2)
            
            # 如果还在运行，强制杀死
            if process.is_running():
                process.kill()
            
            time.sleep(1)
            
            # 重启服务
            if cmdline:
                subprocess.Popen(cmdline, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log_action("restart_success", {"port": port, "pid": pid})
                return True
        except Exception as e:
            log_action("restart_failed", {"port": port, "error": str(e)})
            return False
    
    return False

def clear_cache():
    """清理缓存"""
    actions = []
    
    # 清理Python缓存
    result = subprocess.run(
        ["find", "/root/.openclaw/workspace/ultron", "-name", "*.pyc", "-delete"],
        capture_output=True
    )
    if result.returncode == 0:
        actions.append("清理.pyc文件")
    
    # 清理__pycache__
    result = subprocess.run(
        ["find", "/root/.openclaw/workspace/ultron", "-name", "__pycache__", "-type", "d", "-exec", "rm", "-rf", "{}", "+"],
        capture_output=True
    )
    if result.returncode == 0:
        actions.append("清理__pycache__目录")
    
    # 清理临时文件
    result = subprocess.run(
        ["find", "/tmp", "-name", "nohup.out", "-mtime", "+1", "-delete"],
        capture_output=True
    )
    
    return actions

def run_diagnostics():
    """运行诊断"""
    config = load_config()
    issues = []
    fixes = []
    
    # 1. 检查服务健康
    health_check = config.get('health_check', {})
    if health_check.get('enabled'):
        ports = health_check.get('ports', [])
        
        for port in ports:
            result = check_service_health(port)
            if result['status'] == 'down':
                issues.append({
                    "type": "service_down",
                    "port": port,
                    "severity": "high",
                    "details": result.get('error', 'Unknown')
                })
                
                if config.get('auto_repair') and config.get('repair_actions', {}).get('restart_service'):
                    # 尝试重启
                    if restart_service_by_port(port):
                        fixes.append(f"重启端口{port}服务成功")
    
    # 2. 检查系统资源
    resources = get_system_resources()
    limits = config.get('resource_limits', {})
    
    if resources['cpu_percent'] > limits.get('cpu_critical', 95):
        issues.append({
            "type": "high_cpu",
            "severity": "critical",
            "value": resources['cpu_percent']
        })
    elif resources['cpu_percent'] > limits.get('cpu_warning', 80):
        issues.append({
            "type": "high_cpu",
            "severity": "medium",
            "value": resources['cpu_percent']
        })
    
    if resources['memory_percent'] > limits.get('memory_critical', 95):
        issues.append({
            "type": "high_memory",
            "severity": "critical",
            "value": resources['memory_percent']
        })
    elif resources['memory_percent'] > limits.get('memory_warning', 80):
        issues.append({
            "type": "high_memory",
            "severity": "medium",
            "value": resources['memory_percent']
        })
    
    # 3. 检查僵尸进程
    zombie_procs = find_unresponsive_processes()
    if zombie_procs:
        issues.append({
            "type": "zombie_processes",
            "severity": "medium",
            "processes": zombie_procs
        })
    
    return {
        "timestamp": datetime.now().isoformat(),
        "resources": resources,
        "issues": issues,
        "fixes": fixes,
        "issues_count": len(issues),
        "fixes_count": len(fixes)
    }

@app.route('/api/diagnostics', methods=['GET'])
def diagnostics():
    """运行诊断"""
    result = run_diagnostics()
    return jsonify({
        "status": "ok",
        "diagnostics": result
    })

@app.route('/api/repair', methods=['POST'])
def repair():
    """执行修复操作"""
    config = load_config()
    action = request.get_json().get('action', 'diagnostics')
    
    results = []
    
    if action == "clear_cache":
        results = clear_cache()
    elif action == "restart_all":
        # 重启所有已知服务
        ports = config.get('health_check', {}).get('ports', [])
        for port in ports:
            if restart_service_by_port(port):
                results.append(f"重启端口{port}成功")
    elif action == "diagnostics":
        diag = run_diagnostics()
        return jsonify({
            "status": "ok",
            "diagnostics": diag
        })
    
    return jsonify({
        "status": "ok",
        "action": action,
        "results": results
    })

@app.route('/api/services', methods=['GET'])
def services():
    """检查所有服务状态"""
    config = load_config()
    ports = config.get('health_check', {}).get('ports', [])
    
    service_status = []
    for port in ports:
        result = check_service_health(port)
        service_status.append(result)
    
    healthy = sum(1 for s in service_status if s['status'] == 'healthy')
    
    return jsonify({
        "status": "ok",
        "services": service_status,
        "summary": {
            "total": len(service_status),
            "healthy": healthy,
            "unhealthy": len(service_status) - healthy
        }
    })

@app.route('/api/resources', methods=['GET'])
def resources():
    """获取系统资源"""
    resources = get_system_resources()
    config = load_config()
    limits = config.get('resource_limits', {})
    
    # 添加状态
    resources['cpu_status'] = 'critical' if resources['cpu_percent'] > limits.get('cpu_critical', 95) else 'warning' if resources['cpu_percent'] > limits.get('cpu_warning', 80) else 'normal'
    resources['memory_status'] = 'critical' if resources['memory_percent'] > limits.get('memory_critical', 95) else 'warning' if resources['memory_percent'] > limits.get('memory_warning', 80) else 'normal'
    resources['disk_status'] = 'critical' if resources['disk_percent'] > limits.get('disk_critical', 95) else 'warning' if resources['disk_percent'] > limits.get('disk_warning', 80) else 'normal'
    
    return jsonify({
        "status": "ok",
        "resources": resources
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    config = load_config()
    return jsonify({
        "status": "ok",
        "config": config
    })

@app.route('/api/config', methods=['PUT', 'POST'])
def update_config():
    """更新配置"""
    config = load_config()
    data = request.get_json()
    
    config.update(data)
    save_config(config)
    
    return jsonify({
        "status": "ok",
        "config": config
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "self-healer",
        "port": 18226
    })

if __name__ == '__main__':
    init_dirs()
    print("启动系统自愈与自动修复服务...")
    print(f"端口: 18226")
    app.run(host='0.0.0.0', port=18227, debug=False)