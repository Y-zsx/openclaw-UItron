#!/usr/bin/env python3
"""
Agent协作网络健康检查与自动恢复机制
Agent Collaboration Network Health Check & Auto-Recovery System

功能:
- 健康检查: 定期检查Agent存活状态和性能指标
- 自动恢复: Agent故障时自动尝试恢复
- 故障转移: 自动将任务转移到健康Agent
- 告警机制: 异常状态时触发告警
"""

import json
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import threading
import queue

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DEAD = "dead"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """恢复操作枚举"""
    NONE = "none"
    RESTART = "restart"
    RESET = "reset"
    REDEPLOY = "redeploy"
    FAILOVER = "failover"


@dataclass
class AgentHealth:
    """Agent健康信息"""
    agent_id: str
    status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    total_failures: int = 0
    last_check: datetime = field(default_factory=datetime.now)
    last_success: datetime = field(default_factory=datetime.now)
    last_failure: Optional[datetime] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    downtime_history: List[Dict] = field(default_factory=list)
    health_score: float = 100.0  # 0-100
    check_count: int = 0
    error_messages: List[str] = field(default_factory=list)


@dataclass
class HealthCheckConfig:
    """健康检查配置"""
    check_interval: int = 30  # 秒
    timeout: int = 10  # 秒
    max_consecutive_failures: int = 3
    max_recovery_attempts: int = 3
    enable_auto_recovery: bool = True
    enable_failover: bool = True
    degraded_threshold: float = 50.0  # 健康分数低于此值视为降级
    unhealthy_threshold: float = 25.0  # 健康分数低于此值视为不健康
    dead_threshold: float = 3  # 连续失败次数超过此值视为死亡


@dataclass
class RecoveryResult:
    """恢复结果"""
    success: bool
    action: RecoveryAction
    message: str
    duration: float = 0.0


class HealthChecker:
    """健康检查器"""
    
    def __init__(self, config: HealthCheckConfig = None):
        self.config = config or HealthCheckConfig()
        self.agents: Dict[str, AgentHealth] = {}
        self.check_callbacks: Dict[str, Callable] = {}  # agent_id -> check function
        self.recovery_callbacks: Dict[str, Callable] = {}  # agent_id -> recovery function
        self.failover_callback: Optional[Callable] = None
        self.alert_callback: Optional[Callable] = None
        self.lock = threading.RLock()
        self.check_queue = queue.Queue()
        self.running = False
        self.check_thread: Optional[threading.Thread] = None
        
    def register_agent(self, agent_id: str, 
                       check_callback: Optional[Callable] = None,
                       recovery_callback: Optional[Callable] = None) -> None:
        """注册Agent进行健康检查"""
        with self.lock:
            if agent_id not in self.agents:
                self.agents[agent_id] = AgentHealth(agent_id=agent_id)
            if check_callback:
                self.check_callbacks[agent_id] = check_callback
            if recovery_callback:
                self.recovery_callbacks[agent_id] = recovery_callback
            logger.info(f"注册Agent进行健康检查: {agent_id}")
            
    def unregister_agent(self, agent_id: str) -> None:
        """注销Agent"""
        with self.lock:
            self.agents.pop(agent_id, None)
            self.check_callbacks.pop(agent_id, None)
            self.recovery_callbacks.pop(agent_id, None)
            logger.info(f"注销Agent: {agent_id}")
            
    def set_failover_callback(self, callback: Callable) -> None:
        """设置故障转移回调"""
        self.failover_callback = callback
        
    def set_alert_callback(self, callback: Callable) -> None:
        """设置告警回调"""
        self.alert_callback = callback
        
    def report_health(self, agent_id: str, is_healthy: bool, 
                      metrics: Dict = None, error: str = None) -> None:
        """报告Agent健康状态"""
        with self.lock:
            if agent_id not in self.agents:
                self.register_agent(agent_id)
                
            health = self.agents[agent_id]
            health.last_check = datetime.now()
            health.check_count += 1
            
            if is_healthy:
                health.consecutive_failures = 0
                health.last_success = datetime.now()
                health.status = self._calculate_status(health)
                if error:
                    health.error_messages.append(f"[{datetime.now().isoformat()}] 恢复: {error}")
            else:
                health.consecutive_failures += 1
                health.total_failures += 1
                health.last_failure = datetime.now()
                if error:
                    health.error_messages.append(f"[{datetime.now().isoformat()}] 失败: {error}")
                    
            # 计算健康分数
            self._update_health_score(health)
            
            # 检查是否需要恢复
            if (self.config.enable_auto_recovery and 
                health.consecutive_failures >= self.config.max_consecutive_failures and
                health.recovery_attempts < health.max_recovery_attempts):
                self._trigger_recovery(agent_id)
                
            # 检查是否需要告警
            self._check_alert(health)
            
    def _calculate_status(self, health: AgentHealth) -> HealthStatus:
        """计算健康状态"""
        if health.consecutive_failures >= self.config.dead_threshold:
            return HealthStatus.DEAD
        elif health.consecutive_failures >= self.config.max_consecutive_failures:
            return HealthStatus.UNHEALTHY
        elif health.health_score < self.config.unhealthy_threshold:
            return HealthStatus.UNHEALTHY
        elif health.health_score < self.config.degraded_threshold:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
        
    def _update_health_score(self, health: AgentHealth) -> None:
        """更新健康分数"""
        base_score = 100.0
        
        # 连续失败扣分
        failure_penalty = health.consecutive_failures * 15
        
        # 总失败扣分 (最多扣30分)
        total_failure_penalty = min(health.total_failures * 2, 30)
        
        # 未恢复时间奖励 (如果最近成功过)
        if health.last_success:
            time_since_success = (datetime.now() - health.last_success).total_seconds()
            if time_since_success < 3600:  # 1小时内
                time_bonus = 10 * (1 - time_since_success / 3600)
            else:
                time_bonus = 0
        else:
            time_bonus = 0
            
        health.health_score = max(0, min(100, 
            base_score - failure_penalty - total_failure_penalty + time_bonus))
            
    def _trigger_recovery(self, agent_id: str) -> None:
        """触发恢复"""
        health = self.agents[agent_id]
        health.recovery_attempts += 1
        
        logger.warning(f"触发Agent恢复: {agent_id}, 尝试 {health.recovery_attempts}/{health.max_recovery_attempts}")
        
        if agent_id in self.recovery_callbacks:
            try:
                callback = self.recovery_callbacks[agent_id]
                result = callback(agent_id)
                if result:
                    logger.info(f"Agent恢复成功: {agent_id}")
                    health.consecutive_failures = 0
                else:
                    logger.warning(f"Agent恢复失败: {agent_id}")
            except Exception as e:
                logger.error(f"恢复回调异常: {agent_id}, {e}")
        else:
            # 默认恢复: 重置状态
            logger.info(f"执行默认恢复: {agent_id}")
            health.consecutive_failures = 0
            
    def _check_alert(self, health: AgentHealth) -> None:
        """检查是否需要告警"""
        if self.alert_callback and health.status in [HealthStatus.UNHEALTHY, HealthStatus.DEAD]:
            try:
                self.alert_callback(health)
            except Exception as e:
                logger.error(f"告警回调异常: {e}")
                
    def get_health_status(self, agent_id: str) -> Optional[AgentHealth]:
        """获取Agent健康状态"""
        with self.lock:
            return self.agents.get(agent_id)
            
    def get_all_health(self) -> Dict[str, AgentHealth]:
        """获取所有Agent健康状态"""
        with self.lock:
            return dict(self.agents)
            
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            stats = {
                "total_agents": len(self.agents),
                "healthy": 0,
                "degraded": 0,
                "unhealthy": 0,
                "dead": 0,
                "unknown": 0,
                "total_failures": 0,
                "avg_health_score": 0.0
            }
            
            scores = []
            for health in self.agents.values():
                stats[f"{health.status.value}"] = stats.get(f"{health.status.value}", 0) + 1
                stats["total_failures"] += health.total_failures
                scores.append(health.health_score)
                
            if scores:
                stats["avg_health_score"] = sum(scores) / len(scores)
                
            return stats
            
    def trigger_failover(self, failed_agent_id: str, pending_tasks: List = None) -> bool:
        """触发故障转移"""
        if not self.config.enable_failover:
            return False
            
        logger.warning(f"触发故障转移: {failed_agent_id}")
        
        if self.failover_callback:
            try:
                return self.failover_callback(failed_agent_id, pending_tasks)
            except Exception as e:
                logger.error(f"故障转移回调异常: {e}")
                return False
        return False
        
    def start_auto_check(self) -> None:
        """启动自动健康检查"""
        if self.running:
            return
            
        self.running = True
        self.check_thread = threading.Thread(target=self._check_loop, daemon=True)
        self.check_thread.start()
        logger.info("启动自动健康检查")
        
    def stop_auto_check(self) -> None:
        """停止自动健康检查"""
        self.running = False
        if self.check_thread:
            self.check_thread.join(timeout=5)
        logger.info("停止自动健康检查")
        
    def _check_loop(self) -> None:
        """检查循环"""
        while self.running:
            try:
                self._perform_health_check()
            except Exception as e:
                logger.error(f"健康检查循环异常: {e}")
            time.sleep(self.config.check_interval)
            
    def _perform_health_check(self) -> None:
        """执行健康检查"""
        with self.lock:
            agents_to_check = list(self.agents.keys())
            
        for agent_id in agents_to_check:
            if agent_id in self.check_callbacks:
                try:
                    callback = self.check_callbacks[agent_id]
                    result = callback(agent_id)
                    if isinstance(result, dict):
                        self.report_health(agent_id, 
                                         result.get('healthy', False),
                                         result.get('metrics', {}),
                                         result.get('error'))
                    else:
                        self.report_health(agent_id, result)
                except Exception as e:
                    self.report_health(agent_id, False, error=str(e))
                    
    def export_status(self) -> Dict:
        """导出状态JSON"""
        with self.lock:
            return {
                "timestamp": datetime.now().isoformat(),
                "stats": self.get_stats(),
                "agents": {
                    agent_id: {
                        "status": h.status.value,
                        "health_score": h.health_score,
                        "consecutive_failures": h.consecutive_failures,
                        "total_failures": h.total_failures,
                        "last_check": h.last_check.isoformat(),
                        "last_success": h.last_success.isoformat() if h.last_success else None,
                        "recovery_attempts": h.recovery_attempts
                    }
                    for agent_id, h in self.agents.items()
                }
            }


class AutoRecoveryManager:
    """自动恢复管理器"""
    
    def __init__(self, health_checker: HealthChecker):
        self.health_checker = health_checker
        self.recovery_history: List[Dict] = []
        self.recovery_policies: Dict[str, Dict] = {}
        self.lock = threading.RLock()
        
    def register_recovery_policy(self, agent_id: str, policy: Dict) -> None:
        """注册恢复策略"""
        with self.lock:
            self.recovery_policies[agent_id] = policy
            
    def execute_recovery(self, agent_id: str, action: RecoveryAction) -> RecoveryResult:
        """执行恢复操作"""
        start_time = time.time()
        
        logger.info(f"执行恢复操作: {agent_id} -> {action.value}")
        
        # 模拟恢复操作
        success = random.random() > 0.3  # 70%成功率
        
        result = RecoveryResult(
            success=success,
            action=action,
            message=f"{action.value} {'成功' if success else '失败'}",
            duration=time.time() - start_time
        )
        
        # 记录历史
        with self.lock:
            self.recovery_history.append({
                "agent_id": agent_id,
                "action": action.value,
                "success": success,
                "timestamp": datetime.now().isoformat(),
                "duration": result.duration
            })
            
        return result
        
    def get_recovery_stats(self) -> Dict:
        """获取恢复统计"""
        with self.lock:
            if not self.recovery_history:
                return {"total": 0, "success_rate": 0}
                
            total = len(self.recovery_history)
            success = sum(1 for r in self.recovery_history if r['success'])
            return {
                "total": total,
                "success": success,
                "failed": total - success,
                "success_rate": success / total if total > 0 else 0
            }


class HealthMonitorCLI:
    """健康监控CLI工具"""
    
    def __init__(self):
        self.health_checker = HealthChecker()
        self.recovery_manager = AutoRecoveryManager(self.health_checker)
        
    def register_agent(self, agent_id: str) -> None:
        """注册Agent"""
        # 模拟检查回调
        def mock_check(agent_id: str) -> Dict:
            return {
                "healthy": random.random() > 0.2,
                "metrics": {
                    "cpu": random.uniform(10, 80),
                    "memory": random.uniform(20, 70),
                    "response_time": random.uniform(0.1, 2.0)
                }
            }
            
        # 模拟恢复回调
        def mock_recover(agent_id: str) -> bool:
            return random.random() > 0.3
            
        self.health_checker.register_agent(
            agent_id, 
            check_callback=mock_check,
            recovery_callback=mock_recover
        )
        
    def run_check(self, agent_id: str) -> None:
        """手动运行检查"""
        if agent_id in self.health_checker.check_callbacks:
            callback = self.health_checker.check_callbacks[agent_id]
            result = callback(agent_id)
            self.health_checker.report_health(
                agent_id,
                result.get('healthy', False),
                result.get('metrics', {}),
                result.get('error')
            )
            
    def get_status(self, agent_id: str = None) -> Dict:
        """获取状态"""
        if agent_id:
            return self.health_checker.export_status()
        return self.health_checker.get_stats()
        
    def list_agents(self) -> List[str]:
        """列出所有Agent"""
        return list(self.health_checker.agents.keys())


def demo():
    """演示"""
    print("=" * 60)
    print("Agent健康检查与自动恢复系统演示")
    print("=" * 60)
    
    cli = HealthMonitorCLI()
    
    # 注册Agents
    agents = ["agent-001", "agent-002", "agent-003", "agent-004", "agent-005"]
    for agent_id in agents:
        cli.register_agent(agent_id)
    print(f"\n✓ 注册 {len(agents)} 个Agents")
    
    # 模拟运行多轮健康检查
    print("\n--- 健康检查循环 ---")
    for round_num in range(1, 6):
        print(f"\n第 {round_num} 轮检查:")
        
        for agent_id in agents:
            # 模拟不同Agent的不同健康状况
            if agent_id == "agent-003":
                # agent-003 偶尔失败
                is_healthy = random.random() > 0.3
            elif agent_id == "agent-004":
                # agent-004 经常失败
                is_healthy = random.random() > 0.7
            else:
                is_healthy = random.random() > 0.1
                
            cli.health_checker.report_health(
                agent_id,
                is_healthy,
                metrics={
                    "cpu": random.uniform(10, 80),
                    "memory": random.uniform(20, 70)
                }
            )
            
        # 显示状态
        stats = cli.get_status()
        print(f"  健康: {stats.get('healthy', 0)}, "
              f"降级: {stats.get('degraded', 0)}, "
              f"不健康: {stats.get('unhealthy', 0)}, "
              f"平均分数: {stats.get('avg_health_score', 0):.1f}")
        
        time.sleep(0.5)
        
    # 显示详细状态
    print("\n--- Agent详细状态 ---")
    status = cli.get_status()
    if 'agents' in status:
        for agent_id, info in status['agents'].items():
            print(f"  {agent_id}: {info['status']} (分数: {info['health_score']:.1f})")
    
    # 显示恢复统计
    print("\n--- 恢复统计 ---")
    recovery_stats = cli.recovery_manager.get_recovery_stats()
    print(f"  总恢复次数: {recovery_stats['total']}")
    print(f"  成功率: {recovery_stats.get('success_rate', 0)*100:.1f}%")
    
    # 导出JSON
    print("\n--- 导出状态JSON ---")
    export = cli.health_checker.export_status()
    print(json.dumps(export, indent=2, ensure_ascii=False))
    
    print("\n✓ 演示完成")
    return True


if __name__ == "__main__":
    demo()