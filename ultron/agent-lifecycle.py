#!/usr/bin/env python3
"""
智能体生命周期管理 (Agent Lifecycle Management)
全智能体生态系统 - 第1世核心组件
"""

import json
import time
import uuid
import threading
import asyncio
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import deque
from agent_foundation import AgentFoundation, AgentConfig, AgentType, AgentState, AgentCapability, get_registry


class LifecyclePhase(Enum):
    """生命周期阶段"""
    CREATION = "creation"
    INITIALIZATION = "initialization"
    ACTIVATION = "activation"
    OPERATION = "operation"
    MAINTENANCE = "maintenance"
    DEGRADATION = "degradation"
    RECOVERY = "recovery"
    TERMINATION = "termination"
    ARCHIVAL = "archival"


class TransitionType(Enum):
    """状态转换类型"""
    NORMAL = "normal"           # 正常转换
    AUTOMATED = "automated"     # 自动转换
    FORCED = "forced"           # 强制转换
    EMERGENCY = "emergency"     # 紧急转换
    SCHEDULED = "scheduled"     # 计划转换


@dataclass
class LifecycleTransition:
    """生命周期转换记录"""
    from_phase: LifecyclePhase
    to_phase: LifecyclePhase
    transition_type: TransitionType
    timestamp: float
    reason: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class HealthStatus:
    """健康状态"""
    overall: float = 1.0        # 0-1 健康评分
    performance: float = 1.0    # 性能健康
    reliability: float = 1.0    # 可靠性健康
    resource: float = 1.0       # 资源健康
    last_check: float = field(default_factory=time.time)


@dataclass
class LifecycleConfig:
    """生命周期配置"""
    auto_start: bool = True
    auto_recovery: bool = True
    max_restart_attempts: int = 3
    health_check_interval: int = 60  # 秒
    graceful_shutdown_timeout: int = 30
    maintenance_interval: int = 3600  # 1小时
    degradation_threshold: float = 0.3  # 降级阈值
    recovery_threshold: float = 0.7  # 恢复阈值


class LifecycleStateMachine:
    """
    生命周期状态机
    管理智能体的生命周期阶段转换
    """
    
    # 有效的状态转换
    VALID_TRANSITIONS = {
        LifecyclePhase.CREATION: [LifecyclePhase.INITIALIZATION],
        LifecyclePhase.INITIALIZATION: [LifecyclePhase.ACTIVATION, LifecyclePhase.TERMINATION],
        LifecyclePhase.ACTIVATION: [LifecyclePhase.OPERATION, LifecyclePhase.MAINTENANCE, LifecyclePhase.TERMINATION],
        LifecyclePhase.OPERATION: [LifecyclePhase.MAINTENANCE, LifecyclePhase.DEGRADATION, LifecyclePhase.TERMINATION],
        LifecyclePhase.MAINTENANCE: [LifecyclePhase.OPERATION, LifecyclePhase.RECOVERY, LifecyclePhase.TERMINATION],
        LifecyclePhase.DEGRADATION: [LifecyclePhase.RECOVERY, LifecyclePhase.TERMINATION],
        LifecyclePhase.RECOVERY: [LifecyclePhase.OPERATION, LifecyclePhase.MAINTENANCE, LifecyclePhase.DEGRADATION],
        LifecyclePhase.TERMINATION: [LifecyclePhase.ARCHIVAL],
        LifecyclePhase.ARCHIVAL: [],  # 终态
    }
    
    def __init__(self, agent: AgentFoundation, config: Optional[LifecycleConfig] = None):
        self.agent = agent
        self.config = config or LifecycleConfig()
        
        # 当前阶段
        self.current_phase = LifecyclePhase.CREATION
        
        # 转换历史
        self.transition_history: List[LifecycleTransition] = []
        
        # 阶段进入时间
        self.phase_entered_at = time.time()
        
        # 健康状态
        self.health = HealthStatus()
        
        # 统计
        self.total_uptime = 0.0
        self.total_downtime = 0.0
        self.restart_count = 0
        
        # 事件回调
        self.transition_callbacks: Dict[LifecyclePhase, List[Callable]] = {
            phase: [] for phase in LifecyclePhase
        }
        
        # 自动恢复任务
        self._recovery_task: Optional[threading.Thread] = None
        self._health_check_task: Optional[threading.Thread] = None
        self._running = False
    
    def can_transition(self, to_phase: LifecyclePhase) -> bool:
        """检查是否可以转换到指定阶段"""
        valid_next = self.VALID_TRANSITIONS.get(self.current_phase, [])
        return to_phase in valid_next
    
    def transition(self, to_phase: LifecyclePhase, 
                   transition_type: TransitionType = TransitionType.NORMAL,
                   reason: str = "",
                   metadata: Optional[Dict] = None) -> bool:
        """
        执行生命周期转换
        """
        if not self.can_transition(to_phase):
            return False
        
        from_phase = self.current_phase
        
        # 记录转换
        transition = LifecycleTransition(
            from_phase=from_phase,
            to_phase=to_phase,
            transition_type=transition_type,
            timestamp=time.time(),
            reason=reason,
            metadata=metadata or {}
        )
        self.transition_history.append(transition)
        
        # 更新阶段
        self.current_phase = to_phase
        self.phase_entered_at = time.time()
        
        # 更新统计
        if to_phase == LifecyclePhase.OPERATION:
            self.total_uptime += time.time() - self.phase_entered_at
        elif to_phase in [LifecyclePhase.DEGRADATION, LifecyclePhase.TERMINATION]:
            self.total_downtime += time.time() - self.phase_entered_at
        
        # 执行回调
        self._execute_callbacks(to_phase)
        
        # 触发智能体状态变化
        self._sync_agent_state(to_phase)
        
        return True
    
    def _sync_agent_state(self, phase: LifecyclePhase):
        """同步智能体状态"""
        state_mapping = {
            LifecyclePhase.CREATION: AgentState.CREATED,
            LifecyclePhase.INITIALIZATION: AgentState.INITIALIZING,
            LifecyclePhase.ACTIVATION: AgentState.ACTIVE,
            LifecyclePhase.OPERATION: AgentState.ACTIVE,
            LifecyclePhase.MAINTENANCE: AgentState.IDLE,
            LifecyclePhase.DEGRADATION: AgentState.ERROR,
            LifecyclePhase.RECOVERY: AgentState.PROCESSING,
            LifecyclePhase.TERMINATION: AgentState.TERMINATED,
        }
        
        if phase in state_mapping:
            # 通过反射设置状态
            pass  # AgentFoundation已经有自己的状态管理
    
    def _execute_callbacks(self, phase: LifecyclePhase):
        """执行阶段回调"""
        if phase in self.transition_callbacks:
            for callback in self.transition_callbacks[phase]:
                try:
                    callback(self.agent, phase)
                except Exception as e:
                    print(f"Callback error: {e}")
    
    def on_phase(self, phase: LifecyclePhase, callback: Callable):
        """注册阶段回调"""
        self.transition_callbacks[phase].append(callback)
    
    def force_transition(self, to_phase: LifecyclePhase, reason: str = "") -> bool:
        """强制转换（绕过检查）"""
        from_phase = self.current_phase
        
        transition = LifecycleTransition(
            from_phase=from_phase,
            to_phase=to_phase,
            transition_type=TransitionType.FORCED,
            timestamp=time.time(),
            reason=reason
        )
        self.transition_history.append(transition)
        
        self.current_phase = to_phase
        self.phase_entered_at = time.time()
        
        self._execute_callbacks(to_phase)
        return True
    
    # ==================== 健康检查 ====================
    
    def check_health(self) -> HealthStatus:
        """检查健康状态"""
        # 性能健康
        metrics = self.agent.metrics
        if metrics.tasks_completed > 0:
            success_rate = metrics.success_rate()
            avg_time = metrics.average_processing_time()
            
            # 基于成功率和响应时间计算
            self.health.performance = success_rate * 0.7 + (1.0 / (1.0 + avg_time)) * 0.3
        else:
            self.health.performance = 1.0
        
        # 可靠性健康
        error_rate = metrics.tasks_failed / max(1, metrics.tasks_completed + metrics.tasks_failed)
        self.health.reliability = 1.0 - error_rate
        
        # 资源健康（基于任务队列长度）
        queue_ratio = len(self.agent.task_queue) / max(1, self.agent.capabilities.max_concurrent_tasks)
        self.health.resource = 1.0 - min(1.0, queue_ratio)
        
        # 综合健康评分
        self.health.overall = (
            self.health.performance * 0.4 +
            self.health.reliability * 0.4 +
            self.health.resource * 0.2
        )
        
        self.health.last_check = time.time()
        
        return self.health
    
    def start_health_monitoring(self):
        """启动健康监控"""
        if self._running:
            return
        
        self._running = True
        
        def monitor_loop():
            while self._running:
                health = self.check_health()
                
                # 自动恢复
                if self.config.auto_recovery:
                    if health.overall < self.config.degradation_threshold:
                        self._trigger_recovery()
                
                time.sleep(self.config.health_check_interval)
        
        self._health_check_task = threading.Thread(target=monitor_loop, daemon=True)
        self._health_check_task.start()
    
    def stop_health_monitoring(self):
        """停止健康监控"""
        self._running = False
    
    def _trigger_recovery(self):
        """触发恢复"""
        if self.current_phase == LifecyclePhase.DEGRADATION:
            return  # 已经在恢复中
        
        # 转换到恢复阶段
        self.transition(
            LifecyclePhase.RECOVERY,
            TransitionType.AUTOMATED,
            "Auto-recovery triggered"
        )
        
        # 执行恢复操作
        self._perform_recovery()
    
    def _perform_recovery(self):
        """执行恢复操作"""
        # 清空失败的任务
        failed_tasks = [t for t in self.agent.task_queue if t.get("status") == "failed"]
        for task in failed_tasks:
            self.agent.task_queue.remove(task)
        
        # 尝试恢复
        self.agent.resume()
        
        # 等待恢复
        time.sleep(2)
        
        # 检查是否恢复成功
        health = self.check_health()
        
        if health.overall >= self.config.recovery_threshold:
            self.transition(
                LifecyclePhase.OPERATION,
                TransitionType.AUTOMATED,
                "Recovery successful"
            )
        else:
            self.transition(
                LifecyclePhase.DEGRADATION,
                TransitionType.AUTOMATED,
                "Recovery failed"
            )
    
    # ==================== 生命周期操作 ====================
    
    def start(self):
        """启动智能体生命周期"""
        if self.current_phase == LifecyclePhase.CREATION:
            self.transition(
                LifecyclePhase.INITIALIZATION,
                TransitionType.AUTOMATED,
                "Initial startup"
            )
            
            # 执行初始化
            self.agent._initialize()
            
            self.transition(
                LifecyclePhase.ACTIVATION,
                TransitionType.AUTOMATED,
                "Initialization complete"
            )
            
            self.agent.start()
            
            if self.config.auto_start:
                self.transition(
                    LifecyclePhase.OPERATION,
                    TransitionType.AUTOMATED,
                    "Auto-start enabled"
                )
                
                # 启动健康监控
                self.start_health_monitoring()
    
    def stop(self, graceful: bool = True):
        """停止智能体"""
        if graceful and self.config.graceful_shutdown_timeout > 0:
            # 优雅关闭：等待任务完成
            self.transition(
                LifecyclePhase.MAINTENANCE,
                TransitionType.SCHEDULED,
                "Graceful shutdown"
            )
            
            # 等待任务完成
            timeout = self.config.graceful_shutdown_timeout
            start_wait = time.time()
            
            while len(self.agent.task_queue) > 0 and time.time() - start_wait < timeout:
                time.sleep(1)
        
        self.transition(
            LifecyclePhase.TERMINATION,
            TransitionType.NORMAL,
            "Stop requested"
        )
        
        # 停止健康监控
        self.stop_health_monitoring()
        
        # 终止智能体
        self.agent.terminate()
        
        # 归档
        self.transition(
            LifecyclePhase.ARCHIVAL,
            TransitionType.NORMAL,
            "Lifecycle complete"
        )
    
    def pause(self):
        """暂停"""
        if self.current_phase == LifecyclePhase.OPERATION:
            self.transition(
                LifecyclePhase.MAINTENANCE,
                TransitionType.NORMAL,
                "Pause requested"
            )
            self.agent.pause()
    
    def resume(self):
        """恢复"""
        if self.current_phase == LifecyclePhase.MAINTENANCE:
            self.transition(
                LifecyclePhase.OPERATION,
                TransitionType.NORMAL,
                "Resume requested"
            )
            self.agent.resume()
    
    def restart(self):
        """重启"""
        if self.restart_count >= self.config.max_restart_attempts:
            print(f"Max restart attempts reached: {self.config.max_restart_attempts}")
            return False
        
        self.restart_count += 1
        
        # 停止
        self.stop(graceful=False)
        
        # 重新创建智能体（简化处理：重新初始化）
        self.agent.metrics = type(self.agent.metrics)()
        self.agent.task_queue.clear()
        self.agent.completed_tasks.clear()
        
        # 重新启动
        self.start()
        
        return True
    
    # ==================== 状态查询 ====================
    
    def get_phase(self) -> LifecyclePhase:
        """获取当前阶段"""
        return self.current_phase
    
    def get_status(self) -> Dict:
        """获取生命周期状态"""
        return {
            "phase": self.current_phase.value,
            "phase_duration": time.time() - self.phase_entered_at,
            "health": {
                "overall": self.health.overall,
                "performance": self.health.performance,
                "reliability": self.health.reliability,
                "resource": self.health.resource
            },
            "total_uptime": self.total_uptime,
            "total_downtime": self.total_downtime,
            "restart_count": self.restart_count,
            "transition_count": len(self.transition_history)
        }
    
    def get_transition_history(self, limit: int = 10) -> List[Dict]:
        """获取转换历史"""
        history = self.transition_history[-limit:]
        return [
            {
                "from": t.from_phase.value,
                "to": t.to_phase.value,
                "type": t.transition_type.value,
                "timestamp": t.timestamp,
                "reason": t.reason
            }
            for t in history
        ]


class AgentLifecycleManager:
    """
    智能体生命周期管理器
    管理多个智能体的生命周期
    """
    
    def __init__(self):
        self.lifecycle_states: Dict[str, LifecycleStateMachine] = {}
        self.global_config = LifecycleConfig()
        
        # 统计
        self.total_lifecycles = 0
        self.active_count = 0
    
    def register_agent(self, agent: AgentFoundation, config: Optional[LifecycleConfig] = None) -> LifecycleStateMachine:
        """注册智能体并创建生命周期管理"""
        lifecycle = LifecycleStateMachine(agent, config or self.global_config)
        self.lifecycle_states[agent.id] = lifecycle
        self.total_lifecycles += 1
        self.active_count += 1
        
        return lifecycle
    
    def unregister_agent(self, agent_id: str):
        """注销智能体"""
        if agent_id in self.lifecycle_states:
            lifecycle = self.lifecycle_states[agent_id]
            lifecycle.stop()
            del self.lifecycle_states[agent_id]
            self.active_count -= 1
    
    def get_lifecycle(self, agent_id: str) -> Optional[LifecycleStateMachine]:
        """获取智能体的生命周期状态机"""
        return self.lifecycle_states.get(agent_id)
    
    def start_all(self):
        """启动所有智能体"""
        for lifecycle in self.lifecycle_states.values():
            try:
                lifecycle.start()
            except Exception as e:
                print(f"Error starting agent: {e}")
    
    def stop_all(self, graceful: bool = True):
        """停止所有智能体"""
        for lifecycle in self.lifecycle_states.values():
            try:
                lifecycle.stop(graceful)
            except Exception as e:
                print(f"Error stopping agent: {e}")
    
    def get_all_status(self) -> Dict:
        """获取所有智能体状态"""
        status = {
            "total_registered": self.total_lifecycles,
            "active": self.active_count,
            "agents": {}
        }
        
        for agent_id, lifecycle in self.lifecycle_states.items():
            status["agents"][agent_id] = lifecycle.get_status()
        
        return status
    
    def get_health_summary(self) -> Dict:
        """获取健康摘要"""
        total_health = 0.0
        health_counts = {"healthy": 0, "degraded": 0, "critical": 0}
        
        for lifecycle in self.lifecycle_states.values():
            health = lifecycle.check_health()
            total_health += health.overall
            
            if health.overall >= 0.7:
                health_counts["healthy"] += 1
            elif health.overall >= 0.4:
                health_counts["degraded"] += 1
            else:
                health_counts["critical"] += 1
        
        avg_health = total_health / len(self.lifecycle_states) if self.lifecycle_states else 0
        
        return {
            "average_health": avg_health,
            "counts": health_counts,
            "total": len(self.lifecycle_states)
        }


# 全局生命周期管理器
_lifecycle_manager = AgentLifecycleManager()


def get_lifecycle_manager() -> AgentLifecycleManager:
    """获取全局生命周期管理器"""
    return _lifecycle_manager


# 示例使用
if __name__ == "__main__":
    from agent_foundation import AgentFoundation, AgentConfig, AgentType
    
    # 创建智能体
    config = AgentConfig(
        name="LifecycleTestAgent",
        agent_type=AgentType.SPECIALIST,
        description="生命周期测试",
        tags=["test"]
    )
    agent = AgentFoundation(config)
    
    # 创建生命周期管理
    manager = get_lifecycle_manager()
    lifecycle = manager.register_agent(agent)
    
    # 注册阶段回调
    lifecycle.on_phase(LifecyclePhase.OPERATION, lambda a, p: print(f"Agent {a.config.name} is now operational"))
    
    # 启动
    lifecycle.start()
    
    # 提交任务
    agent.submit_task({"type": "test", "input": "data"})
    
    # 获取状态
    print(f"Lifecycle status: {lifecycle.get_status()}")
    print(f"Health summary: {manager.get_health_summary()}")
    
    # 停止
    lifecycle.stop()
    
    print("Lifecycle test completed")