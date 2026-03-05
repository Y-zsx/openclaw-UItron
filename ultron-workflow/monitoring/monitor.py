#!/usr/bin/env python3
"""
服务状态监控器
收集系统指标和Agent状态
"""
import json
import os
import subprocess
import psutil
import requests
from datetime import datetime
from pathlib import Path

MONITOR_DIR = Path("/root/.openclaw/workspace/ultron-workflow/monitoring")
STATE_FILE = MONITOR_DIR / "metrics.json"


class ServiceMonitor:
    """服务监控器"""
    
    def __init__(self):
        self.last_metrics = {}
    
    def get_system_metrics(self):
        """获取系统指标"""
        metrics = {}
        
        # CPU
        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        metrics["cpu_count"] = psutil.cpu_count()
        
        # 内存
        mem = psutil.virtual_memory()
        metrics["memory_total"] = mem.total
        metrics["memory_used"] = mem.used
        metrics["memory_percent"] = mem.percent
        metrics["memory_available"] = mem.available
        
        # 磁盘
        disk = psutil.disk_usage('/')
        metrics["disk_total"] = disk.total
        metrics["disk_used"] = disk.used
        metrics["disk_percent"] = disk.percent
        metrics["disk_free"] = disk.free
        
        # 网络
        net = psutil.net_io_counters()
        metrics["network_bytes_sent"] = net.bytes_sent
        metrics["network_bytes_recv"] = net.bytes_recv
        
        # 负载
        load = os.getloadavg()
        metrics["load_avg_1m"] = load[0]
        metrics["load_avg_5m"] = load[1]
        metrics["load_avg_15m"] = load[2]
        
        return metrics
    
    def get_openclaw_status(self):
        """获取OpenClaw状态"""
        metrics = {}
        
        try:
            # 检查Gateway端口是否可访问
            import socket
            gateway_running = False
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('127.0.0.1', 18789))
                gateway_running = (result == 0)
                sock.close()
            except Exception as e:
                # 备用检查
                try:
                    r = subprocess.run(['pgrep', '-f', 'openclaw-gateway'], capture_output=True, timeout=2)
                    gateway_running = (r.returncode == 0)
                except:
                    gateway_running = False
            
            metrics["gateway_reachable"] = gateway_running
            metrics["gateway_service_running"] = gateway_running
            
            # 检查Gateway进程 (不抛异常)
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and 'gateway' in ' '.join(cmdline).lower():
                            metrics["gateway_process_pid"] = proc.pid
                            metrics["gateway_process_cpu"] = proc.cpu_percent()
                            metrics["gateway_process_memory"] = proc.memory_percent()
                            break
                    except:
                        pass
            except:
                pass
            
            # 尝试获取会话数
            try:
                sessions_file = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
                if sessions_file.exists():
                    with open(sessions_file) as f:
                        sessions_data = json.load(f)
                        metrics["session_count"] = len(sessions_data.get("sessions", []))
            except:
                pass
        
        except Exception as e:
            metrics["gateway_reachable"] = False
            metrics["error"] = str(e)
        
        # 尝试解析完整的status (不在主try中)
        try:
            result = subprocess.run(
                ["openclaw", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0:
                status = json.loads(result.stdout)
                metrics["gateway_version"] = status.get("app", "unknown")
                metrics["agent_count"] = status.get("Agents", {}).get("count", 1)
                heartbeat = status.get("Heartbeat", {})
                metrics["heartbeat_interval"] = heartbeat.get("interval", "unknown")
        except Exception as e:
            metrics["status_error"] = str(e)
        
        return metrics
    
    def get_agent_metrics(self):
        """获取Agent指标"""
        metrics = {}
        
        agent_dir = Path("/root/.openclaw/workspace/ultron-workflow/agents")
        
        # 检查各个Agent状态文件
        agent_files = {
            "coordinator": "coordinator-state.json",
            "executor": "executor-state.json",
            "analyzer": "analyzer-state.json",
            "monitor": "monitor-state.json"
        }
        
        for agent_name, state_file in agent_files.items():
            state_path = agent_dir / state_file
            if state_path.exists():
                try:
                    with open(state_path) as f:
                        state = json.load(f)
                        metrics[f"agent_{agent_name}_status"] = state.get("status", "unknown")
                        
                        # 检查心跳时间
                        last_heartbeat = state.get("last_heartbeat")
                        if last_heartbeat:
                            last_time = datetime.fromisoformat(last_heartbeat)
                            age = (datetime.now() - last_time).total_seconds()
                            metrics[f"agent_{agent_name}_heartbeat_age"] = age
                except Exception as e:
                    metrics[f"agent_{agent_name}_status"] = "error"
                    metrics[f"agent_{agent_name}_error"] = str(e)
            else:
                metrics[f"agent_{agent_name}_status"] = "not_found"
        
        return metrics
    
    def get_process_metrics(self):
        """获取进程指标"""
        metrics = {}
        
        # Gateway进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'gateway' in ' '.join(cmdline).lower():
                    metrics["gateway_process_pid"] = proc.info['pid']
                    metrics["gateway_process_cpu"] = proc.cpu_percent()
                    metrics["gateway_process_memory"] = proc.memory_percent()
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return metrics
    
    def collect_all(self):
        """收集所有指标"""
        all_metrics = {}
        
        # 系统指标
        all_metrics.update(self.get_system_metrics())
        
        # OpenClaw状态
        all_metrics.update(self.get_openclaw_status())
        
        # Agent状态
        all_metrics.update(self.get_agent_metrics())
        
        # 进程指标
        all_metrics.update(self.get_process_metrics())
        
        # 时间戳
        all_metrics["timestamp"] = datetime.now().isoformat()
        
        # 保存
        self.last_metrics = all_metrics
        with open(STATE_FILE, 'w') as f:
            json.dump(all_metrics, f, indent=2, ensure_ascii=False)
        
        return all_metrics
    
    def get_status_summary(self):
        """获取状态摘要"""
        if not self.last_metrics:
            self.collect_all()
        
        m = self.last_metrics
        
        # 快速健康检查
        issues = []
        
        if not m.get("gateway_reachable", False):
            issues.append("Gateway不可达")
        
        if m.get("memory_percent", 0) > 85:
            issues.append(f"内存使用率高: {m['memory_percent']}%")
        
        if m.get("cpu_percent", 0) > 90:
            issues.append(f"CPU使用率高: {m['cpu_percent']}%")
        
        if m.get("disk_percent", 0) > 90:
            issues.append(f"磁盘使用率高: {m['disk_percent']}%")
        
        # Agent状态检查
        for agent in ["coordinator", "executor", "analyzer", "monitor"]:
            status = m.get(f"agent_{agent}_status")
            if status and status not in ["running", "idle", "completed"]:
                issues.append(f"Agent {agent} 状态异常: {status}")
        
        health = "healthy" if not issues else "degraded"
        
        return {
            "health": health,
            "issues": issues,
            "metrics": m
        }


def get_monitor():
    """获取监控器实例"""
    return ServiceMonitor()


if __name__ == "__main__":
    import sys
    
    monitor = get_monitor()
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "collect"
    
    if cmd == "collect":
        metrics = monitor.collect_all()
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    
    elif cmd == "summary":
        summary = monitor.get_status_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    elif cmd == "system":
        print(json.dumps(monitor.get_system_metrics(), indent=2, ensure_ascii=False))
    
    elif cmd == "openclaw":
        print(json.dumps(monitor.get_openclaw_status(), indent=2, ensure_ascii=False))
    
    elif cmd == "agents":
        print(json.dumps(monitor.get_agent_metrics(), indent=2, ensure_ascii=False))