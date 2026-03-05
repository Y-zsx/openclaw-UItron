#!/usr/bin/env python3
"""
Agent协作网络 - 增强型生命周期管理器
支持自动恢复、故障转移、状态持久化
"""

import json
import time
import random
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from pathlib import Path
from enum import Enum
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 状态文件
LIFECYCLE_STATE_FILE = "/root/.openclaw/workspace/ultron/data/agent_lifecycle_state.json"


class AgentState(Enum):
    """Agent状态"""
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    STOPPED = "stopped"
    FAILED = "failed"


class LifecycleConfig:
    """生命周期配置"""
    def __init__(self):
        self.enable_auto_recovery = True
        self.enable_failover = True
        self.check_interval = 30  # 秒
        self.max_consecutive_failures = 3
        self.recovery_timeout = 60  # 秒
        self.health_threshold = 70.0
        self.degraded_threshold = 50.0
        self.state_file = LIFECYCLE_STATE_FILE


class AgentLifecycle:
    """单个Agent的生命周期状态"""
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.state = AgentState.STARTING
        self.health_score = 100.0
        self.start_time = time.time()
        self.last_check = time.time()
        self.consecutive_failures = 0
        self.total_failures = 0
        self.recovery_attempts = 0
        self.restart_count = 0
        self.last_error = None
        self.metadata = {}
        
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "health_score": self.health_score,
            "start_time": self.start_time,
            "last_check": self.last_check,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "recovery_attempts": self.recovery_attempts,
            "restart_count": self.restart_count,
            "last_error": self.last_error,
            "uptime": str(timedelta(seconds=int(time.time() - self.start_time))),
            "metadata": self.metadata
        }


class EnhancedLifecycleManager:
    """增强型生命周期管理器"""
    
    def __init__(self, config: LifecycleConfig = None):
        self.config = config or LifecycleConfig()
        self.agents: Dict[str, AgentLifecycle] = {}
        self.health_check_callbacks: Dict[str, Callable] = {}
        self.recovery_callbacks: Dict[str, Callable] = {}
        self.failover_callbacks: List[Callable] = []
        self.alert_callbacks: List[Callable] = []
        
        # 统计
        self.stats = {
            "total_checks": 0,
            "total_failovers": 0,
            "total_recoveries": 0,
            "total_restarts": 0,
            "agents_registered": 0
        }
        
        # 状态持久化
        self._ensure_state_dir()
        self._load_state()
        
        # 线程安全
        self._lock = threading.Lock()
        
    def _ensure_state_dir(self):
        """确保状态目录存在"""
        Path(LIFECYCLE_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
        
    def _load_state(self):
        """加载状态"""
        if os.path.exists(LIFECYCLE_STATE_FILE):
            try:
                with open(LIFECYCLE_STATE_FILE) as f:
                    data = json.load(f)
                    for agent_id, info in data.get("agents", {}).items():
                        lifecycle = AgentLifecycle(agent_id)
                        lifecycle.state = AgentState(info.get("state", "running"))
                        lifecycle.health_score = info.get("health_score", 100.0)
                        lifecycle.total_failures = info.get("total_failures", 0)
                        lifecycle.restart_count = info.get("restart_count", 0)
                        self.agents[agent_id] = lifecycle
                logger.info(f"加载了 {len(self.agents)} 个Agent状态")
            except Exception as e:
                logger.error(f"加载状态失败: {e}")
                
    def _save_state(self):
        """保存状态"""
        try:
            data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "agents": {
                    agent_id: lc.to_dict() 
                    for agent_id, lc in self.agents.items()
                },
                "stats": self.stats
            }
            with open(LIFECYCLE_STATE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
            
    def register_agent(self, agent_id: str, 
                       health_check: Callable = None, 
                       recovery: Callable = None,
                       metadata: dict = None) -> None:
        """注册Agent"""
        with self._lock:
            if agent_id in self.agents:
                logger.info(f"Agent {agent_id} 已存在，更新")
            else:
                self.agents[agent_id] = AgentLifecycle(agent_id)
                self.stats["agents_registered"] += 1
                logger.info(f"注册Agent: {agent_id}")
                
            if metadata:
                self.agents[agent_id].metadata.update(metadata)
                
        if health_check:
            self.health_check_callbacks[agent_id] = health_check
        if recovery:
            self.recovery_callbacks[agent_id] = recovery
            
        self._save_state()
        
    def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        with self._lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                self.health_check_callbacks.pop(agent_id, None)
                self.recovery_callbacks.pop(agent_id, None)
                self._save_state()
                logger.info(f"注销Agent: {agent_id}")
                return True
        return False
        
    def set_health_check(self, agent_id: str, callback: Callable):
        """设置健康检查回调"""
        self.health_check_callbacks[agent_id] = callback
        
    def set_recovery(self, agent_id: str, callback: Callable):
        """设置恢复回调"""
        self.recovery_callbacks[agent_id] = callback
        
    def add_failover_handler(self, callback: Callable):
        """添加故障转移处理器"""
        self.failover_callbacks.append(callback)
        
    def add_alert_handler(self, callback: Callable):
        """添加告警处理器"""
        self.alert_callbacks.append(callback)
        
    def check_agent(self, agent_id: str, force: bool = False) -> Optional[AgentLifecycle]:
        """检查单个Agent"""
        if agent_id not in self.agents:
            return None
            
        lifecycle = self.agents[agent_id]
        
        # 检查是否需要跳过 (检查间隔)
        if not force and (time.time() - lifecycle.last_check) < self.config.check_interval:
            return lifecycle
            
        lifecycle.last_check = time.time()
        self.stats["total_checks"] += 1
        
        # 执行健康检查回调
        health_result = {"healthy": True, "metrics": {}, "error": None}
        if agent_id in self.health_check_callbacks:
            try:
                health_result = self.health_check_callbacks[agent_id](agent_id)
            except Exception as e:
                health_result = {"healthy": False, "error": str(e)}
                
        # 更新状态
        is_healthy = health_result.get("healthy", False)
        metrics = health_result.get("metrics", {})
        
        if is_healthy:
            lifecycle.consecutive_failures = 0
            # 根据指标计算健康分数
            if metrics:
                health_score = 100.0
                if "cpu" in metrics:
                    health_score -= min(metrics["cpu"] / 10, 30)
                if "memory" in metrics:
                    health_score -= min(metrics["memory"] / 10, 30)
                if "response_time" in metrics:
                    health_score -= min(metrics["response_time"] * 10, 20)
                lifecycle.health_score = max(health_score, 50.0)
                
            if lifecycle.state == AgentState.UNHEALTHY:
                lifecycle.state = AgentState.RECOVERING
                self._trigger_recovery(agent_id)
            elif lifecycle.health_score < self.config.degraded_threshold:
                lifecycle.state = AgentState.DEGRADED
            else:
                lifecycle.state = AgentState.RUNNING
        else:
            lifecycle.consecutive_failures += 1
            lifecycle.total_failures += 1
            lifecycle.last_error = health_result.get("error")
            
            if lifecycle.consecutive_failures >= self.config.max_consecutive_failures:
                lifecycle.state = AgentState.UNHEALTHY
                self._trigger_alert(agent_id, lifecycle)
                
                if self.config.enable_failover:
                    self._trigger_failover(agent_id)
                    
        self._save_state()
        return lifecycle
        
    def check_all_agents(self, force: bool = False) -> Dict:
        """检查所有Agent"""
        for agent_id in list(self.agents.keys()):
            self.check_agent(agent_id, force)
            
        return self.get_stats()
        
    def _trigger_recovery(self, agent_id: str):
        """触发恢复"""
        lifecycle = self.agents[agent_id]
        lifecycle.recovery_attempts += 1
        self.stats["total_recoveries"] += 1
        
        logger.info(f"触发恢复: {agent_id} (尝试 {lifecycle.recovery_attempts})")
        
        # 执行恢复回调
        if agent_id in self.recovery_callbacks:
            try:
                success = self.recovery_callbacks[agent_id](agent_id)
                if success:
                    lifecycle.state = AgentState.RUNNING
                    lifecycle.health_score = 80.0
                    logger.info(f"恢复成功: {agent_id}")
                else:
                    lifecycle.state = AgentState.FAILED
                    logger.warning(f"恢复失败: {agent_id}")
            except Exception as e:
                logger.error(f"恢复异常: {agent_id} - {e}")
                lifecycle.last_error = str(e)
                
        self._save_state()
        
    def _trigger_failover(self, agent_id: str):
        """触发故障转移"""
        self.stats["total_failovers"] += 1
        logger.warning(f"触发故障转移: {agent_id}")
        
        for callback in self.failover_callbacks:
            try:
                callback(agent_id)
            except Exception as e:
                logger.error(f"故障转移处理异常: {e}")
                
    def _trigger_alert(self, agent_id: str, lifecycle: AgentLifecycle):
        """触发告警"""
        for callback in self.alert_callbacks:
            try:
                callback(agent_id, lifecycle)
            except Exception as e:
                logger.error(f"告警处理异常: {e}")
                
    def auto_recovery_check(self) -> Dict:
        """自动恢复检查 - 定时任务调用"""
        result = {
            "checked": 0,
            "recovered": [],
            "failed": [],
            "failovers": []
        }
        
        for agent_id, lifecycle in self.agents.items():
            if lifecycle.state in [AgentState.UNHEALTHY, AgentState.FAILED]:
                result["checked"] += 1
                
                if self.config.enable_auto_recovery:
                    # 尝试自动恢复
                    self._trigger_recovery(agent_id)
                    
                    if lifecycle.state == AgentState.RUNNING:
                        result["recovered"].append(agent_id)
                    else:
                        result["failed"].append(agent_id)
                        
                    # 如果恢复失败，标记为需要故障转移
                    if lifecycle.state == AgentState.FAILED:
                        result["failovers"].append(agent_id)
                        if self.config.enable_failover:
                            self._trigger_failover(agent_id)
                            
        self._save_state()
        return result
        
    def get_agent_status(self, agent_id: str = None) -> Dict:
        """获取Agent状态"""
        if agent_id:
            if agent_id in self.agents:
                return self.agents[agent_id].to_dict()
            return {}
        
        return {
            "agents": {
                aid: lc.to_dict() 
                for aid, lc in self.agents.items()
            },
            "stats": self.stats,
            "config": {
                "check_interval": self.config.check_interval,
                "max_consecutive_failures": self.config.max_consecutive_failures,
                "enable_auto_recovery": self.config.enable_auto_recovery,
                "enable_failover": self.config.enable_failover
            }
        }
        
    def get_stats(self) -> Dict:
        """获取统计"""
        healthy = sum(1 for lc in self.agents.values() if lc.state == AgentState.RUNNING)
        degraded = sum(1 for lc in self.agents.values() if lc.state == AgentState.DEGRADED)
        unhealthy = sum(1 for lc in self.agents.values() if lc.state == AgentState.UNHEALTHY)
        
        avg_score = 0
        if self.agents:
            avg_score = sum(lc.health_score for lc in self.agents.values()) / len(self.agents)
            
        return {
            "total_agents": len(self.agents),
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "avg_health_score": avg_score,
            **self.stats
        }
        
    def restart_agent(self, agent_id: str) -> bool:
        """重启Agent"""
        if agent_id not in self.agents:
            return False
            
        lifecycle = self.agents[agent_id]
        lifecycle.restart_count += 1
        lifecycle.state = AgentState.STARTING
        lifecycle.consecutive_failures = 0
        lifecycle.health_score = 100.0
        lifecycle.start_time = time.time()
        
        self.stats["total_restarts"] += 1
        self._save_state()
        
        logger.info(f"重启Agent: {agent_id} (第{lifecycle.restart_count}次)")
        return True
        
    def start_agent(self, agent_id: str, metadata: dict = None) -> bool:
        """启动Agent"""
        if agent_id in self.agents:
            if self.agents[agent_id].state == AgentState.STOPPED:
                self.agents[agent_id].state = AgentState.STARTING
                self._save_state()
                return True
            return False
            
        self.register_agent(agent_id, metadata=metadata)
        return True
        
    def stop_agent(self, agent_id: str) -> bool:
        """停止Agent"""
        if agent_id in self.agents:
            self.agents[agent_id].state = AgentState.STOPPED
            self._save_state()
            logger.info(f"停止Agent: {agent_id}")
            return True
        return False


# 兼容旧API
class AgentLifecycleManager(EnhancedLifecycleManager):
    """兼容旧版本的类名"""
    
    def get_agent_info(self, agent_id: str = None) -> Dict:
        """兼容旧API - 获取Agent信息"""
        return self.get_agent_status(agent_id)
        
    def get_all_health(self) -> Dict:
        """兼容旧API"""
        return {
            agent_id: type('obj', (object,), {'status': lc.state.value, 'health_score': lc.health_score})()
            for agent_id, lc in self.agents.items()
        }


def demo():
    """演示"""
    print("=" * 60)
    print("增强型Agent生命周期管理 - 自动恢复演示")
    print("=" * 60)
    
    manager = EnhancedLifecycleManager()
    
    # 定义健康检查和恢复回调
    def health_check(agent_id: str) -> Dict:
        """模拟健康检查"""
        is_healthy = random.random() > 0.2
        return {
            "healthy": is_healthy,
            "metrics": {
                "cpu": random.uniform(10, 80),
                "memory": random.uniform(20, 70),
                "response_time": random.uniform(0.1, 2.0)
            }
        }
        
    def recovery(agent_id: str) -> bool:
        """模拟恢复"""
        logger.info(f"执行恢复: {agent_id}")
        return random.random() > 0.3
        
    # 注册Agents
    agents = ["agent-001", "agent-002", "agent-003", "agent-004", "agent-005"]
    for agent_id in agents:
        manager.register_agent(agent_id, health_check, recovery)
        
    print(f"\n✓ 已注册 {len(agents)} 个Agents")
    
    # 健康检查循环
    print("\n--- 健康检查循环 ---")
    for round_num in range(1, 6):
        stats = manager.check_all_agents(force=True)
        print(f"轮{round_num}: 健康{stats['healthy']}, 降级{stats['degraded']}, "
              f"不健康{stats['unhealthy']}, 平均分{stats['avg_health_score']:.1f}")
        time.sleep(0.3)
        
    # 自动恢复检查
    print("\n--- 自动恢复检查 ---")
    recovery_result = manager.auto_recovery_check()
    print(f"检查: {recovery_result['checked']}, 恢复: {len(recovery_result['recovered'])}, "
          f"失败: {len(recovery_result['failed'])}")
    
    # 显示状态
    print("\n--- Agent状态 ---")
    status = manager.get_agent_status()
    for agent_id, info in status["agents"].items():
        print(f"  {agent_id}: {info['state']} (分数:{info['health_score']:.1f}, 失败:{info['total_failures']})")
    
    # 统计
    print("\n--- 统计 ---")
    stats = manager.get_stats()
    print(f"  总检查: {stats['total_checks']}")
    print(f"  故障转移: {stats['total_failovers']}")
    print(f"  恢复次数: {stats['total_recoveries']}")
    print(f"  重启次数: {stats['total_restarts']}")
    
    print("\n✓ 演示完成")
    return True


if __name__ == "__main__":
    demo()