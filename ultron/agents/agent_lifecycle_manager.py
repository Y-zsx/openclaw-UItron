#!/usr/bin/env python3
"""
Agent生命周期管理器 - 第35世
负责Agent的注册、启动、停止、监控与健康检查

功能:
- Agent注册与发现
- 生命周期状态管理
- 健康检查与自动恢复
- 资源监控
"""

import json
import time
import asyncio
import subprocess
import psutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from threading import Thread, Event
import os
import sys

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENTS_DIR)

class AgentState(Enum):
    """Agent生命周期状态"""
    REGISTERED = "registered"       # 已注册，未启动
    STARTING = "starting"           # 启动中
    RUNNING = "running"             # 运行中
    STOPPING = "stopping"           # 停止中
    STOPPED = "stopped"             # 已停止
    FAILED = "failed"               # 失败
    RECOVERING = "recovering"       # 恢复中

class AgentType(Enum):
    """Agent类型"""
    PYTHON = "python"
    SHELL = "shell"
    COMPOSITE = "composite"

@dataclass
class AgentMetadata:
    """Agent元数据"""
    name: str
    agent_type: AgentType
    script_path: str = ""
    command: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    auto_restart: bool = True
    max_restarts: int = 3
    health_check_interval: int = 30  # 秒
    startup_timeout: int = 10        # 秒

@dataclass
class AgentStatus:
    """Agent运行时状态"""
    state: AgentState = AgentState.REGISTERED
    pid: Optional[int] = None
    start_time: Optional[str] = None
    last_heartbeat: Optional[str] = None
    restart_count: int = 0
    last_error: Optional[str] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    health_score: float = 100.0
    
    def to_dict(self) -> Dict:
        return {
            "state": self.state.value,
            "pid": self.pid,
            "start_time": self.start_time,
            "last_heartbeat": self.last_heartbeat,
            "restart_count": self.restart_count,
            "last_error": self.last_error,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "health_score": self.health_score
        }

class AgentLifecycleManager:
    """Agent生命周期管理器"""
    
    def __init__(self, state_file: str = None):
        self.agents: Dict[str, AgentMetadata] = {}
        self.statuses: Dict[str, AgentStatus] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.health_check_callbacks: Dict[str, Callable] = {}
        
        # 状态持久化
        self.state_file = state_file or os.path.join(AGENTS_DIR, "agent_lifecycle_state.json")
        self._health_check_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._running = False
        
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    for name, meta in data.get('agents', {}).items():
                        self.agents[name] = AgentMetadata(
                            name=meta['name'],
                            agent_type=AgentType(meta['agent_type']),
                            script_path=meta.get('script_path', ''),
                            command=meta.get('command', ''),
                            env=meta.get('env', {}),
                            cwd=meta.get('cwd', ''),
                            auto_restart=meta.get('auto_restart', True),
                            max_restarts=meta.get('max_restarts', 3),
                            health_check_interval=meta.get('health_check_interval', 30),
                            startup_timeout=meta.get('startup_timeout', 10)
                        )
                    for name, stat in data.get('statuses', {}).items():
                        self.statuses[name] = AgentStatus(
                            state=AgentState(stat['state']),
                            pid=stat.get('pid'),
                            start_time=stat.get('start_time'),
                            last_heartbeat=stat.get('last_heartbeat'),
                            restart_count=stat.get('restart_count', 0),
                            last_error=stat.get('last_error'),
                            cpu_percent=stat.get('cpu_percent', 0.0),
                            memory_mb=stat.get('memory_mb', 0.0),
                            health_score=stat.get('health_score', 100.0)
                        )
            except Exception as e:
                print(f"加载状态失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        data = {
            'agents': {
                name: {
                    'name': m.name,
                    'agent_type': m.agent_type.value,
                    'script_path': m.script_path,
                    'command': m.command,
                    'env': m.env,
                    'cwd': m.cwd,
                    'auto_restart': m.auto_restart,
                    'max_restarts': m.max_restarts,
                    'health_check_interval': m.health_check_interval,
                    'startup_timeout': m.startup_timeout
                }
                for name, m in self.agents.items()
            },
            'statuses': {
                name: s.to_dict()
                for name, s in self.statuses.items()
            }
        }
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register_agent(self, metadata: AgentMetadata) -> bool:
        """注册Agent"""
        if metadata.name in self.agents:
            return False
        
        self.agents[metadata.name] = metadata
        self.statuses[metadata.name] = AgentStatus(state=AgentState.REGISTERED)
        self._save_state()
        print(f"✅ Agent注册: {metadata.name}")
        return True
    
    def unregister_agent(self, name: str) -> bool:
        """注销Agent"""
        if name not in self.agents:
            return False
        
        # 如果在运行，先停止
        if self.statuses[name].state == AgentState.RUNNING:
            self.stop_agent(name)
        
        del self.agents[name]
        del self.statuses[name]
        if name in self.processes:
            del self.processes[name]
        self._save_state()
        print(f"✅ Agent注销: {name}")
        return True
    
    def start_agent(self, name: str) -> bool:
        """启动Agent"""
        if name not in self.agents:
            print(f"❌ Agent不存在: {name}")
            return False
        
        meta = self.agents[name]
        status = self.statuses[name]
        
        if status.state == AgentState.RUNNING:
            print(f"⚠️ Agent已在运行: {name}")
            return True
        
        status.state = AgentState.STARTING
        self._save_state()
        
        try:
            if meta.agent_type == AgentType.PYTHON:
                cmd = [sys.executable, meta.script_path] if meta.script_path else meta.command.split()
            elif meta.agent_type == AgentType.SHELL:
                cmd = ['sh', '-c', meta.command] if meta.command else [meta.script_path]
            else:
                cmd = meta.command.split()
            
            process = subprocess.Popen(
                cmd,
                env={**os.environ, **meta.env} if meta.env else None,
                cwd=meta.cwd or None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # 等待启动超时
            time.sleep(0.5)
            
            if process.poll() is not None:
                status.state = AgentState.FAILED
                status.last_error = "启动后立即退出"
                print(f"❌ Agent启动失败: {name}")
                self._save_state()
                return False
            
            status.state = AgentState.RUNNING
            status.pid = process.pid
            status.start_time = datetime.now().isoformat()
            status.last_heartbeat = status.start_time
            status.last_error = None
            
            self.processes[name] = process
            self._save_state()
            print(f"✅ Agent已启动: {name} (PID: {process.pid})")
            return True
            
        except Exception as e:
            status.state = AgentState.FAILED
            status.last_error = str(e)
            self._save_state()
            print(f"❌ Agent启动异常: {name} - {e}")
            return False
    
    def stop_agent(self, name: str, timeout: int = 10) -> bool:
        """停止Agent"""
        if name not in self.agents:
            return False
        
        status = self.statuses[name]
        
        if status.state != AgentState.RUNNING:
            return True
        
        status.state = AgentState.STOPPING
        self._save_state()
        
        process = self.processes.get(name)
        
        try:
            if process:
                # 发送SIGTERM
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # 强制杀死
                    process.kill()
                    process.wait()
                
                status.state = AgentState.STOPPED
                status.pid = None
                
                if name in self.processes:
                    del self.processes[name]
                
                self._save_state()
                print(f"✅ Agent已停止: {name}")
                return True
            else:
                status.state = AgentState.STOPPED
                self._save_state()
                return True
                
        except Exception as e:
            status.state = AgentState.FAILED
            status.last_error = f"停止失败: {e}"
            self._save_state()
            print(f"❌ Agent停止失败: {name} - {e}")
            return False
    
    def restart_agent(self, name: str) -> bool:
        """重启Agent"""
        if name not in self.agents:
            return False
        
        print(f"🔄 重启Agent: {name}")
        self.stop_agent(name)
        time.sleep(1)
        return self.start_agent(name)
    
    def get_agent_status(self, name: str) -> Optional[AgentStatus]:
        """获取Agent状态"""
        if name not in self.statuses:
            return None
        
        status = self.statuses[name]
        
        # 更新资源使用
        if status.pid and status.state == AgentState.RUNNING:
            try:
                proc = psutil.Process(status.pid)
                status.cpu_percent = proc.cpu_percent(interval=0.1)
                status.memory_mb = proc.memory_info().rss / 1024 / 1024
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                status.state = AgentState.FAILED
                status.last_error = "进程不存在"
        
        return status
    
    def get_all_status(self) -> Dict[str, Dict]:
        """获取所有Agent状态"""
        result = {}
        for name in self.agents:
            status = self.get_agent_status(name)
            if status:
                result[name] = status.to_dict()
        return result
    
    def register_health_check(self, name: str, callback: Callable):
        """注册健康检查回调"""
        self.health_check_callbacks[name] = callback
    
    def check_agent_health(self, name: str) -> float:
        """检查Agent健康度 (0-100)"""
        if name not in self.statuses:
            return 0.0
        
        status = self.statuses[name]
        
        # 基础状态检查
        if status.state != AgentState.RUNNING:
            return 0.0
        
        # 进程存在检查
        if status.pid:
            try:
                proc = psutil.Process(status.pid)
                if not proc.is_running():
                    return 0.0
            except psutil.NoSuchProcess:
                return 0.0
        
        # 自定义健康检查
        if name in self.health_check_callbacks:
            try:
                cb_result = self.health_check_callbacks[name]()
                if cb_result is False:
                    return 0.0
            except Exception:
                pass
        
        # 资源使用评估
        score = 100.0
        
        # CPU过高扣分
        if status.cpu_percent > 90:
            score -= 30
        elif status.cpu_percent > 70:
            score -= 15
        
        # 内存过高扣分
        if status.memory_mb > 2048:
            score -= 20
        elif status.memory_mb > 1024:
            score -= 10
        
        # 频繁重启扣分
        if status.restart_count > 5:
            score -= 20
        elif status.restart_count > 2:
            score -= 10
        
        return max(0.0, score)
    
    def _health_check_loop(self):
        """健康检查循环"""
        while not self._stop_event.is_set():
            for name in list(self.agents.keys()):
                status = self.statuses.get(name)
                if not status or status.state != AgentState.RUNNING:
                    continue
                
                # 健康检查
                health = self.check_agent_health(name)
                status.health_score = health
                
                # 更新心跳
                status.last_heartbeat = datetime.now().isoformat()
                
                # 低健康度自动恢复
                if health < 50 and self.agents[name].auto_restart:
                    if status.restart_count < self.agents[name].max_restarts:
                        print(f"⚠️ Agent健康度低({health:.0f}%)，尝试恢复: {name}")
                        status.state = AgentState.RECOVERING
                        self.restart_agent(name)
                        status.restart_count += 1
                
                # 进程意外退出
                if status.pid:
                    try:
                        proc = psutil.Process(status.pid)
                        if not proc.is_running():
                            status.state = AgentState.FAILED
                            status.last_error = "进程意外退出"
                            if self.agents[name].auto_restart:
                                if status.restart_count < self.agents[name].max_restarts:
                                    self.restart_agent(name)
                                    status.restart_count += 1
                    except psutil.NoSuchProcess:
                        status.state = AgentState.FAILED
                        if self.agents[name].auto_restart:
                            if status.restart_count < self.agents[name].max_restarts:
                                self.restart_agent(name)
                                status.restart_count += 1
            
            self._save_state()
            time.sleep(10)
    
    def start_monitoring(self):
        """启动监控循环"""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._health_check_thread = Thread(target=self._health_check_loop, daemon=True)
        self._health_check_thread.start()
        print("✅ Agent生命周期监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        self._stop_event.set()
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)
        print("⏹️ Agent生命周期监控已停止")
    
    def get_summary(self) -> Dict:
        """获取汇总信息"""
        total = len(self.agents)
        running = sum(1 for s in self.statuses.values() if s.state == AgentState.RUNNING)
        failed = sum(1 for s in self.statuses.values() if s.state == AgentState.FAILED)
        
        return {
            "total": total,
            "running": running,
            "stopped": total - running,
            "failed": failed,
            "agents": list(self.agents.keys())
        }


# 演示和测试
if __name__ == "__main__":
    manager = AgentLifecycleManager()
    
    # 注册示例Agent
    manager.register_agent(AgentMetadata(
        name="monitor-agent",
        agent_type=AgentType.PYTHON,
        script_path=os.path.join(AGENTS_DIR, "monitor_agent.py"),
        auto_restart=True,
        max_restarts=3
    ))
    
    manager.register_agent(AgentMetadata(
        name="executor-agent",
        agent_type=AgentType.PYTHON,
        script_path=os.path.join(AGENTS_DIR, "executor_agent.py"),
        auto_restart=True,
        max_restarts=3
    ))
    
    # 启动所有Agent
    print("\n=== 启动所有Agent ===")
    for name in manager.agents:
        manager.start_agent(name)
    
    # 获取状态
    print("\n=== Agent状态 ===")
    for name, status in manager.get_all_status().items():
        print(f"{name}: {status['state']} (PID: {status['pid']})")
    
    # 启动监控
    manager.start_monitoring()
    
    # 运行一段时间
    print("\n=== 监控中 (10秒) ===")
    time.sleep(10)
    
    # 停止监控
    manager.stop_monitoring()
    
    # 最终状态
    print("\n=== 最终状态 ===")
    print(manager.get_summary())