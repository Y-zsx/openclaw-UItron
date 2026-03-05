#!/usr/bin/env python3
"""
Agent Lifecycle Manager - Agent生命周期管理与自动恢复
实现功能:
1. Agent健康状态监控
2. 自动故障检测与恢复
3. 状态持久化与恢复
4. 心跳机制
5. 资源限制与重启策略
"""

import json
import os
import time
import psutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

AGENTS_DIR = Path("/root/.openclaw/workspace/ultron-workflow/agents")

class AgentStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"
    STOPPED = "stopped"

class AgentLifecycleManager:
    def __init__(self):
        self.config = self._load_config()
        self.agents = {}
        self.health_records = {}
        
    def _load_config(self) -> Dict:
        """加载配置"""
        config_path = AGENTS_DIR / "lifecycle-config.json"
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        return {
            "health_check_interval": 60,  # 秒
            "max_restart_attempts": 3,
            "restart_cooldown": 30,  # 秒
            "failure_threshold": 3,  # 连续失败次数
            "healthy_threshold": 5,  # 连续健康次数
            "memory_warning_threshold": 80,  # %
            "memory_critical_threshold": 95,  # %
        }
    
    def _get_agent_states(self) -> Dict[str, Dict]:
        """扫描所有Agent状态文件"""
        states = {}
        for f in AGENTS_DIR.glob("*-state.json"):
            agent_name = f.stem.replace("-state", "")
            try:
                with open(f) as sf:
                    states[agent_name] = json.load(sf)
            except:
                pass
        return states
    
    def check_agent_health(self, agent_name: str) -> Dict[str, Any]:
        """检查单个Agent健康状态"""
        state_file = AGENTS_DIR / f"{agent_name}-state.json"
        log_file = AGENTS_DIR / f"{agent_name}.log"
        
        result = {
            "agent": agent_name,
            "status": AgentStatus.STOPPED,
            "last_update": None,
            "error_count": 0,
            "memory_percent": 0,
            "cpu_percent": 0,
            "uptime_seconds": 0,
            "issues": []
        }
        
        # 读取状态文件
        if state_file.exists():
            try:
                with open(state_file) as f:
                    state = json.load(f)
                    result["status"] = state.get("status", "unknown")
                    result["last_update"] = state.get("last_update")
                    
                    # 检查错误计数
                    result["error_count"] = state.get("error_count", 0)
                    
                    # 计算运行时间
                    if "last_update" in state:
                        try:
                            last = datetime.fromisoformat(state["last_update"].replace('Z', '+00:00'))
                            result["uptime_seconds"] = (datetime.now() - last.replace(tzinfo=None)).total_seconds()
                        except:
                            pass
            except Exception as e:
                result["issues"].append(f"State read error: {e}")
        
        # 检查日志文件是否有错误
        if log_file.exists():
            try:
                with open(log_file) as f:
                    lines = f.readlines()
                    recent_errors = [l for l in lines[-50:] if "ERROR" in l or "Exception" in l]
                    if len(recent_errors) > 5:
                        result["issues"].append(f"Found {len(recent_errors)} errors in recent logs")
                    if recent_errors:
                        result["last_error"] = recent_errors[-1].strip()[:100]
            except:
                pass
        
        # 检查Agent进程
        agent_script = AGENTS_DIR / f"{agent_name}-agent.py"
        if agent_script.exists():
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and any(agent_name in str(c) for c in cmdline):
                            result["memory_percent"] = proc.info.get('memory_percent', 0)
                            result["cpu_percent"] = proc.info.get('cpu_percent', 0)
                            result["pid"] = proc.info.get('pid')
                            if result["status"] == "stopped":
                                result["status"] = AgentStatus.HEALTHY
                            break
                    except:
                        pass
            except:
                pass
        
        # 判断健康状态
        if result["memory_percent"] > self.config["memory_critical_threshold"]:
            result["status"] = AgentStatus.FAILED
            result["issues"].append("Critical memory usage")
        elif result["memory_percent"] > self.config["memory_warning_threshold"]:
            result["status"] = AgentStatus.DEGRADED
            result["issues"].append("High memory usage")
        elif result["error_count"] >= self.config["failure_threshold"]:
            result["status"] = AgentStatus.FAILED
            result["issues"].append("Too many errors")
        elif result["issues"]:
            result["status"] = AgentStatus.DEGRADED
        
        return result
    
    def get_all_agents_health(self) -> Dict[str, Dict]:
        """获取所有Agent健康状态"""
        states = self._get_agent_states()
        health = {}
        for agent_name in states.keys():
            health[agent_name] = self.check_agent_health(agent_name)
        return health
    
    def auto_recover_agent(self, agent_name: str) -> Dict[str, Any]:
        """自动恢复Agent"""
        result = {
            "agent": agent_name,
            "action": None,
            "success": False,
            "message": ""
        }
        
        state_file = AGENTS_DIR / f"{agent_name}-state.json"
        agent_script = AGENTS_DIR / f"{agent_name}-agent.py"
        
        # 检查重试次数
        restart_count_file = AGENTS_DIR / f"{agent_name}-restart.count"
        restart_count = 0
        if restart_count_file.exists():
            try:
                restart_count = int(restart_count_file.read().strip())
            except:
                pass
        
        if restart_count >= self.config["max_restart_attempts"]:
            result["message"] = f"Max restart attempts ({self.config['max_restart_attempts']}) reached"
            return result
        
        # 尝试恢复
        if agent_script.exists():
            try:
                # 更新状态为恢复中
                if state_file.exists():
                    with open(state_file) as f:
                        state = json.load(f)
                    state["status"] = "recovering"
                    state["last_recovery_attempt"] = datetime.now().isoformat()
                    with open(state_file, 'w') as f:
                        json.dump(state, f, indent=2)
                
                # 启动Agent
                cmd = ["python3", str(agent_script)]
                # 检查是否已有进程在运行
                proc_running = False
                for proc in psutil.process_iter(['cmdline']):
                    try:
                        if proc.info.get('cmdline') and any(agent_name in str(c) for c in proc.info['cmdline']):
                            proc_running = True
                            break
                    except:
                        pass
                
                if not proc_running:
                    subprocess.Popen(cmd, stdout=open(AGENTS_DIR / f"{agent_name}.log", "a"),
                                   stderr=subprocess.STDOUT, start_new_session=True)
                    result["action"] = "started"
                    result["success"] = True
                    result["message"] = f"Agent {agent_name} started successfully"
                    
                    # 增加重启计数
                    restart_count += 1
                    restart_count_file.write_text(str(restart_count))
                else:
                    result["action"] = "already_running"
                    result["success"] = True
                    result["message"] = f"Agent {agent_name} is already running"
                    
            except Exception as e:
                result["message"] = f"Recovery failed: {e}"
        else:
            result["message"] = f"Agent script not found: {agent_name}"
        
        return result
    
    def perform_auto_recovery(self) -> Dict[str, Any]:
        """执行自动恢复检查"""
        health = self.get_all_agents_health()
        recovery_results = {
            "checked": len(health),
            "recovered": [],
            "failed": [],
            "healthy": [],
            "timestamp": datetime.now().isoformat()
        }
        
        for agent_name, agent_health in health.items():
            status = agent_health.get("status", AgentStatus.STOPPED)
            
            if status in [AgentStatus.FAILED, AgentStatus.DEGRADED]:
                recovery = self.auto_recover_agent(agent_name)
                if recovery["success"]:
                    recovery_results["recovered"].append(recovery)
                else:
                    recovery_results["failed"].append(recovery)
            elif status == AgentStatus.HEALTHY:
                recovery_results["healthy"].append(agent_name)
                
                # 重置重启计数
                restart_count_file = AGENTS_DIR / f"{agent_name}-restart.count"
                if restart_count_file.exists():
                    restart_count_file.unlink()
        
        return recovery_results
    
    def generate_report(self) -> str:
        """生成健康报告"""
        health = self.get_all_agents_health()
        
        report = ["# Agent Lifecycle Report", f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
        report.append("## Agent Status")
        
        for agent_name, h in health.items():
            status = h.get("status", AgentStatus.STOPPED)
            if isinstance(status, str):
                status_str = status
            else:
                status_str = status.value if hasattr(status, 'value') else str(status)
            
            status_emoji = {
                AgentStatus.HEALTHY: "✅",
                AgentStatus.DEGRADED: "⚠️",
                AgentStatus.FAILED: "❌",
                AgentStatus.RECOVERING: "🔄",
                AgentStatus.STOPPED: "⏹️"
            }.get(status if isinstance(status, AgentStatus) else AgentStatus.STOPPED, "❓")
            
            report.append(f"- **{agent_name}**: {status_emoji} {status_str}")
            if h.get("memory_percent"):
                report.append(f"  - Memory: {h['memory_percent']:.1f}%")
            if h.get("issues"):
                for issue in h["issues"]:
                    report.append(f"  - Issue: {issue}")
        
        return "\n".join(report)


if __name__ == "__main__":
    import sys
    
    manager = AgentLifecycleManager()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "health":
            health = manager.get_all_agents_health()
            print(json.dumps(health, indent=2, default=str))
        elif sys.argv[1] == "recover":
            result = manager.perform_auto_recovery()
            print(json.dumps(result, indent=2, default=str))
        elif sys.argv[1] == "report":
            print(manager.generate_report())
        elif sys.argv[1] == "check" and len(sys.argv) > 2:
            result = manager.check_agent_health(sys.argv[2])
            print(json.dumps(result, indent=2, default=str))
    else:
        # 默认执行健康检查和自动恢复
        result = manager.perform_auto_recovery()
        print(json.dumps(result, indent=2, default=str))