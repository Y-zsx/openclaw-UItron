#!/usr/bin/env python3
"""
Agent生命周期管理器 - 第20世（完善版）
负责Agent的注册、启动、停止、监控与健康检查

增强功能:
- Agent依赖管理与启动顺序
- 资源限制与配额
- 生命周期钩子
- 事件通知系统
- 批量操作
- 详细审计日志

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
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from threading import Thread, Event, Lock
import os
import sys
from collections import defaultdict
from copy import deepcopy

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
    PAUSED = "paused"               # 暂停（可恢复）

class AgentType(Enum):
    """Agent类型"""
    PYTHON = "python"
    SHELL = "shell"
    DOCKER = "docker"
    COMPOSITE = "composite"

class LifecycleEvent(Enum):
    """生命周期事件"""
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    STARTED = "started"
    STOPPED = "stopped"
    RESTARTED = "restarted"
    FAILED = "failed"
    RECOVERED = "recovered"
    PAUSED = "paused"
    RESUMED = "resumed"
    HEALTH_CHECK_PASSED = "health_check_passed"
    HEALTH_CHECK_FAILED = "health_check_failed"

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
    
    # 新增：依赖管理
    depends_on: List[str] = field(default_factory=list)  # 依赖的Agent列表
    startup_order: int = 0  # 启动顺序，数字越小越先启动
    
    # 新增：资源限制
    max_cpu_percent: float = 0.0  # 0表示无限制
    max_memory_mb: float = 0.0    # 0表示无限制
    priority: int = 50  # 优先级 0-100
    
    # 新增：生命周期钩子
    pre_start_hook: str = ""   # 启动前执行的脚本
    post_start_hook: str = ""  # 启动后执行的脚本
    pre_stop_hook: str = ""    # 停止前执行的脚本
    post_stop_hook: str = ""   # 停止后执行的脚本

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
    uptime_seconds: float = 0.0
    
    # 新增：资源使用统计
    total_cpu_time: float = 0.0
    peak_memory_mb: float = 0.0
    
    # 新增：事件历史
    event_history: List[Dict] = field(default_factory=list)
    
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
            "health_score": self.health_score,
            "uptime_seconds": self.uptime_seconds,
            "total_cpu_time": self.total_cpu_time,
            "peak_memory_mb": self.peak_memory_mb,
            "event_history": self.event_history[-10:]  # 只保留最近10条
        }

class LifecycleEventEmitter:
    """生命周期事件发射器"""
    
    def __init__(self):
        self._listeners: Dict[LifecycleEvent, List[Callable]] = defaultdict(list)
        self._lock = Lock()
    
    def on(self, event: LifecycleEvent, callback: Callable):
        """订阅事件"""
        with self._lock:
            self._listeners[event].append(callback)
    
    def off(self, event: LifecycleEvent, callback: Callable):
        """取消订阅"""
        with self._lock:
            if callback in self._listeners[event]:
                self._listeners[event].remove(callback)
    
    def emit(self, event: LifecycleEvent, agent_name: str, data: Dict = None):
        """发射事件"""
        event_data = {
            "event": event.value,
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat(),
            "data": data or {}
        }
        
        with self._lock:
            listeners = self._listeners.get(event, []) + self._listeners.get(LifecycleEvent.REGISTERED, [])  # 监听所有事件
            for callback in listeners:
                try:
                    callback(event_data)
                except Exception as e:
                    print(f"事件处理错误: {e}")

class AgentLifecycleManager:
    """Agent生命周期管理器"""
    
    def __init__(self, state_file: str = None):
        self.agents: Dict[str, AgentMetadata] = {}
        self.statuses: Dict[str, AgentStatus] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.health_check_callbacks: Dict[str, Callable] = {}
        self.event_emitter = LifecycleEventEmitter()
        
        # 状态持久化
        self.state_file = state_file or os.path.join(AGENTS_DIR, "agent_lifecycle_state.json")
        self._health_check_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._running = False
        self._lock = Lock()
        
        # 新增：审计日志
        self.audit_log: List[Dict] = []
        
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
                            startup_timeout=meta.get('startup_timeout', 10),
                            depends_on=meta.get('depends_on', []),
                            startup_order=meta.get('startup_order', 0),
                            max_cpu_percent=meta.get('max_cpu_percent', 0.0),
                            max_memory_mb=meta.get('max_memory_mb', 0.0),
                            priority=meta.get('priority', 50),
                            pre_start_hook=meta.get('pre_start_hook', ''),
                            post_start_hook=meta.get('post_start_hook', ''),
                            pre_stop_hook=meta.get('pre_stop_hook', ''),
                            post_stop_hook=meta.get('post_stop_hook', '')
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
                            health_score=stat.get('health_score', 100.0),
                            uptime_seconds=stat.get('uptime_seconds', 0.0),
                            total_cpu_time=stat.get('total_cpu_time', 0.0),
                            peak_memory_mb=stat.get('peak_memory_mb', 0.0),
                            event_history=stat.get('event_history', [])
                        )
            except Exception as e:
                print(f"加载状态失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        with self._lock:
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
                        'startup_timeout': m.startup_timeout,
                        'depends_on': m.depends_on,
                        'startup_order': m.startup_order,
                        'max_cpu_percent': m.max_cpu_percent,
                        'max_memory_mb': m.max_memory_mb,
                        'priority': m.priority,
                        'pre_start_hook': m.pre_start_hook,
                        'post_start_hook': m.post_start_hook,
                        'pre_stop_hook': m.pre_stop_hook,
                        'post_stop_hook': m.post_stop_hook
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
    
    def _log_audit(self, action: str, agent_name: str, details: Dict = None):
        """记录审计日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "agent_name": agent_name,
            "details": details or {}
        }
        self.audit_log.append(entry)
        # 只保留最近1000条
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
    
    def _run_hook(self, hook_script: str, agent_name: str) -> bool:
        """执行钩子脚本"""
        if not hook_script:
            return True
        
        try:
            result = subprocess.run(
                ['sh', '-c', hook_script],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"⚠️ 钩子执行失败 [{agent_name}]: {result.stderr}")
                return False
            return True
        except Exception as e:
            print(f"⚠️ 钩子执行异常 [{agent_name}]: {e}")
            return False
    
    def _check_dependencies(self, name: str, running_only: bool = True) -> tuple[bool, List[str]]:
        """检查依赖是否满足"""
        if name not in self.agents:
            return False, [f"Agent不存在: {name}"]
        
        meta = self.agents[name]
        missing = []
        
        for dep in meta.depends_on:
            if dep not in self.agents:
                missing.append(f"依赖不存在: {dep}")
            elif running_only and self.statuses.get(dep, AgentStatus()).state != AgentState.RUNNING:
                missing.append(f"依赖未运行: {dep}")
        
        return len(missing) == 0, missing
    
    def _resolve_startup_order(self) -> List[str]:
        """解析启动顺序（拓扑排序）"""
        # 按startup_order排序，相同order按字母序
        sorted_agents = sorted(
            self.agents.keys(),
            key=lambda x: (self.agents[x].startup_order, x)
        )
        return sorted_agents
    
    def register_agent(self, metadata: AgentMetadata) -> bool:
        """注册Agent"""
        if metadata.name in self.agents:
            return False
        
        self.agents[metadata.name] = metadata
        self.statuses[metadata.name] = AgentStatus(state=AgentState.REGISTERED)
        
        self._save_state()
        self._log_audit("register", metadata.name, {"type": metadata.agent_type.value})
        self.event_emitter.emit(LifecycleEvent.REGISTERED, metadata.name)
        
        print(f"✅ Agent注册: {metadata.name} (依赖: {metadata.depends_on}, 顺序: {metadata.startup_order})")
        return True
    
    def unregister_agent(self, name: str) -> bool:
        """注销Agent"""
        if name not in self.agents:
            return False
        
        # 如果在运行，先停止
        if self.statuses[name].state == AgentState.RUNNING:
            self.stop_agent(name)
        
        # 检查是否有其他Agent依赖此Agent
        dependent = [a for a, m in self.agents.items() if name in m.depends_on]
        if dependent:
            print(f"⚠️ 仍有Agent依赖 {name}: {dependent}")
        
        del self.agents[name]
        del self.statuses[name]
        if name in self.processes:
            del self.processes[name]
        
        self._save_state()
        self._log_audit("unregister", name)
        self.event_emitter.emit(LifecycleEvent.UNREGISTERED, name)
        
        print(f"✅ Agent注销: {name}")
        return True
    
    def start_agent(self, name: str) -> bool:
        """启动Agent（带依赖检查）"""
        if name not in self.agents:
            print(f"❌ Agent不存在: {name}")
            return False
        
        meta = self.agents[name]
        status = self.statuses[name]
        
        if status.state == AgentState.RUNNING:
            print(f"⚠️ Agent已在运行: {name}")
            return True
        
        # 检查依赖
        can_start, missing = self._check_dependencies(name, running_only=True)
        if not can_start:
            print(f"❌ 无法启动 {name}: {', '.join(missing)}")
            return False
        
        status.state = AgentState.STARTING
        self._save_state()
        
        # 执行启动前钩子
        if not self._run_hook(meta.pre_start_hook, name):
            status.state = AgentState.FAILED
            status.last_error = "启动前钩子失败"
            self._save_state()
            return False
        
        try:
            if meta.agent_type == AgentType.PYTHON:
                cmd = [sys.executable, meta.script_path] if meta.script_path else meta.command.split()
            elif meta.agent_type == AgentType.SHELL:
                cmd = ['sh', '-c', meta.command] if meta.command else [meta.script_path]
            elif meta.agent_type == AgentType.DOCKER:
                cmd = meta.command.split() if meta.command else ['docker', 'start', meta.script_path]
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
                self._log_audit("start_failed", name, {"error": status.last_error})
                self.event_emitter.emit(LifecycleEvent.FAILED, name, {"error": status.last_error})
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
            
            # 执行启动后钩子
            self._run_hook(meta.post_start_hook, name)
            
            self._log_audit("start", name, {"pid": process.pid})
            self.event_emitter.emit(LifecycleEvent.STARTED, name, {"pid": process.pid})
            
            print(f"✅ Agent已启动: {name} (PID: {process.pid})")
            return True
            
        except Exception as e:
            status.state = AgentState.FAILED
            status.last_error = str(e)
            self._save_state()
            self._log_audit("start_failed", name, {"error": str(e)})
            self.event_emitter.emit(LifecycleEvent.FAILED, name, {"error": str(e)})
            print(f"❌ Agent启动异常: {name} - {e}")
            return False
    
    def start_all_agents(self, ordered: bool = True) -> Dict[str, bool]:
        """按依赖顺序启动所有Agent"""
        results = {}
        
        if ordered:
            # 拓扑排序启动
            started = set()
            max_iterations = len(self.agents) * 2  # 防止循环依赖
            
            for _ in range(max_iterations):
                progress = False
                for name in self._resolve_startup_order():
                    if name in started:
                        continue
                    
                    can_start, _ = self._check_dependencies(name, running_only=True)
                    if can_start:
                        results[name] = self.start_agent(name)
                        started.add(name)
                        progress = True
                
                if not progress:
                    break
            
            # 尝试启动剩余的（忽略依赖）
            for name in self.agents:
                if name not in started:
                    results[name] = self.start_agent(name)
        else:
            # 并行启动
            for name in self.agents:
                results[name] = self.start_agent(name)
        
        return results
    
    def stop_agent(self, name: str, timeout: int = 10, force: bool = False) -> bool:
        """停止Agent"""
        if name not in self.agents:
            return False
        
        meta = self.agents[name]
        status = self.statuses[name]
        
        if status.state != AgentState.RUNNING and status.state != AgentState.PAUSED:
            return True
        
        # 检查是否有依赖此Agent的正在运行
        if not force:
            dependent = [a for a, m in self.agents.items() 
                        if name in m.depends_on and 
                        self.statuses.get(a, AgentStatus()).state == AgentState.RUNNING]
            if dependent:
                print(f"⚠️ 仍有依赖Agent运行: {dependent}")
                return False
        
        status.state = AgentState.STOPPING
        self._save_state()
        
        # 执行停止前钩子
        self._run_hook(meta.pre_stop_hook, name)
        
        process = self.processes.get(name)
        
        try:
            if process:
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                
                if name in self.processes:
                    del self.processes[name]
            
            status.state = AgentState.STOPPED
            status.pid = None
            
            # 执行停止后钩子
            self._run_hook(meta.post_stop_hook, name)
            
            self._save_state()
            self._log_audit("stop", name)
            self.event_emitter.emit(LifecycleEvent.STOPPED, name)
            
            print(f"✅ Agent已停止: {name}")
            return True
                
        except Exception as e:
            status.state = AgentState.FAILED
            status.last_error = f"停止失败: {e}"
            self._save_state()
            self._log_audit("stop_failed", name, {"error": str(e)})
            print(f"❌ Agent停止失败: {name} - {e}")
            return False
    
    def stop_all_agents(self, reverse_order: bool = True) -> Dict[str, bool]:
        """按反向依赖顺序停止所有Agent"""
        results = {}
        
        if reverse_order:
            # 反向停止（先停止依赖者）
            for name in reversed(self._resolve_startup_order()):
                results[name] = self.stop_agent(name)
        else:
            for name in self.agents:
                results[name] = self.stop_agent(name)
        
        return results
    
    def restart_agent(self, name: str) -> bool:
        """重启Agent"""
        if name not in self.agents:
            return False
        
        print(f"🔄 重启Agent: {name}")
        self.stop_agent(name)
        time.sleep(1)
        result = self.start_agent(name)
        
        if result:
            self._log_audit("restart", name)
            self.event_emitter.emit(LifecycleEvent.RESTARTED, name)
        
        return result
    
    def pause_agent(self, name: str) -> bool:
        """暂停Agent（发送SIGSTOP）"""
        if name not in self.agents:
            return False
        
        status = self.statuses[name]
        if status.state != AgentState.RUNNING:
            return False
        
        process = self.processes.get(name)
        if process:
            try:
                process.send_signal(19)  # SIGSTOP
                status.state = AgentState.PAUSED
                self._save_state()
                self._log_audit("pause", name)
                self.event_emitter.emit(LifecycleEvent.PAUSED, name)
                print(f"⏸ Agent已暂停: {name}")
                return True
            except Exception as e:
                print(f"❌ 暂停失败: {e}")
        
        return False
    
    def resume_agent(self, name: str) -> bool:
        """恢复Agent（发送SIGCONT）"""
        if name not in self.agents:
            return False
        
        status = self.statuses[name]
        if status.state != AgentState.PAUSED:
            return False
        
        process = self.processes.get(name)
        if process:
            try:
                process.send_signal(18)  # SIGCONT
                status.state = AgentState.RUNNING
                self._save_state()
                self._log_audit("resume", name)
                self.event_emitter.emit(LifecycleEvent.RESUMED, name)
                print(f"▶ Agent已恢复: {name}")
                return True
            except Exception as e:
                print(f"❌ 恢复失败: {e}")
        
        return False
    
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
                
                # 更新峰值内存
                if status.memory_mb > status.peak_memory_mb:
                    status.peak_memory_mb = status.memory_mb
                
                # 计算运行时间
                if status.start_time:
                    start = datetime.fromisoformat(status.start_time)
                    status.uptime_seconds = (datetime.now() - start).total_seconds()
                
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
    
    def get_resource_usage(self) -> Dict:
        """获取资源使用汇总"""
        total_cpu = 0.0
        total_memory = 0.0
        agent_usage = {}
        
        for name, status in self.statuses.items():
            if status.state == AgentState.RUNNING:
                cpu = status.cpu_percent
                mem = status.memory_mb
                total_cpu += cpu
                total_memory += mem
                agent_usage[name] = {"cpu": cpu, "memory": mem}
        
        return {
            "total_cpu_percent": total_cpu,
            "total_memory_mb": total_memory,
            "agent_count": len([s for s in self.statuses.values() if s.state == AgentState.RUNNING]),
            "agent_usage": agent_usage
        }
    
    def register_health_check(self, name: str, callback: Callable):
        """注册健康检查回调"""
        self.health_check_callbacks[name] = callback
    
    def check_agent_health(self, name: str) -> float:
        """检查Agent健康度 (0-100)"""
        if name not in self.statuses:
            return 0.0
        
        status = self.statuses[name]
        meta = self.agents.get(name)
        
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
        
        score = 100.0
        
        # 资源限制检查
        if meta:
            if meta.max_cpu_percent > 0 and status.cpu_percent > meta.max_cpu_percent:
                score -= 30
            
            if meta.max_memory_mb > 0 and status.memory_mb > meta.max_memory_mb:
                score -= 30
        
        # CPU过高扣分
        if status.cpu_percent > 90:
            score -= 20
        elif status.cpu_percent > 70:
            score -= 10
        
        # 内存过高扣分
        if status.memory_mb > 2048:
            score -= 15
        elif status.memory_mb > 1024:
            score -= 5
        
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
                meta = self.agents.get(name)
                if not status or status.state not in [AgentState.RUNNING, AgentState.PAUSED]:
                    continue
                
                # 健康检查
                health = self.check_agent_health(name)
                old_health = status.health_score
                status.health_score = health
                
                # 更新心跳
                status.last_heartbeat = datetime.now().isoformat()
                
                # 健康度变化事件
                if old_health >= 50 and health < 50:
                    self.event_emitter.emit(LifecycleEvent.HEALTH_CHECK_FAILED, name, 
                                           {"health": health, "old_health": old_health})
                elif old_health < 50 and health >= 50:
                    self.event_emitter.emit(LifecycleEvent.HEALTH_CHECK_PASSED, name,
                                           {"health": health, "old_health": old_health})
                
                # 低健康度自动恢复
                if health < 50 and meta and meta.auto_restart:
                    if status.restart_count < meta.max_restarts:
                        print(f"⚠️ Agent健康度低({health:.0f}%)，尝试恢复: {name}")
                        status.state = AgentState.RECOVERING
                        self.restart_agent(name)
                        status.restart_count += 1
                        self.event_emitter.emit(LifecycleEvent.RECOVERED, name)
                
                # 进程意外退出
                if status.pid:
                    try:
                        proc = psutil.Process(status.pid)
                        if not proc.is_running():
                            status.state = AgentState.FAILED
                            status.last_error = "进程意外退出"
                            self._log_audit("process_died", name, {"restart_count": status.restart_count})
                            self.event_emitter.emit(LifecycleEvent.FAILED, name, {"reason": "process_died"})
                            if meta and meta.auto_restart:
                                if status.restart_count < meta.max_restarts:
                                    self.restart_agent(name)
                                    status.restart_count += 1
                    except psutil.NoSuchProcess:
                        status.state = AgentState.FAILED
                        status.last_error = "进程不存在"
                        self.event_emitter.emit(LifecycleEvent.FAILED, name, {"reason": "no_process"})
                        if meta and meta.auto_restart:
                            if status.restart_count < meta.max_restarts:
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
        paused = sum(1 for s in self.statuses.values() if s.state == AgentState.PAUSED)
        failed = sum(1 for s in self.statuses.values() if s.state == AgentState.FAILED)
        
        return {
            "total": total,
            "running": running,
            "paused": paused,
            "stopped": total - running - paused,
            "failed": failed,
            "agents": list(self.agents.keys()),
            "resource_usage": self.get_resource_usage()
        }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """获取审计日志"""
        return self.audit_log[-limit:]


# 演示和测试
if __name__ == "__main__":
    manager = AgentLifecycleManager()
    
    # 注册示例Agent（带依赖关系）
    manager.register_agent(AgentMetadata(
        name="monitor-agent",
        agent_type=AgentType.PYTHON,
        script_path=os.path.join(AGENTS_DIR, "monitor_agent.py"),
        auto_restart=True,
        max_restarts=3,
        startup_order=2,
        priority=80,
        max_memory_mb=512
    ))
    
    manager.register_agent(AgentMetadata(
        name="executor-agent",
        agent_type=AgentType.PYTHON,
        script_path=os.path.join(AGENTS_DIR, "executor_agent.py"),
        auto_restart=True,
        max_restarts=3,
        startup_order=1,
        priority=90,
        depends_on=["monitor-agent"],
        max_memory_mb=1024
    ))
    
    manager.register_agent(AgentMetadata(
        name="test-agent",
        agent_type=AgentType.SHELL,
        command="sleep 60",
        auto_restart=True,
        startup_order=3,
        priority=50
    ))
    
    # 演示事件监听
    def on_agent_event(event_data):
        print(f"📢 事件: {event_data['event']} - {event_data['agent_name']}")
    
    manager.event_emitter.on(LifecycleEvent.STARTED, on_agent_event)
    manager.event_emitter.on(LifecycleEvent.FAILED, on_agent_event)
    
    # 按依赖顺序启动
    print("\n=== 按依赖顺序启动所有Agent ===")
    results = manager.start_all_agents(ordered=True)
    for name, success in results.items():
        print(f"  {name}: {'✅' if success else '❌'}")
    
    # 获取状态
    print("\n=== Agent状态 ===")
    for name, status in manager.get_all_status().items():
        print(f"{name}: {status['state']} (PID: {status['pid']}, 内存: {status['memory_mb']:.1f}MB)")
    
    # 资源使用
    print("\n=== 资源使用 ===")
    usage = manager.get_resource_usage()
    print(f"总CPU: {usage['total_cpu_percent']:.1f}%, 总内存: {usage['total_memory_mb']:.1f}MB")
    
    # 启动监控
    manager.start_monitoring()
    
    # 运行一段时间
    print("\n=== 监控中 (10秒) ===")
    time.sleep(10)
    
    # 停止监控
    manager.stop_monitoring()
    
    # 按反向依赖顺序停止
    print("\n=== 按反向依赖顺序停止 ===")
    manager.stop_all_agents(reverse_order=True)
    
    # 最终状态
    print("\n=== 最终状态 ===")
    print(manager.get_summary())
    
    # 审计日志
    print("\n=== 审计日志 ===")
    for entry in manager.get_audit_log(10):
        print(f"  {entry['timestamp']} - {entry['action']} - {entry['agent_name']}")