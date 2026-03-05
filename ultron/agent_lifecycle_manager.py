#!/usr/bin/env python3
"""
Agent协作网络 - 健康检查集成模块
将健康检查与调度系统集成，实现完整的生命周期管理
"""

import json
import time
import random
import logging
from datetime import datetime
from typing import Dict, List
from agent_health_monitor import HealthChecker, HealthCheckConfig, HealthStatus, HealthMonitorCLI
from agent_scheduler import LoadBalancer, TaskScheduler, Task

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AgentLifecycleManager:
    """Agent生命周期管理器 - 整合健康检查与调度"""
    
    def __init__(self):
        self.health_checker = HealthChecker()
        self.load_balancer = LoadBalancer(strategy="smart")
        self.scheduler = TaskScheduler(self.load_balancer)
        
        # 配置
        self.config = {
            "enable_auto_recovery": True,
            "enable_failover": True,
            "check_interval": 30,
            "max_consecutive_failures": 3
        }
        
        # 设置回调
        self.health_checker.set_failover_callback(self._failover_handler)
        self.health_checker.set_alert_callback(self._alert_handler)
        
        # 统计数据
        self.stats = {
            "total_checks": 0,
            "total_failovers": 0,
            "total_recoveries": 0,
            "agents_registered": 0
        }
        
    def register_agent(self, agent_id: str, capability: str = None) -> None:
        """注册Agent (同时注册到健康检查和调度)"""
        # 注册到健康检查
        def health_check(agent_id: str) -> Dict:
            # 模拟健康检查 (实际应该检查真实Agent)
            is_healthy = random.random() > 0.15
            return {
                "healthy": is_healthy,
                "metrics": {
                    "cpu": random.uniform(10, 70),
                    "memory": random.uniform(20, 60),
                    "queue_size": random.randint(0, 5),
                    "success_rate": random.uniform(0.8, 1.0),
                    "response_time": random.uniform(0.1, 1.5)
                }
            }
            
        def recovery(agent_id: str) -> bool:
            logger.info(f"执行Agent恢复: {agent_id}")
            return random.random() > 0.3
            
        self.health_checker.register_agent(agent_id, health_check, recovery)
        
        # 注册到负载均衡器
        self.load_balancer.register_agent(agent_id)
            
        self.stats["agents_registered"] += 1
        logger.info(f"注册Agent: {agent_id}")
        
    def _failover_handler(self, failed_agent_id: str, pending_tasks: List = None) -> bool:
        """故障转移处理"""
        logger.warning(f"故障转移: {failed_agent_id}")
        self.stats["total_failovers"] += 1
        
        # 将任务转移到其他健康Agent
        healthy_agents = [
            aid for aid, h in self.health_checker.get_all_health().items()
            if h.status == HealthStatus.HEALTHY and aid != failed_agent_id
        ]
        
        if healthy_agents:
            target_agent = random.choice(healthy_agents)
            logger.info(f"任务转移到: {target_agent}")
            return True
        return False
        
    def _alert_handler(self, health) -> None:
        """告警处理"""
        logger.warning(f"告警: {health.agent_id} 状态 {health.status.value}")
        
    def check_agent(self, agent_id: str) -> Dict:
        """检查单个Agent"""
        self.stats["total_checks"] += 1
        
        if agent_id in self.health_checker.check_callbacks:
            callback = self.health_checker.check_callbacks[agent_id]
            result = callback(agent_id)
            self.health_checker.report_health(
                agent_id,
                result.get('healthy', False),
                result.get('metrics', {}),
                result.get('error')
            )
            
        return self.health_checker.get_health_status(agent_id)
        
    def check_all_agents(self) -> Dict:
        """检查所有Agent"""
        for agent_id in list(self.health_checker.agents.keys()):
            self.check_agent(agent_id)
            
        return self.health_checker.get_stats()
        
    def get_agent_info(self, agent_id: str = None) -> Dict:
        """获取Agent信息"""
        if agent_id:
            health = self.health_checker.get_health_status(agent_id)
            if health:
                return {
                    "agent_id": health.agent_id,
                    "status": health.status.value,
                    "health_score": health.health_score,
                    "consecutive_failures": health.consecutive_failures,
                    "total_failures": health.total_failures,
                    "last_check": health.last_check.isoformat(),
                    "recovery_attempts": health.recovery_attempts
                }
            return {}
        else:
            return self.health_checker.export_status()
            
    def submit_task(self, task: Task) -> str:
        """提交任务 (自动选择健康Agent)"""
        # 获取健康Agent
        healthy_agents = [
            aid for aid, h in self.health_checker.get_all_health().items()
            if h.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        ]
        
        if not healthy_agents:
            logger.error("无健康Agent可执行任务")
            return None
            
        # 使用负载均衡选择 - 随机选择
        target_agent = random.choice(healthy_agents)
        logger.info(f"任务 {task.task_id} 分配给 {target_agent}")
            
        return target_agent
        
    def get_stats(self) -> Dict:
        """获取统计"""
        health_stats = self.health_checker.get_stats()
        return {
            **self.stats,
            **health_stats
        }


def demo():
    """演示"""
    print("=" * 60)
    print("Agent生命周期管理 - 健康检查集成演示")
    print("=" * 60)
    
    manager = AgentLifecycleManager()
    
    # 注册Agents
    agents = [
        "agent-001",
        "agent-002", 
        "agent-003",
        "agent-004",
        "agent-005"
    ]
    
    for agent_id in agents:
        manager.register_agent(agent_id)
        
    print(f"\n✓ 已注册 {len(agents)} 个Agents")
    
    # 模拟健康检查循环
    print("\n--- 健康检查循环 ---")
    for round_num in range(1, 6):
        stats = manager.check_all_agents()
        print(f"第{round_num}轮: 健康{stats.get('healthy',0)}, 降级{stats.get('degraded',0)}, "
              f"不健康{stats.get('unhealthy',0)}, 平均分数{stats.get('avg_health_score',0):.1f}")
        time.sleep(0.3)
        
    # 显示详细状态
    print("\n--- Agent状态 ---")
    status = manager.get_agent_info()
    for agent_id, info in status.get('agents', {}).items():
        print(f"  {agent_id}: {info['status']} (分数: {info['health_score']:.1f}, "
              f"失败: {info['total_failures']})")
    
    # 模拟任务提交
    print("\n--- 任务分发测试 ---")
    for i in range(3):
        task = Task(
            task_id=f"task-{i+1}",
            task_type="code",
            priority=random.randint(1, 10)
        )
        target = manager.submit_task(task)
        print(f"  任务 {task.task_id} -> {target}")
        
    # 统计
    print("\n--- 统计 ---")
    stats = manager.get_stats()
    print(f"  总检查次数: {stats['total_checks']}")
    print(f"  故障转移: {stats['total_failovers']}")
    print(f"  Agents注册: {stats['agents_registered']}")
    
    print("\n✓ 演示完成")
    return True


if __name__ == "__main__":
    demo()