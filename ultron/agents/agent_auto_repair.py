#!/usr/bin/env python3
"""
Agent自动修复模块 - 第53世
负责Agent故障检测、自动修复与恢复

功能:
- Agent健康状态监控
- 故障检测与诊断
- 自动修复策略
- 修复历史记录
- 修复超时与重试
"""

import json
import time
import asyncio
import subprocess
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from threading import Thread, Event, Lock
from collections import defaultdict
import os
import sys
import traceback
import psutil

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENTS_DIR)

from agent_lifecycle_manager import AgentLifecycleManager, AgentState, AgentMetadata


class RepairStrategy(Enum):
    """修复策略"""
    RESTART = "restart"           # 重启Agent
    RECREATE = "recreate"         # 重新创建进程
    ROLLBACK = "rollback"         # 回滚到上一个稳定版本
    SCALE_UP = "scale_up"         # 增加资源
    ISOLATE = "isolate"           # 隔离问题Agent
    NOTIFY = "notify"             # 仅通知，不修复
    IGNORE = "ignore"             # 忽略


class RepairStatus(Enum):
    """修复状态"""
    PENDING = "pending"           # 待修复
    IN_PROGRESS = "in_progress"   # 修复中
    SUCCESS = "success"           # 修复成功
    FAILED = "failed"             # 修复失败
    SKIPPED = "skipped"           # 跳过


class FailureType(Enum):
    """故障类型"""
    CRASH = "crash"               # 崩溃
    HANG = "hang"                 # 挂起
    MEMORY_LEAK = "memory_leak"      # 内存泄漏
    HIGH_CPU = "high_cpu"         # CPU过高
    UNRESPONSIVE = "unresponsive"  # 无响应
    HEALTH_CHECK_FAIL = "health_check_fail"  # 健康检查失败
    DEPENDENCY_LOST = "dependency_lost"  # 依赖丢失
    RESOURCE_EXHAUSTED = "resource_exhausted"  # 资源耗尽


@dataclass
class RepairConfig:
    """修复配置"""
    enabled: bool = True
    auto_repair: bool = True           # 是否自动修复
    max_repair_attempts: int = 3       # 最大修复尝试次数
    repair_timeout: int = 60          # 修复超时（秒）
    repair_cooldown: int = 300        # 修复冷却时间（秒）
    health_check_on_repair: bool = True  # 修复后健康检查
    
    # 故障检测阈值
    crash_threshold: int = 3           # 崩溃次数阈值
    memory_threshold_percent: float = 90.0  # 内存阈值
    cpu_threshold_percent: float = 90.0     # CPU阈值
    unresponsive_timeout: int = 60    # 无响应超时
    
    # 修复策略配置
    default_strategy: RepairStrategy = RepairStrategy.RESTART
    strategies: Dict[str, RepairStrategy] = field(default_factory=dict)  # 按故障类型配置


@dataclass
class RepairRecord:
    """修复记录"""
    agent_name: str
    failure_type: FailureType
    strategy: RepairStrategy
    status: RepairStatus
    attempt: int
    timestamp: str
    duration_ms: int
    details: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    before_state: AgentState = None
    after_state: AgentState = None


@dataclass
class DiagnosticResult:
    """诊断结果"""
    failure_type: FailureType
    severity: str  # critical, warning, info
    root_cause: str
    recommendations: List[str]
    can_repair: bool
    suggested_strategy: RepairStrategy


class AgentAutoRepair:
    """Agent自动修复器"""
    
    def __init__(self, lifecycle_manager: AgentLifecycleManager, config: Optional[RepairConfig] = None):
        self.lifecycle = lifecycle_manager
        self.config = config or RepairConfig()
        self.repair_history: List[RepairRecord] = []
        self.repair_queue: Dict[str, RepairRecord] = {}  # 待修复队列
        self.last_repair_time: Dict[str, float] = {}     # 上次修复时间
        self.repair_attempts: Dict[str, int] = {}       # 修复尝试次数
        self.running = False
        self._lock = Lock()
        self._monitor_thread: Optional[Thread] = None
        self._stop_event = Event()
        
        # 诊断回调
        self.diagnostic_handlers: Dict[FailureType, Callable] = {}
        self._register_default_diagnostics()
    
    def _register_default_diagnostics(self):
        """注册默认诊断处理器"""
        self.diagnostic_handlers = {
            FailureType.CRASH: self._diagnose_crash,
            FailureType.HANG: self._diagnose_hang,
            FailureType.MEMORY_LEAK: self._diagnose_memory_leak,
            FailureType.HIGH_CPU: self._diagnose_high_cpu,
            FailureType.UNRESPONSIVE: self._diagnose_unresponsive,
            FailureType.HEALTH_CHECK_FAIL: self._diagnose_health_check_fail,
            FailureType.DEPENDENCY_LOST: self._diagnose_dependency_lost,
            FailureType.RESOURCE_EXHAUSTED: self._diagnose_resource_exhausted,
        }
    
    def start(self):
        """启动自动修复模块"""
        if self.running:
            return
        
        self.running = True
        self._stop_event.clear()
        self._monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print(f"✅ Agent自动修复模块已启动")
    
    def stop(self):
        """停止自动修复模块"""
        self.running = False
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        print(f"🛑 Agent自动修复模块已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                self._check_all_agents()
            except Exception as e:
                print(f"⚠️ 监控循环异常: {e}")
            
            # 每10秒检查一次
            self._stop_event.wait(10)
    
    def _check_all_agents(self):
        """检查所有Agent状态"""
        if not self.lifecycle.statuses:
            return
        
        for agent_name, status in list(self.lifecycle.statuses.items()):
            # 检查是否需要修复
            if self._needs_repair(agent_name, status):
                self._queue_repair(agent_name)
    
    def _needs_repair(self, agent_name: str, status) -> bool:
        """检查Agent是否需要修复"""
        if not self.config.enabled or not self.config.auto_repair:
            return False
        
        # 检查冷却时间
        if agent_name in self.last_repair_time:
            elapsed = time.time() - self.last_repair_time[agent_name]
            if elapsed < self.config.repair_cooldown:
                return False
        
        # 检查修复次数
        attempts = self.repair_attempts.get(agent_name, 0)
        if attempts >= self.config.max_repair_attempts:
            return False
        
        # 根据状态判断
        if status.state == AgentState.FAILED:
            return True
        
        if status.state == AgentState.RUNNING:
            # 检查健康指标
            if status.health_score < 50:
                return True
            
            # 检查CPU
            if status.cpu_percent > self.config.cpu_threshold_percent:
                return True
            
            # 检查内存
            if status.memory_mb > 0:
                # 估算内存百分比（需要总内存）
                mem = psutil.virtual_memory()
                mem_percent = (status.memory_mb / (mem.total / 1024 / 1024)) * 100
                if mem_percent > self.config.memory_threshold_percent:
                    return True
            
            # 检查重启次数（频繁重启）
            if status.restart_count >= self.config.crash_threshold:
                return True
        
        # 检查无响应
        if status.last_heartbeat:
            elapsed = time.time() - status.last_heartbeat
            if elapsed > self.config.unresponsive_timeout:
                return True
        
        return False
    
    def _queue_repair(self, agent_name: str):
        """将Agent加入修复队列"""
        with self._lock:
            if agent_name in self.repair_queue:
                return  # 已在队列中
            
            # 诊断故障类型
            failure_type = self._diagnose_failure(agent_name)
            
            # 创建修复记录
            record = RepairRecord(
                agent_name=agent_name,
                failure_type=failure_type,
                strategy=self._get_repair_strategy(failure_type),
                status=RepairStatus.PENDING,
                attempt=self.repair_attempts.get(agent_name, 0) + 1,
                timestamp=datetime.now().isoformat(),
                duration_ms=0,
                before_state=self.lifecycle.statuses.get(agent_name, None)
            )
            
            self.repair_queue[agent_name] = record
            print(f"📋 加入修复队列: {agent_name} (故障: {failure_type.value}, 策略: {record.strategy.value})")
            
            # 异步执行修复
            Thread(target=self._execute_repair, args=(agent_name,), daemon=True).start()
    
    def _diagnose_failure(self, agent_name: str) -> FailureType:
        """诊断故障类型"""
        status = self.lifecycle.statuses.get(agent_name)
        if not status:
            return FailureType.CRASH
        
        # 根据状态和指标判断
        if status.state == AgentState.FAILED:
            if status.last_error:
                error = status.last_error.lower()
                if "memory" in error:
                    return FailureType.MEMORY_LEAK
                elif "cpu" in error:
                    return FailureType.HIGH_CPU
            
            # 检查重启次数
            if status.restart_count >= self.config.crash_threshold:
                return FailureType.CRASH
        
        # 检查CPU
        if status.cpu_percent > self.config.cpu_threshold_percent:
            return FailureType.HIGH_CPU
        
        # 检查内存（这里简单判断，实际需要趋势分析）
        mem = psutil.virtual_memory()
        if status.memory_mb > 0:
            mem_percent = (status.memory_mb / (mem.total / 1024 / 1024)) * 100
            if mem_percent > self.config.memory_threshold_percent:
                return FailureType.MEMORY_LEAK
        
        # 检查无响应
        if status.last_heartbeat:
            elapsed = time.time() - status.last_heartbeat
            if elapsed > self.config.unresponsive_timeout:
                return FailureType.UNRESPONSIVE
        
        # 检查健康检查失败（通过事件历史判断）
        recent_failures = [e for e in status.event_history[-10:] 
                         if 'health_check_failed' in str(e)]
        if len(recent_failures) >= 3:
            return FailureType.HEALTH_CHECK_FAIL
        
        # 检查依赖
        meta = self.lifecycle.agents.get(agent_name)
        if meta and meta.depends_on:
            for dep in meta.depends_on:
                dep_status = self.lifecycle.statuses.get(dep)
                if not dep_status or dep_status.state != AgentState.RUNNING:
                    return FailureType.DEPENDENCY_LOST
        
        return FailureType.UNRESPONSIVE
    
    def _diagnose_crash(self, agent_name: str) -> DiagnosticResult:
        """诊断崩溃"""
        status = self.lifecycle.statuses.get(agent_name)
        return DiagnosticResult(
            failure_type=FailureType.CRASH,
            severity="critical",
            root_cause=f"Agent崩溃，重启次数: {status.restart_count if status else 'N/A'}",
            recommendations=[
                "检查Agent日志获取详细错误信息",
                "检查系统资源是否充足",
                "考虑增加健康检查频率"
            ],
            can_repair=True,
            suggested_strategy=RepairStrategy.RESTART
        )
    
    def _diagnose_hang(self, agent_name: str) -> DiagnosticResult:
        """诊断挂起"""
        return DiagnosticResult(
            failure_type=FailureType.HANG,
            severity="critical",
            root_cause="Agent进程挂起，无响应",
            recommendations=[
                "检查Agent进程是否阻塞",
                "检查网络连接",
                "尝试强制重启"
            ],
            can_repair=True,
            suggested_strategy=RepairStrategy.RECREATE
        )
    
    def _diagnose_memory_leak(self, agent_name: str) -> DiagnosticResult:
        """诊断内存泄漏"""
        status = self.lifecycle.statuses.get(agent_name)
        mem_info = f"内存使用: {status.memory_mb if status else 'N/A'}MB"
        return DiagnosticResult(
            failure_type=FailureType.MEMORY_LEAK,
            severity="warning",
            root_cause=f"内存使用过高 - {mem_info}",
            recommendations=[
                "增加内存限制",
                "检查代码中的内存泄漏",
                "考虑重启释放内存"
            ],
            can_repair=True,
            suggested_strategy=RepairStrategy.RESTART
        )
    
    def _diagnose_high_cpu(self, agent_name: str) -> DiagnosticResult:
        """诊断CPU过高"""
        status = self.lifecycle.statuses.get(agent_name)
        return DiagnosticResult(
            failure_type=FailureType.HIGH_CPU,
            severity="warning",
            root_cause=f"CPU使用率过高: {status.cpu_percent if status else 'N/A'}%",
            recommendations=[
                "检查Agent是否有死循环",
                "考虑增加CPU资源",
                "限制并发请求数"
            ],
            can_repair=True,
            suggested_strategy=RepairStrategy.SCALE_UP
        )
    
    def _diagnose_unresponsive(self, agent_name: str) -> DiagnosticResult:
        """诊断无响应"""
        status = self.lifecycle.statuses.get(agent_name)
        return DiagnosticResult(
            failure_type=FailureType.UNRESPONSIVE,
            severity="warning",
            root_cause="Agent无响应",
            recommendations=[
                "检查Agent进程状态",
                "检查网络连接",
                "尝试重启"
            ],
            can_repair=True,
            suggested_strategy=RepairStrategy.RESTART
        )
    
    def _diagnose_health_check_fail(self, agent_name: str) -> DiagnosticResult:
        """诊断健康检查失败"""
        return DiagnosticResult(
            failure_type=FailureType.HEALTH_CHECK_FAIL,
            severity="warning",
            root_cause="连续健康检查失败",
            recommendations=[
                "检查Agent内部状态",
                "检查依赖服务",
                "查看健康检查日志"
            ],
            can_repair=True,
            suggested_strategy=RepairStrategy.RESTART
        )
    
    def _diagnose_dependency_lost(self, agent_name: str) -> DiagnosticResult:
        """诊断依赖丢失"""
        meta = self.lifecycle.agents.get(agent_name)
        missing = []
        if meta:
            for dep in meta.depends_on:
                dep_status = self.lifecycle.statuses.get(dep)
                if not dep_status or dep_status.state != AgentState.RUNNING:
                    missing.append(dep)
        
        return DiagnosticResult(
            failure_type=FailureType.DEPENDENCY_LOST,
            severity="warning",
            root_cause=f"依赖不可用: {missing}",
            recommendations=[
                "先修复依赖的Agent",
                "调整启动顺序",
                "考虑启动依赖后再启动此Agent"
            ],
            can_repair=False,  # 无法直接修复，需先修复依赖
            suggested_strategy=RepairStrategy.NOTIFY
        )
    
    def _diagnose_resource_exhausted(self, agent_name: str) -> DiagnosticResult:
        """诊断资源耗尽"""
        return DiagnosticResult(
            failure_type=FailureType.RESOURCE_EXHAUSTED,
            severity="critical",
            root_cause="系统资源耗尽",
            recommendations=[
                "增加系统资源",
                "清理其他占用资源的进程",
                "考虑横向扩展"
            ],
            can_repair=True,
            suggested_strategy=RepairStrategy.SCALE_UP
        )
    
    def _get_repair_strategy(self, failure_type: FailureType) -> RepairStrategy:
        """获取修复策略"""
        # 检查配置中是否有针对该故障类型的策略
        if failure_type in self.config.strategies:
            return self.config.strategies[failure_type]
        
        # 使用默认策略
        return self.config.default_strategy
    
    def _execute_repair(self, agent_name: str):
        """执行修复"""
        with self._lock:
            if agent_name not in self.repair_queue:
                return
            
            record = self.repair_queue[agent_name]
            record.status = RepairStatus.IN_PROGRESS
        
        start_time = time.time()
        print(f"🔧 开始修复: {agent_name} (尝试 {record.attempt}/{self.config.max_repair_attempts})")
        
        try:
            # 根据策略执行修复
            success = False
            
            if record.strategy == RepairStrategy.RESTART:
                success = self._repair_restart(agent_name)
            elif record.strategy == RepairStrategy.RECREATE:
                success = self._repair_recreate(agent_name)
            elif record.strategy == RepairStrategy.SCALE_UP:
                success = self._repair_scale_up(agent_name)
            elif record.strategy == RepairStrategy.ISOLATE:
                success = self._repair_isolate(agent_name)
            elif record.strategy == RepairStrategy.NOTIFY:
                success = self._repair_notify(agent_name)
            elif record.strategy == RepairStrategy.IGNORE:
                success = True
            else:
                success = self._repair_restart(agent_name)
            
            # 更新记录
            duration_ms = int((time.time() - start_time) * 1000)
            record.duration_ms = duration_ms
            record.status = RepairStatus.SUCCESS if success else RepairStatus.FAILED
            record.after_state = self.lifecycle.statuses.get(agent_name)
            
            if success:
                self.last_repair_time[agent_name] = time.time()
                self.repair_attempts[agent_name] = 0  # 重置重试次数
                print(f"✅ 修复成功: {agent_name} (耗时 {duration_ms}ms)")
            else:
                self.repair_attempts[agent_name] = record.attempt
                if record.attempt < self.config.max_repair_attempts:
                    # 再次加入队列
                    time.sleep(5)  # 等待后重试
                    self._queue_repair(agent_name)
                else:
                    print(f"❌ 修复失败，已达最大重试次数: {agent_name}")
        
        except Exception as e:
            record.status = RepairStatus.FAILED
            record.error = str(e)
            record.duration_ms = int((time.time() - start_time) * 1000)
            print(f"❌ 修复异常: {agent_name} - {e}")
            traceback.print_exc()
        
        finally:
            # 移动到历史记录
            with self._lock:
                if agent_name in self.repair_queue:
                    del self.repair_queue[agent_name]
                self.repair_history.append(record)
                
                # 只保留最近100条
                if len(self.repair_history) > 100:
                    self.repair_history = self.repair_history[-100:]
    
    def _repair_restart(self, agent_name: str) -> bool:
        """重启修复"""
        try:
            # 先停止
            self.lifecycle.stop_agent(agent_name)
            time.sleep(2)
            # 再启动
            return self.lifecycle.start_agent(agent_name)
        except Exception as e:
            print(f"⚠️ 重启修复失败: {e}")
            return False
    
    def _repair_recreate(self, agent_name: str) -> bool:
        """重新创建修复"""
        try:
            # 完全注销再重新注册
            meta = self.lifecycle.agents.get(agent_name)
            if not meta:
                return False
            
            # 保存元数据
            meta_copy = AgentMetadata(
                name=meta.name,
                agent_type=meta.agent_type,
                script_path=meta.script_path,
                command=meta.command,
                env=meta.env.copy(),
                cwd=meta.cwd,
                auto_restart=meta.auto_restart,
                max_restarts=meta.max_restarts,
                health_check_interval=meta.health_check_interval,
                startup_timeout=meta.startup_timeout,
                depends_on=meta.depends_on.copy(),
                startup_order=meta.startup_order,
                max_cpu_percent=meta.max_cpu_percent,
                max_memory_mb=meta.max_memory_mb,
                priority=meta.priority,
                pre_start_hook=meta.pre_start_hook,
                post_start_hook=meta.post_start_hook,
                pre_stop_hook=meta.pre_stop_hook,
                post_stop_hook=meta.post_stop_hook
            )
            
            # 注销
            self.lifecycle.unregister_agent(agent_name)
            time.sleep(1)
            
            # 重新注册
            self.lifecycle.register_agent(meta_copy)
            
            # 启动
            return self.lifecycle.start_agent(agent_name)
        
        except Exception as e:
            print(f"⚠️ 重新创建修复失败: {e}")
            return False
    
    def _repair_scale_up(self, agent_name: str) -> bool:
        """扩容修复"""
        try:
            # 增加资源限制
            meta = self.lifecycle.agents.get(agent_name)
            if meta:
                # 增加内存限制
                if meta.max_memory_mb > 0:
                    meta.max_memory_mb *= 1.5
                # 增加CPU限制
                if meta.max_cpu_percent > 0:
                    meta.max_cpu_percent = min(meta.max_cpu_percent * 1.5, 100.0)
                
                self.lifecycle._save_state()
                print(f"📈 已增加资源配额: {agent_name}")
            
            return self._repair_restart(agent_name)
        
        except Exception as e:
            print(f"⚠️ 扩容修复失败: {e}")
            return False
    
    def _repair_isolate(self, agent_name: str) -> bool:
        """隔离修复"""
        try:
            # 标记为暂停，停止运行
            self.lifecycle.pause_agent(agent_name)
            print(f"🔒 已隔离问题Agent: {agent_name}")
            return True
        except Exception as e:
            print(f"⚠️ 隔离修复失败: {e}")
            return False
    
    def _repair_notify(self, agent_name: str) -> bool:
        """通知修复（仅通知）"""
        # 发送通知
        print(f"📢 需要人工干预: {agent_name}")
        # 这里可以集成通知系统
        return True
    
    def get_repair_status(self, agent_name: str) -> Optional[RepairRecord]:
        """获取Agent修复状态"""
        with self._lock:
            if agent_name in self.repair_queue:
                return self.repair_queue[agent_name]
            
            # 查找最近的历史记录
            for record in reversed(self.repair_history):
                if record.agent_name == agent_name:
                    return record
        
        return None
    
    def get_repair_history(self, agent_name: Optional[str] = None, limit: int = 20) -> List[RepairRecord]:
        """获取修复历史"""
        with self._lock:
            if agent_name:
                return [r for r in self.repair_history if r.agent_name == agent_name][-limit:]
            return self.repair_history[-limit:]
    
    def get_repair_stats(self) -> Dict[str, Any]:
        """获取修复统计"""
        with self._lock:
            total = len(self.repair_history)
            success = sum(1 for r in self.repair_history if r.status == RepairStatus.SUCCESS)
            failed = sum(1 for r in self.repair_history if r.status == RepairStatus.FAILED)
            
            return {
                "total_repairs": total,
                "success": success,
                "failed": failed,
                "success_rate": f"{(success/total*100):.1f}%" if total > 0 else "N/A",
                "pending_repairs": len(self.repair_queue),
                "enabled": self.config.enabled,
                "auto_repair": self.config.auto_repair
            }
    
    def force_repair(self, agent_name: str, strategy: Optional[RepairStrategy] = None) -> bool:
        """强制修复"""
        if agent_name not in self.lifecycle.agents:
            print(f"❌ Agent不存在: {agent_name}")
            return False
        
        failure_type = self._diagnose_failure(agent_name)
        repair_strategy = strategy or self._get_repair_strategy(failure_type)
        
        record = RepairRecord(
            agent_name=agent_name,
            failure_type=failure_type,
            strategy=repair_strategy,
            status=RepairStatus.PENDING,
            attempt=1,
            timestamp=datetime.now().isoformat(),
            duration_ms=0
        )
        
        self.repair_queue[agent_name] = record
        
        Thread(target=self._execute_repair, args=(agent_name,), daemon=True).start()
        
        return True
    
    def update_config(self, config: RepairConfig):
        """更新配置"""
        self.config = config
    
    def get_diagnostic_report(self, agent_name: str) -> DiagnosticResult:
        """获取诊断报告"""
        if agent_name not in self.lifecycle.agents:
            raise ValueError(f"Agent不存在: {agent_name}")
        
        failure_type = self._diagnose_failure(agent_name)
        
        # 调用对应的诊断处理器
        handler = self.diagnostic_handlers.get(failure_type)
        if handler:
            return handler(agent_name)
        
        return DiagnosticResult(
            failure_type=failure_type,
            severity="unknown",
            root_cause="未知故障",
            recommendations=["请人工检查"],
            can_repair=True,
            suggested_strategy=RepairStrategy.RESTART
        )


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent自动修复模块")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--agent", help="指定Agent名称")
    parser.add_argument("--action", choices=["start", "stop", "status", "repair", "diagnose", "history", "stats"], 
                       default="status", help="操作")
    parser.add_argument("--strategy", choices=["restart", "recreate", "scale_up", "isolate", "notify", "ignore"],
                       help="修复策略")
    
    args = parser.parse_args()
    
    # 加载生命周期管理器
    lifecycle = AgentLifecycleManager()
    
    # 创建自动修复模块
    repair = AgentAutoRepair(lifecycle)
    
    if args.action == "start":
        repair.start()
        print("✅ 自动修复模块已启动")
    
    elif args.action == "stop":
        repair.stop()
        print("🛑 自动修复模块已停止")
    
    elif args.action == "status":
        stats = repair.get_repair_stats()
        print(f"""
╔══════════════════════════════════════╗
║     Agent自动修复模块状态             ║
╠══════════════════════════════════════╣
║ 启用状态: {stats['enabled']}
║ 自动修复: {stats['auto_repair']}
║ 总修复次数: {stats['total_repairs']}
║ 成功: {stats['success']}
║ 失败: {stats['failed']}
║ 成功率: {stats['success_rate']}
║ 待处理: {stats['pending_repairs']}
╚══════════════════════════════════════╝
""")
    
    elif args.action == "repair":
        if not args.agent:
            print("❌ 请指定Agent名称 (--agent)")
            return
        
        strategy = RepairStrategy(args.strategy) if args.strategy else None
        success = repair.force_repair(args.agent, strategy)
        if success:
            print(f"✅ 修复已启动: {args.agent}")
        else:
            print(f"❌ 修复失败: {args.agent}")
    
    elif args.action == "diagnose":
        if not args.agent:
            print("❌ 请指定Agent名称 (--agent)")
            return
        
        report = repair.get_diagnostic_report(args.agent)
        print(f"""
╔══════════════════════════════════════╗
║     Agent诊断报告: {args.agent[:20]:<20}     ║
╠══════════════════════════════════════╣
║ 故障类型: {report.failure_type.value}
║ 严重程度: {report.severity}
║ 根本原因: {report.root_cause[:30]:<30}
║ 可修复: {report.can_repair}
║ 建议策略: {report.suggested_strategy.value}
╠══════════════════════════════════════╣
║ 建议:
""")
        for rec in report.recommendations:
            print(f"║   - {rec}")
        print("╚══════════════════════════════════════╝")
    
    elif args.action == "history":
        history = repair.get_repair_history(args.agent)
        print(f"\n{'时间':<25} {'Agent':<20} {'故障类型':<15} {'策略':<10} {'状态':<10} {'耗时(ms)':<10}")
        print("-" * 95)
        for r in history:
            print(f"{r.timestamp:<25} {r.agent_name:<20} {r.failure_type.value:<15} {r.strategy.value:<10} {r.status.value:<10} {r.duration_ms:<10}")
    
    elif args.action == "stats":
        stats = repair.get_repair_stats()
        for k, v in stats.items():
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()