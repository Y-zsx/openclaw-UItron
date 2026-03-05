#!/usr/bin/env python3
"""
全智能系统协同平台 - 第2世：智能协作
Multi-Component Collaboration System
多组件协同工作：动态协作、自适应负载、跨域协调

功能：
1. 动态协作引擎 - 实时调整协作策略
2. 自适应负载均衡 - 根据系统状态动态分配
3. 跨域协调机制 - 跨系统任务协同
4. 协作状态管理 - 实时状态同步与恢复
"""

import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import threading
import random
import hashlib

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CollaborationMode(Enum):
    """协作模式"""
    SEQUENTIAL = "sequential"      # 顺序执行
    PARALLEL = "parallel"          # 并行执行
    PIPELINE = "pipeline"          # 管道模式
    HIERARCHICAL = "hierarchical"  # 层级模式
    ADAPTIVE = "adaptive"          # 自适应模式
    FEDERATED = "federated"        # 联邦模式


class ComponentState(Enum):
    """组件状态"""
    IDLE = "idle"
    ACTIVE = "active"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    RECOVERING = "recovering"


class TaskType(Enum):
    """任务类型"""
    COMPUTATION = "computation"
    IO = "io"
    NETWORK = "network"
    STORAGE = "storage"
    ANALYTICS = "analytics"
    ORCHESTRATION = "orchestration"
    COORDINATION = "coordination"


@dataclass
class CollaborationMetrics:
    """协作指标"""
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_response_time: float = 0.0
    throughput: float = 0.0
    load_balance_score: float = 0.0
    collaboration_efficiency: float = 0.0
    resource_utilization: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "avg_response_time": round(self.avg_response_time, 2),
            "throughput": round(self.throughput, 2),
            "load_balance_score": round(self.load_balance_score, 2),
            "collaboration_efficiency": round(self.collaboration_efficiency, 2),
            "resource_utilization": round(self.resource_utilization, 2)
        }


@dataclass
class ComponentHealth:
    """组件健康状态"""
    component_id: str
    state: ComponentState = ComponentState.IDLE
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    response_time: float = 0.0
    error_rate: float = 0.0
    success_rate: float = 0.0
    last_check: str = field(default_factory=lambda: datetime.now().isoformat())
    consecutive_failures: int = 0
    health_score: float = 1.0  # 0-1评分
    
    def update_health(self, success: bool, response_time: float):
        """更新健康状态"""
        self.last_check = datetime.now().isoformat()
        self.response_time = response_time
        
        if success:
            self.consecutive_failures = 0
            self.success_rate = min(1.0, self.success_rate * 0.9 + 0.1)
        else:
            self.consecutive_failures += 1
            self.success_rate = max(0.0, self.success_rate * 0.9)
        
        # 计算健康评分
        self.health_score = (
            (1 - self.error_rate) * 0.3 +
            self.success_rate * 0.4 +
            (1 - self.cpu_usage) * 0.2 +
            (1 - self.memory_usage) * 0.1
        )
        
        # 根据连续失败次数降级
        if self.consecutive_failures >= 5:
            self.state = ComponentState.DEGRADED
        elif self.consecutive_failures >= 10:
            self.state = ComponentState.OFFLINE


class DynamicCollaborationEngine:
    """
    动态协作引擎
    实时分析系统状态，动态调整协作策略
    """
    
    def __init__(self):
        self.components: Dict[str, ComponentHealth] = {}
        self.active_sessions: Dict[str, Dict] = {}
        self.collaboration_history: deque = deque(maxlen=1000)
        self.mode_performance: Dict[str, List[float]] = defaultdict(list)
        
        # 策略调整参数
        self.strategy_config = {
            "load_threshold_high": 0.8,     # 高负载阈值
            "load_threshold_low": 0.2,      # 低负载阈值
            "response_time_threshold": 1.0, # 响应时间阈值(秒)
            "error_rate_threshold": 0.1,    # 错误率阈值
            "adaptation_interval": 5,       # 调整间隔(秒)
            "min_sample_size": 10           # 最小样本数
        }
        
        # 当前策略
        self.current_mode = CollaborationMode.ADAPTIVE
        self.last_adaptation = datetime.now()
        
        logger.info("🔄 动态协作引擎初始化完成")
    
    def register_component(self, component_id: str) -> bool:
        """注册组件"""
        if component_id not in self.components:
            self.components[component_id] = ComponentHealth(component_id)
            logger.info(f"✅ 组件注册到协作引擎: {component_id}")
            return True
        return False
    
    def get_optimal_mode(self) -> CollaborationMode:
        """获取最佳协作模式"""
        # 收集系统指标
        total_components = len(self.components)
        if total_components == 0:
            return CollaborationMode.ADAPTIVE
        
        # 计算平均负载
        active_count = sum(1 for c in self.components.values() 
                         if c.state == ComponentState.ACTIVE)
        avg_load = active_count / total_components
        
        # 计算平均响应时间
        response_times = [c.response_time for c in self.components.values() 
                        if c.response_time > 0]
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        
        # 计算平均错误率
        error_rates = [c.error_rate for c in self.components.values()]
        avg_error = sum(error_rates) / len(error_rates) if error_rates else 0
        
        # 基于指标选择模式
        if avg_error > self.strategy_config["error_rate_threshold"]:
            # 错误率高，使用顺序模式提高可靠性
            return CollaborationMode.SEQUENTIAL
        elif avg_load > self.strategy_config["load_threshold_high"]:
            # 高负载，使用管道模式
            return CollaborationMode.PIPELINE
        elif avg_load < self.strategy_config["load_threshold_low"]:
            # 低负载，使用并行模式
            return CollaborationMode.PARALLEL
        elif avg_response > self.strategy_config["response_time_threshold"]:
            # 响应时间长，使用联邦模式分散负载
            return CollaborationMode.FEDERATED
        else:
            # 默认使用自适应模式
            return CollaborationMode.ADAPTIVE
    
    def record_task_execution(self, component_id: str, success: bool, 
                             response_time: float, task_type: TaskType):
        """记录任务执行情况"""
        if component_id not in self.components:
            self.register_component(component_id)
        
        component = self.components[component_id]
        component.update_health(success, response_time)
        
        # 记录历史
        self.collaboration_history.append({
            "component_id": component_id,
            "success": success,
            "response_time": response_time,
            "task_type": task_type.value,
            "timestamp": datetime.now().isoformat(),
            "mode": self.current_mode.value
        })
    
    def analyze_performance(self) -> Dict:
        """分析协作性能"""
        if len(self.collaboration_history) < self.strategy_config["min_sample_size"]:
            return {"status": "insufficient_data"}
        
        # 按组件分组分析
        component_stats = defaultdict(lambda: {"success": 0, "total": 0, "times": []})
        
        for record in self.collaboration_history:
            comp_id = record["component_id"]
            component_stats[comp_id]["total"] += 1
            if record["success"]:
                component_stats[comp_id]["success"] += 1
            component_stats[comp_id]["times"].append(record["response_time"])
        
        # 计算组件性能
        performance = {}
        for comp_id, stats in component_stats.items():
            performance[comp_id] = {
                "success_rate": stats["success"] / stats["total"] if stats["total"] > 0 else 0,
                "avg_response_time": sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0,
                "task_count": stats["total"]
            }
        
        # 负载均衡评分
        if performance:
            load_scores = [p["task_count"] for p in performance.values()]
            max_load = max(load_scores) if load_scores else 1
            min_load = min(load_scores) if load_scores else 0
            load_balance = 1 - (max_load - min_load) / (max_load + 1)
        else:
            load_balance = 0
        
        return {
            "current_mode": self.current_mode.value,
            "optimal_mode": self.get_optimal_mode().value,
            "component_performance": performance,
            "load_balance_score": load_balance,
            "total_executions": len(self.collaboration_history)
        }
    
    def adapt_strategy(self) -> bool:
        """自适应策略调整"""
        now = datetime.now()
        
        # 检查是否需要调整
        time_since_last = (now - self.last_adaptation).total_seconds()
        if time_since_last < self.strategy_config["adaptation_interval"]:
            return False
        
        # 分析性能
        analysis = self.analyze_performance()
        
        if "optimal_mode" in analysis:
            new_mode = analysis["optimal_mode"]
            
            if new_mode != self.current_mode:
                old_mode = self.current_mode
                self.current_mode = new_mode
                self.last_adaptation = now
                
                logger.info(f"🔄 协作策略调整: {old_mode.value} -> {new_mode.value}")
                logger.info(f"   负载均衡评分: {analysis.get('load_balance_score', 0):.2f}")
                
                return True
        
        return False
    
    def get_component_health(self, component_id: str) -> Optional[Dict]:
        """获取组件健康状态"""
        component = self.components.get(component_id)
        if component:
            return {
                "component_id": component.component_id,
                "state": component.state.value,
                "health_score": round(component.health_score, 2),
                "success_rate": round(component.success_rate, 2),
                "avg_response_time": round(component.response_time, 2),
                "consecutive_failures": component.consecutive_failures
            }
        return None
    
    def get_all_health(self) -> Dict:
        """获取所有组件健康状态"""
        return {
            comp_id: self.get_component_health(comp_id)
            for comp_id in self.components.keys()
        }


class AdaptiveLoadBalancer:
    """
    自适应负载均衡器
    根据实时状态动态分配任务
    """
    
    def __init__(self):
        self.component_weights: Dict[str, float] = {}
        self.task_distribution: Dict[str, int] = defaultdict(int)
        self.performance_history: deque = deque(maxlen=100)
        
        # 负载计算参数
        self.load_factors = {
            "cpu": 0.3,
            "memory": 0.3,
            "response_time": 0.2,
            "error_rate": 0.2
        }
        
        logger.info("⚖️ 自适应负载均衡器初始化完成")
    
    def calculate_load(self, component: ComponentHealth) -> float:
        """计算组件负载"""
        # 归一化各因素
        cpu_factor = min(1.0, component.cpu_usage)
        memory_factor = min(1.0, component.memory_usage)
        response_factor = min(1.0, component.response_time / 5.0)  # 5秒为满负载
        error_factor = component.error_rate
        
        # 加权计算
        load = (
            cpu_factor * self.load_factors["cpu"] +
            memory_factor * self.load_factors["memory"] +
            response_factor * self.load_factors["response_time"] +
            error_factor * self.load_factors["error_rate"]
        )
        
        return min(1.0, load)
    
    def select_component(self, components: Dict[str, ComponentHealth], 
                        task_requirements: Optional[Dict] = None) -> Optional[str]:
        """选择最佳组件"""
        if not components:
            return None
        
        # 计算每个组件的可用性评分
        scores = {}
        for comp_id, comp in components.items():
            load = self.calculate_load(comp)
            
            # 基础分数：负载越低分数越高
            base_score = 1 - load
            
            # 健康评分加成
            health_bonus = comp.health_score * 0.3
            
            # 成功率加成
            success_bonus = comp.success_rate * 0.2
            
            # 综合评分
            scores[comp_id] = base_score + health_bonus + success_bonus
        
        # 选择评分最高的组件
        best_component = max(scores.items(), key=lambda x: x[1])
        
        if best_component[1] > 0:
            self.task_distribution[best_component[0]] += 1
            return best_component[0]
        
        return None
    
    def get_distribution_stats(self) -> Dict:
        """获取分配统计"""
        total = sum(self.task_distribution.values())
        if total == 0:
            return {"status": "no_data"}
        
        return {
            comp_id: {
                "count": count,
                "percentage": round(count / total * 100, 2)
            }
            for comp_id, count in self.task_distribution.items()
        }


class CrossDomainCoordinator:
    """
    跨域协调机制
    协调不同系统域之间的任务协作
    """
    
    def __init__(self):
        self.domains: Dict[str, Dict] = {}
        self.cross_domain_tasks: Dict[str, Dict] = {}
        self.domain_relations: Dict[str, Set[str]] = defaultdict(set)
        
        # 协调策略
        self.coordination_strategies = {
            "efficiency": self._coordination_efficiency,
            "reliability": self._coordination_reliability,
            "balance": self._coordination_balance
        }
        
        logger.info("🌐 跨域协调机制初始化完成")
    
    def register_domain(self, domain_id: str, domain_config: Dict) -> bool:
        """注册域"""
        self.domains[domain_id] = {
            "id": domain_id,
            "config": domain_config,
            "components": [],
            "capabilities": domain_config.get("capabilities", []),
            "status": "active"
        }
        
        # 建立域间关系
        for cap in domain_config.get("capabilities", []):
            for other_domain_id, other_domain in self.domains.items():
                if other_domain_id != domain_id:
                    if cap in other_domain.get("capabilities", []):
                        self.domain_relations[domain_id].add(other_domain_id)
                        self.domain_relations[other_domain_id].add(domain_id)
        
        logger.info(f"✅ 域注册: {domain_id}")
        return True
    
    def _coordination_efficiency(self, task: Dict, available_domains: List[str]) -> str:
        """效率优先策略"""
        # 选择处理速度最快的域
        # 简化：随机选择
        return random.choice(available_domains)
    
    def _coordination_reliability(self, task: Dict, available_domains: List[str]) -> str:
        """可靠性优先策略"""
        # 选择成功率最高的域
        # 简化：选择第一个
        return available_domains[0]
    
    def _coordination_balance(self, task: Dict, available_domains: List[str]) -> str:
        """负载均衡策略"""
        # 选择负载最低的域
        # 简化：轮询选择
        return available_domains[len(self.cross_domain_tasks) % len(available_domains)]
    
    def coordinate_task(self, task: Dict, strategy: str = "balance") -> Optional[str]:
        """协调跨域任务"""
        required_capabilities = task.get("required_capabilities", [])
        
        if not required_capabilities:
            return None
        
        # 查找具备所需能力的域
        capable_domains = []
        for domain_id, domain in self.domains.items():
            if all(cap in domain.get("capabilities", []) for cap in required_capabilities):
                capable_domains.append(domain_id)
        
        if not capable_domains:
            logger.warning(f"⚠️ 无域能满足任务需求: {required_capabilities}")
            return None
        
        # 根据策略选择域
        coord_func = self.coordination_strategies.get(strategy, self._coordination_balance)
        selected_domain = coord_func(task, capable_domains)
        
        # 记录跨域任务
        task_id = f"cross_domain_{len(self.cross_domain_tasks)}"
        self.cross_domain_tasks[task_id] = {
            "id": task_id,
            "task": task,
            "source_domain": task.get("source_domain", "unknown"),
            "target_domain": selected_domain,
            "strategy": strategy,
            "status": "coordinated",
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"🔗 跨域协调: {task.get('name', 'task')} -> {selected_domain}")
        return selected_domain
    
    def get_domain_status(self, domain_id: str) -> Optional[Dict]:
        """获取域状态"""
        domain = self.domains.get(domain_id)
        if domain:
            return {
                "id": domain["id"],
                "status": domain["status"],
                "capabilities": domain["capabilities"],
                "component_count": len(domain.get("components", []))
            }
        return None
    
    def get_all_domains(self) -> Dict:
        """获取所有域"""
        return {
            domain_id: self.get_domain_status(domain_id)
            for domain_id in self.domains.keys()
        }


class CollaborationStateManager:
    """
    协作状态管理器
    实时同步协作状态，支持故障恢复
    """
    
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.session_history: Dict[str, List[Dict]] = defaultdict(list)
        self.state_cache: Dict[str, Any] = {}
        self.checkpoints: Dict[str, Dict] = {}
        
        # 状态同步配置
        self.sync_config = {
            "sync_interval": 2,
            "checkpoint_interval": 30,
            "max_history": 100
        }
        
        logger.info("📡 协作状态管理器初始化完成")
    
    def create_session(self, session_id: str, participants: List[str], 
                      mode: CollaborationMode) -> bool:
        """创建协作会话"""
        self.sessions[session_id] = {
            "id": session_id,
            "participants": participants,
            "mode": mode.value,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "task_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "shared_state": {}
        }
        
        # 初始化会话历史
        self.session_history[session_id] = []
        
        logger.info(f"🎯 协作会话创建: {session_id} (模式: {mode.value})")
        return True
    
    def update_session_state(self, session_id: str, state: Dict) -> bool:
        """更新会话状态"""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session["last_update"] = datetime.now().isoformat()
        session["shared_state"].update(state)
        
        # 记录历史
        self.session_history[session_id].append({
            "timestamp": datetime.now().isoformat(),
            "state": state.copy()
        })
        
        # 限制历史长度
        if len(self.session_history[session_id]) > self.sync_config["max_history"]:
            self.session_history[session_id] = self.session_history[session_id][-self.sync_config["max_history"]:]
        
        return True
    
    def record_task_event(self, session_id: str, event_type: str, 
                         task_id: str, data: Optional[Dict] = None):
        """记录任务事件"""
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        
        # 更新计数
        if event_type == "task_started":
            session["task_count"] += 1
        elif event_type == "task_completed":
            session["completed_count"] += 1
        elif event_type == "task_failed":
            session["failed_count"] += 1
        
        # 记录事件
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "task_id": task_id,
            "data": data or {}
        }
        
        self.session_history[session_id].append(event)
        session["last_update"] = datetime.now().isoformat()
    
    def create_checkpoint(self, session_id: str) -> Optional[str]:
        """创建检查点"""
        if session_id not in self.sessions:
            return None
        
        checkpoint_id = f"checkpoint_{session_id}_{int(time.time())}"
        
        self.checkpoints[checkpoint_id] = {
            "id": checkpoint_id,
            "session_id": session_id,
            "session_state": self.sessions[session_id].copy(),
            "history": self.session_history[session_id][-50:],  # 最近50条
            "created_at": datetime.now().isoformat()
        }
        
        logger.info(f"💾 检查点创建: {checkpoint_id}")
        return checkpoint_id
    
    def restore_from_checkpoint(self, checkpoint_id: str) -> bool:
        """从检查点恢复"""
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            return False
        
        session_id = checkpoint["session_id"]
        
        # 恢复会话状态
        self.sessions[session_id] = checkpoint["session_state"]
        self.session_history[session_id] = checkpoint["history"]
        
        logger.info(f"🔄 从检查点恢复: {checkpoint_id}")
        return True
    
    def get_session_status(self, session_id: str) -> Optional[Dict]:
        """获取会话状态"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # 计算成功率
        total = session["completed_count"] + session["failed_count"]
        success_rate = session["completed_count"] / total if total > 0 else 0
        
        return {
            "id": session["id"],
            "mode": session["mode"],
            "status": session["status"],
            "participants": session["participants"],
            "task_count": session["task_count"],
            "completed_count": session["completed_count"],
            "failed_count": session["failed_count"],
            "success_rate": round(success_rate, 2),
            "last_update": session["last_update"]
        }
    
    def close_session(self, session_id: str) -> bool:
        """关闭会话"""
        if session_id in self.sessions:
            session = self.sessions.pop(session_id)
            logger.info(f"👋 协作会话关闭: {session_id}")
            return True
        return False


class MultiComponentCollaboration:
    """
    多组件协作系统 - 主控制器
    整合所有协作功能
    """
    
    def __init__(self):
        # 核心组件
        self.collaboration_engine = DynamicCollaborationEngine()
        self.load_balancer = AdaptiveLoadBalancer()
        self.cross_domain = CrossDomainCoordinator()
        self.state_manager = CollaborationStateManager()
        
        # 指标收集
        self.metrics = CollaborationMetrics()
        
        # 协作会话
        self.active_collaborations: Dict[str, Dict] = {}
        
        # 任务队列
        self.task_queue: asyncio.Queue = asyncio.Queue()
        
        # 统计
        self.stats = {
            "total_collaborations": 0,
            "total_tasks": 0,
            "cross_domain_tasks": 0
        }
        
        logger.info("🤝 多组件协作系统初始化完成")
    
    def create_collaboration(self, name: str, participants: List[str],
                           mode: CollaborationMode = CollaborationMode.ADAPTIVE,
                           cross_domain: bool = False) -> str:
        """创建协作"""
        collaboration_id = f"collab_{int(time.time())}"
        
        collaboration = {
            "id": collaboration_id,
            "name": name,
            "participants": participants,
            "mode": mode,
            "cross_domain": cross_domain,
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        self.active_collaborations[collaboration_id] = collaboration
        
        # 创建状态管理会话
        self.state_manager.create_session(collaboration_id, participants, mode)
        
        # 注册参与组件
        for comp_id in participants:
            self.collaboration_engine.register_component(comp_id)
        
        self.stats["total_collaborations"] += 1
        
        logger.info(f"🤝 协作创建: {name} ({len(participants)}参与者)")
        return collaboration_id
    
    def execute_task(self, collaboration_id: str, task: Dict) -> bool:
        """执行协作任务"""
        collaboration = self.active_collaborations.get(collaboration_id)
        if not collaboration:
            return False
        
        self.stats["total_tasks"] += 1
        
        # 记录任务开始
        self.state_manager.record_task_event(
            collaboration_id, "task_started", task.get("id", "unknown")
        )
        
        # 模拟任务执行
        start_time = time.time()
        success = random.random() > 0.1  # 90%成功率
        response_time = random.uniform(0.1, 2.0)
        
        # 记录执行结果
        component_id = random.choice(collaboration["participants"])
        self.collaboration_engine.record_task_execution(
            component_id, success, response_time, 
            TaskType(task.get("type", "computation"))
        )
        
        # 更新指标
        if success:
            self.metrics.tasks_completed += 1
            self.state_manager.record_task_event(
                collaboration_id, "task_completed", task.get("id", "unknown")
            )
        else:
            self.metrics.tasks_failed += 1
            self.state_manager.record_task_event(
                collaboration_id, "task_failed", task.get("id", "unknown")
            )
        
        # 更新性能指标
        total = self.metrics.tasks_completed + self.metrics.tasks_failed
        if total > 0:
            self.metrics.collaboration_efficiency = (
                self.metrics.tasks_completed / total
            )
        
        return success
    
    def adapt_collaboration(self, collaboration_id: str) -> bool:
        """自适应协作策略"""
        collaboration = self.active_collaborations.get(collaboration_id)
        if not collaboration:
            return False
        
        # 调整协作引擎策略
        adapted = self.collaboration_engine.adapt_strategy()
        
        if adapted:
            # 更新协作模式
            new_mode = self.collaboration_engine.current_mode
            collaboration["mode"] = new_mode
            
            logger.info(f"🔄 协作策略已调整: {collaboration_id} -> {new_mode.value}")
        
        return adapted
    
    def get_collaboration_status(self, collaboration_id: str) -> Optional[Dict]:
        """获取协作状态"""
        collaboration = self.active_collaborations.get(collaboration_id)
        if not collaboration:
            return None
        
        session_status = self.state_manager.get_session_status(collaboration_id)
        performance = self.collaboration_engine.analyze_performance()
        
        return {
            "id": collaboration["id"],
            "name": collaboration["name"],
            "mode": collaboration["mode"].value,
            "status": collaboration["status"],
            "participants": collaboration["participants"],
            "session": session_status,
            "performance": performance,
            "metrics": self.metrics.to_dict()
        }
    
    def get_full_status(self) -> Dict:
        """获取完整系统状态"""
        return {
            "collaboration_engine": {
                "current_mode": self.collaboration_engine.current_mode.value,
                "component_count": len(self.collaboration_engine.components),
                "health": self.collaboration_engine.get_all_health()
            },
            "load_balancer": {
                "distribution": self.load_balancer.get_distribution_stats()
            },
            "cross_domain": {
                "domains": self.cross_domain.get_all_domains(),
                "cross_domain_tasks": len(self.cross_domain.cross_domain_tasks)
            },
            "state_manager": {
                "active_sessions": len(self.state_manager.sessions),
                "checkpoints": len(self.state_manager.checkpoints)
            },
            "metrics": self.metrics.to_dict(),
            "stats": self.stats,
            "timestamp": datetime.now().isoformat()
        }


# ========== 主程序 ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🦞 奥创 - 多组件协同工作系统")
    print("第2世：智能协作 - 多组件协同工作")
    print("=" * 60)
    
    # 创建多组件协作系统
    mcc = MultiComponentCollaboration()
    
    # 注册跨域
    mcc.cross_domain.register_domain("compute-domain", {
        "capabilities": ["computation", "processing", "analytics"]
    })
    mcc.cross_domain.register_domain("storage-domain", {
        "capabilities": ["storage", "retrieval", "backup"]
    })
    mcc.cross_domain.register_domain("network-domain", {
        "capabilities": ["network", "communication", "sync"]
    })
    
    # 创建协作
    collab_id = mcc.create_collaboration(
        "智能数据分析协作",
        ["compute-1", "compute-2", "storage-1", "network-1"],
        CollaborationMode.ADAPTIVE
    )
    
    print(f"✅ 协作已创建: {collab_id}")
    
    # 模拟执行任务
    for i in range(20):
        task = {
            "id": f"task_{i}",
            "name": f"分析任务-{i}",
            "type": random.choice(["computation", "analytics", "io"])
        }
        mcc.execute_task(collab_id, task)
        time.sleep(0.1)
    
    # 自适应调整
    mcc.adapt_collaboration(collab_id)
    
    # 获取状态
    status = mcc.get_collaboration_status(collab_id)
    
    print("\n📊 协作状态:")
    print(f"  模式: {status['mode']}")
    print(f"  参与者: {len(status['participants'])}")
    print(f"  任务数: {status['session']['task_count']}")
    print(f"  完成数: {status['session']['completed_count']}")
    print(f"  失败数: {status['session']['failed_count']}")
    print(f"  成功率: {status['session']['success_rate']}")
    
    print("\n📈 性能指标:")
    metrics = status['metrics']
    print(f"  总完成: {metrics['tasks_completed']}")
    print(f"  总失败: {metrics['tasks_failed']}")
    print(f"  协作效率: {metrics['collaboration_efficiency']}")
    
    print("\n🌐 跨域状态:")
    domains = mcc.cross_domain.get_all_domains()
    for domain_id, domain in domains.items():
        print(f"  {domain_id}: {domain['capabilities']}")
    
    print("\n🦞 第2世完成：多组件协同工作")