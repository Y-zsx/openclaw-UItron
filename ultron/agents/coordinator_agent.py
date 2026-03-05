#!/usr/bin/env python3
"""
协调Agent (Coordinator Agent) - 多智能体协作协调核心
负责任务依赖管理、Agent协作协调、结果汇总、冲突处理
支持负载均衡与故障转移
"""

import json
import os
import sys
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import queue

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENTS_DIR)

# 导入负载均衡模块
try:
    from load_balancer import (
        LoadBalancer, FailoverManager, FailoverConfig,
        LoadBalanceStrategy, AgentMetrics
    )
    LOAD_BALANCER_AVAILABLE = True
except ImportError:
    LOAD_BALANCER_AVAILABLE = False
    print("警告: 负载均衡模块不可用")


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CoordinationMode(Enum):
    """协作模式"""
    SEQUENTIAL = "sequential"      # 顺序执行
    PARALLEL = "parallel"          # 并行执行
    PIPELINE = "pipeline"          # 流水线模式
    FANOUT = "fanout"              # 扇出模式
    FANIN = "fanin"                # 扇入模式


@dataclass
class TaskDependency:
    """任务依赖"""
    task_id: str
    depends_on: Set[str] = field(default_factory=set)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = None
    start_time: str = None
    end_time: str = None
    assigned_agent: str = None


@dataclass
class CoordinationResult:
    """协调结果"""
    workflow_id: str
    status: str
    total_tasks: int
    completed: int
    failed: int
    blocked: int
    results: Dict[str, Any]
    execution_time: float
    timestamp: str


class CoordinatorAgent:
    """协调Agent - 多智能体协作协调核心"""
    
    def __init__(self, data_dir: str = None, enable_lb: bool = True):
        self.name = "coordinator"
        self.version = "1.1"  # 升级版本
        self.data_dir = data_dir or os.path.join(AGENTS_DIR, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 任务依赖图
        self.dependencies: Dict[str, TaskDependency] = {}
        
        # 协作模式
        self.mode: CoordinationMode = CoordinationMode.SEQUENTIAL
        
        # Agent注册表
        self.registered_agents: Dict[str, Dict] = {}
        
        # 任务结果
        self.task_results: Dict[str, Any] = {}
        
        # 事件队列
        self.event_queue = queue.Queue()
        
        # 锁
        self.lock = threading.RLock()
        
        # 历史记录
        self.workflow_history: List[Dict] = []
        
        # ============ 负载均衡与故障转移增强 ============
        self.enable_lb = enable_lb and LOAD_BALANCER_AVAILABLE
        
        if self.enable_lb:
            # 负载均衡器
            self.load_balancer = LoadBalancer(LoadBalanceStrategy.WEIGHTED)
            
            # 故障转移管理器
            failover_config = FailoverConfig(
                max_retries=3,
                retry_delay=2.0,
                health_check_interval=30.0,
                failure_threshold=3,
                auto_failover=True
            )
            self.failover_manager = FailoverManager(failover_config)
            
            # 任务Agent分配记录
            self.task_assignments: Dict[str, str] = {}
            
            # 任务重试队列
            self.retry_queue: queue.Queue = queue.Queue()
            
            # 后台重试线程
            self.retry_thread = None
            self.running = True
            
        else:
            self.load_balancer = None
            self.failover_manager = None
            self.task_assignments = {}
            self.retry_queue = None
            self.retry_thread = None
            self.running = False
        
    def initialize(self) -> Dict:
        """初始化协调Agent"""
        self._load_state()
        
        result = {
            "status": "initialized",
            "name": self.name,
            "version": self.version,
            "mode": self.mode.value,
            "registered_agents": len(self.registered_agents),
            "active_workflows": len(self.dependencies)
        }
        
        # 负载均衡状态
        if self.enable_lb:
            result["load_balancer"] = {
                "enabled": True,
                "strategy": self.load_balancer.strategy.value,
                "healthy_agents": len(self.load_balancer.get_healthy_agents())
            }
            result["failover"] = self.failover_manager.get_status()
            
            # 启动重试线程
            self._start_retry_worker()
        
        return result
    
    def _start_retry_worker(self):
        """启动重试工作线程"""
        if self.retry_thread is None or not self.retry_thread.is_alive():
            self.running = True
            self.retry_thread = threading.Thread(target=self._retry_worker, daemon=True)
            self.retry_thread.start()
    
    def _retry_worker(self):
        """重试工作线程"""
        while self.running:
            try:
                # 从重试队列获取任务
                task_info = self.retry_queue.get(timeout=1)
                if task_info is None:
                    continue
                    
                task_id = task_info["task_id"]
                retry_after = task_info.get("retry_after", 0)
                
                # 等待延迟
                if retry_after > 0:
                    time.sleep(retry_after)
                
                # 检查任务是否仍需要重试
                if task_id in self.dependencies:
                    task_dep = self.dependencies[task_id]
                    if task_dep.status == TaskStatus.FAILED:
                        # 重新选择Agent并重试
                        new_agent = self.load_balancer.select_agent(
                            exclude_agents={task_info.get("failed_agent", "")}
                        )
                        if new_agent:
                            self._retry_task(task_id, new_agent, task_info)
                
                self.retry_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"重试工作线程错误: {e}")
    
    def _retry_task(self, task_id: str, agent_id: str, task_info: Dict):
        """重试任务"""
        with self.lock:
            dep = self.dependencies[task_id]
            dep.status = TaskStatus.READY
            dep.assigned_agent = agent_id
            self.task_assignments[task_id] = agent_id
            
            # 更新负载均衡器
            self.load_balancer.agents.get(agent_id).increment_load() if agent_id in self.load_balancer.agents else None
            
            print(f"任务 {task_id} 重新分配给 Agent {agent_id}")
    
    def _load_state(self):
        """加载状态"""
        state_file = os.path.join(self.data_dir, "coordinator_state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    self.mode = CoordinationMode(data.get("mode", "sequential"))
                    self.registered_agents = data.get("agents", {})
                    # 恢复活跃任务
                    for task_id, task_data in data.get("dependencies", {}).items():
                        dep = TaskDependency(
                            task_id=task_id,
                            depends_on=set(task_data.get("depends_on", [])),
                            status=TaskStatus(task_data.get("status", "pending"))
                        )
                        self.dependencies[task_id] = dep
            except Exception as e:
                print(f"加载状态失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        state_file = os.path.join(self.data_dir, "coordinator_state.json")
        data = {
            "mode": self.mode.value,
            "agents": self.registered_agents,
            "dependencies": {
                task_id: {
                    "depends_on": list(dep.depends_on),
                    "status": dep.status.value
                }
                for task_id, dep in self.dependencies.items()
            }
        }
        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def register_agent(self, agent_id: str, agent_name: str, 
                      capabilities: List[str], status: str = "active",
                      weight: int = 100) -> Dict:
        """注册Agent"""
        with self.lock:
            self.registered_agents[agent_id] = {
                "name": agent_name,
                "capabilities": capabilities,
                "status": status,
                "registered_at": datetime.now().isoformat(),
                "current_task": None,
                "completed_tasks": 0,
                "weight": weight
            }
            
            # 注册到负载均衡器
            if self.enable_lb and self.load_balancer:
                self.load_balancer.register_agent(agent_id, weight)
                
            self._save_state()
            return {
                "agent_id": agent_id,
                "status": "registered",
                "capabilities": capabilities,
                "load_balanced": self.enable_lb
            }
    
    def unregister_agent(self, agent_id: str) -> Dict:
        """注销Agent"""
        with self.lock:
            if agent_id in self.registered_agents:
                del self.registered_agents[agent_id]
                
                # 从负载均衡器移除
                if self.enable_lb and self.load_balancer:
                    self.load_balancer.unregister_agent(agent_id)
                    
                self._save_state()
                return {"agent_id": agent_id, "status": "unregistered"}
            return {"agent_id": agent_id, "status": "not_found"}
    
    def set_coordination_mode(self, mode: str) -> Dict:
        """设置协作模式"""
        try:
            self.mode = CoordinationMode(mode)
            self._save_state()
            return {"mode": self.mode.value, "status": "updated"}
        except ValueError:
            return {"error": f"无效的协作模式: {mode}"}
    
    def create_workflow(self, workflow_id: str, tasks: List[Dict]) -> Dict:
        """
        创建工作流 - 带依赖关系
        tasks格式: [
            {
                "task_id": "task1",
                "name": "任务1",
                "depends_on": [],  # 依赖的任务ID列表
                "agent_id": "agent1",  # 可选，指定执行Agent
                "capability": "execute",  # 需要的能力
                "payload": {}  # 任务数据
            },
            ...
        ]
        """
        with self.lock:
            # 验证依赖关系
            task_ids = {t["task_id"] for t in tasks}
            for task in tasks:
                for dep_id in task.get("depends_on", []):
                    if dep_id not in task_ids:
                        return {"error": f"任务 {task['task_id']} 依赖的任务 {dep_id} 不存在"}
            
            # 创建任务依赖
            for task in tasks:
                task_id = task["task_id"]
                self.dependencies[task_id] = TaskDependency(
                    task_id=task_id,
                    depends_on=set(task.get("depends_on", []))
                )
            
            self._save_state()
            return {
                "workflow_id": workflow_id,
                "status": "created",
                "task_count": len(tasks),
                "mode": self.mode.value
            }
    
    def get_ready_tasks(self) -> List[str]:
        """获取就绪的任务（所有依赖都已完成）"""
        ready = []
        for task_id, dep in self.dependencies.items():
            if dep.status == TaskStatus.PENDING:
                # 检查所有依赖是否都已完成
                all_done = all(
                    self.dependencies.get(d_id, TaskDependency(d_id)).status == TaskStatus.COMPLETED
                    for d_id in dep.depends_on
                )
                if all_done:
                    ready.append(task_id)
                    dep.status = TaskStatus.READY
        return ready
    
    def get_blocked_tasks(self) -> List[Dict]:
        """获取被阻塞的任务"""
        blocked = []
        for task_id, dep in self.dependencies.items():
            if dep.status == TaskStatus.PENDING:
                # 检查是否有依赖未完成
                incomplete = [
                    d_id for d_id in dep.depends_on
                    if self.dependencies.get(d_id, TaskDependency(d_id)).status != TaskStatus.COMPLETED
                ]
                if incomplete:
                    blocked.append({
                        "task_id": task_id,
                        "waiting_on": incomplete,
                        "status": "blocked"
                    })
        return blocked
    
    def start_task(self, task_id: str, agent_id: str) -> Dict:
        """开始执行任务"""
        with self.lock:
            if task_id not in self.dependencies:
                return {"error": f"任务 {task_id} 不存在"}
            
            dep = self.dependencies[task_id]
            dep.status = TaskStatus.RUNNING
            dep.start_time = datetime.now().isoformat()
            dep.assigned_agent = agent_id
            
            # 更新Agent状态
            if agent_id in self.registered_agents:
                self.registered_agents[agent_id]["current_task"] = task_id
            
            self._save_state()
            return {
                "task_id": task_id,
                "agent_id": agent_id,
                "status": "started",
                "start_time": dep.start_time
            }
    
    def complete_task(self, task_id: str, result: Any = None, 
                     error: str = None) -> Dict:
        """完成任务 - 支持故障转移"""
        with self.lock:
            if task_id not in self.dependencies:
                return {"error": f"任务 {task_id} 不存在"}
            
            dep = self.dependencies[task_id]
            dep.end_time = datetime.now().isoformat()
            
            original_agent = dep.assigned_agent
            
            # 计算执行时间
            execution_time = 0.0
            if dep.start_time:
                start = datetime.fromisoformat(dep.start_time)
                execution_time = (datetime.fromisoformat(dep.end_time) - start).total_seconds()
            
            if error:
                dep.status = TaskStatus.FAILED
                dep.error = error
                
                # 更新负载均衡器 - 记录失败
                if self.enable_lb and original_agent and original_agent in self.load_balancer.agents:
                    self.load_balancer.agents[original_agent].record_failure()
                    
                    # 检查是否需要故障转移
                    if self.failover_manager and self.failover_manager.config.auto_failover:
                        task_data = {
                            "task_id": task_id,
                            "assigned_agent": original_agent,
                            "depends_on": list(dep.depends_on),
                            "payload": {}
                        }
                        
                        failover_result = self.failover_manager.record_failure(
                            task_id, original_agent, error, task_data
                        )
                        
                        # 如果需要重试，加入重试队列
                        if failover_result["action"] == "retry":
                            self.retry_queue.put({
                                "task_id": task_id,
                                "failed_agent": original_agent,
                                "retry_after": failover_result["delay"]
                            })
                            return {
                                "task_id": task_id,
                                "status": "failed_retry_scheduled",
                                "retry_count": failover_result["retry_count"],
                                "delay": failover_result["delay"]
                            }
            else:
                dep.status = TaskStatus.COMPLETED
                dep.result = result
                
                # 更新负载均衡器 - 记录成功
                if self.enable_lb and original_agent and original_agent in self.load_balancer.agents:
                    self.load_balancer.agents[original_agent].update_execution_time(execution_time)
                    self.load_balancer.agents[original_agent].decrement_load()
            
            # 记录结果
            self.task_results[task_id] = {
                "result": result,
                "error": error,
                "end_time": dep.end_time,
                "agent": dep.assigned_agent,
                "execution_time": execution_time
            }
            
            # 释放Agent
            if dep.assigned_agent and dep.assigned_agent in self.registered_agents:
                agent = self.registered_agents[dep.assigned_agent]
                agent["current_task"] = None
                if dep.status == TaskStatus.COMPLETED:
                    agent["completed_tasks"] = agent.get("completed_tasks", 0) + 1
            
            # 清除任务分配记录
            self.task_assignments.pop(task_id, None)
            
            # 清除失败记录
            if self.failover_manager:
                self.failover_manager.clear_task(task_id)
            
            self._save_state()
            
            # 检查是否有任务就绪
            ready_tasks = self.get_ready_tasks()
            
            return {
                "task_id": task_id,
                "status": dep.status.value,
                "ready_tasks": ready_tasks,
                "timestamp": dep.end_time
            }
    
    def execute_workflow(self, workflow_id: str, executor_callback=None) -> CoordinationResult:
        """执行工作流"""
        start_time = datetime.now()
        
        # 按依赖顺序获取执行列表
        execution_order = self._topological_sort()
        
        completed = 0
        failed = 0
        
        for task_id in execution_order:
            dep = self.dependencies[task_id]
            
            # 等待依赖完成（顺序模式）
            if self.mode == CoordinationMode.SEQUENTIAL:
                while dep.status == TaskStatus.PENDING:
                    # 检查依赖
                    all_done = all(
                        self.dependencies.get(d_id).status == TaskStatus.COMPLETED
                        for d_id in dep.depends_on if d_id in self.dependencies
                    )
                    if not all_done:
                        dep.status = TaskStatus.BLOCKED
                        failed += 1
                        break
                    dep.status = TaskStatus.READY
            
            if dep.status == TaskStatus.BLOCKED:
                continue
            
            # 分配Agent
            agent_id = self._allocate_agent(dep)
            if not agent_id:
                # 没有可用的Agent
                continue
            
            # 执行任务
            self.start_task(task_id, agent_id)
            
            if executor_callback:
                result = executor_callback(task_id, dep)
            else:
                result = {"status": "simulated", "task_id": task_id}
            
            # 完成任务
            if result.get("error"):
                self.complete_task(task_id, error=result["error"])
                failed += 1
            else:
                self.complete_task(task_id, result=result.get("data"))
                completed += 1
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # 构建结果
        workflow_result = CoordinationResult(
            workflow_id=workflow_id,
            status="completed" if failed == 0 else "completed_with_errors",
            total_tasks=len(self.dependencies),
            completed=completed,
            failed=failed,
            blocked=len([d for d in self.dependencies.values() if d.status == TaskStatus.BLOCKED]),
            results=self.task_results.copy(),
            execution_time=execution_time,
            timestamp=end_time.isoformat()
        )
        
        # 保存到历史
        self.workflow_history.append({
            "workflow_id": workflow_id,
            "result": {
                "status": workflow_result.status,
                "total_tasks": workflow_result.total_tasks,
                "completed": workflow_result.completed,
                "failed": workflow_result.failed,
                "execution_time": execution_time
            },
            "timestamp": end_time.isoformat()
        })
        
        return workflow_result
    
    def _topological_sort(self) -> List[str]:
        """拓扑排序 - 获取任务执行顺序"""
        # 计算入度
        in_degree = {task_id: len(dep.depends_on) for task_id, dep in self.dependencies.items()}
        
        # 入度为0的任务先执行
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            task_id = queue.pop(0)
            result.append(task_id)
            
            # 更新依赖此任务的任务的入度
            for other_id, dep in self.dependencies.items():
                if task_id in dep.depends_on:
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)
        
        return result
    
    def _allocate_agent(self, task_dep: TaskDependency, required_capability: str = None) -> Optional[str]:
        """分配Agent - 支持负载均衡"""
        
        # 如果启用了负载均衡，使用智能分配
        if self.enable_lb and self.load_balancer:
            # 尝试选择最佳Agent
            agent_id = self.load_balancer.select_agent(
                required_capability=required_capability,
                exclude_agents=set()
            )
            
            if agent_id:
                # 更新Agent负载
                if agent_id in self.load_balancer.agents:
                    self.load_balancer.agents[agent_id].increment_load()
                    
                # 记录分配
                self.task_assignments[task_dep.task_id] = agent_id
                return agent_id
        
        # 回退到原有逻辑
        # 查找空闲的Agent
        for agent_id, agent in self.registered_agents.items():
            if agent["status"] == "active" and agent.get("current_task") is None:
                return agent_id
        return None
    
    def get_workflow_status(self, workflow_id: str = None) -> Dict:
        """获取工作流状态"""
        status = {
            "coordinator": self.name,
            "mode": self.mode.value,
            "registered_agents": len(self.registered_agents),
            "active_tasks": len([d for d in self.dependencies.values() 
                               if d.status in [TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING]]),
            "completed_tasks": len([d for d in self.dependencies.values() 
                                   if d.status == TaskStatus.COMPLETED]),
            "tasks": {}
        }
        
        for task_id, dep in self.dependencies.items():
            status["tasks"][task_id] = {
                "status": dep.status.value,
                "depends_on": list(dep.depends_on),
                "assigned_agent": dep.assigned_agent,
                "start_time": dep.start_time,
                "end_time": dep.end_time,
                "result": dep.result if dep.status == TaskStatus.COMPLETED else None,
                "error": dep.error
            }
        
        return status
    
    def get_agent_status(self) -> Dict:
        """获取所有Agent状态"""
        base_status = {
            "agents": self.registered_agents,
            "total": len(self.registered_agents),
            "active": len([a for a in self.registered_agents.values() if a.get("current_task")]),
            "idle": len([a for a in self.registered_agents.values() if not a.get("current_task")])
        }
        
        # 添加负载均衡信息
        if self.enable_lb and self.load_balancer:
            base_status["load_balancer"] = self.load_balancer.get_all_metrics()
            
        if self.failover_manager:
            base_status["failover"] = self.failover_manager.get_status()
            
        return base_status
    
    def set_load_balance_strategy(self, strategy: str) -> Dict:
        """设置负载均衡策略"""
        if not self.enable_lb:
            return {"error": "负载均衡未启用"}
        
        try:
            self.load_balancer.strategy = LoadBalanceStrategy(strategy)
            return {
                "status": "updated",
                "strategy": self.load_balancer.strategy.value
            }
        except ValueError:
            return {"error": f"无效的策略: {strategy}"}
    
    def get_load_balancer_stats(self) -> Dict:
        """获取负载均衡统计"""
        if not self.enable_lb:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "strategy": self.load_balancer.strategy.value,
            "metrics": self.load_balancer.get_all_metrics(),
            "failover": self.failover_manager.get_status() if self.failover_manager else {}
        }
    
    def shutdown(self):
        """关闭协调器"""
        self.running = False
        if self.retry_thread:
            self.retry_thread.join(timeout=2)
    
    def resolve_conflict(self, task1_id: str, task2_id: str, resolution: str = "task1") -> Dict:
        """解决任务冲突"""
        # 简单冲突解决策略
        if resolution == "task1":
            if task2_id in self.dependencies:
                self.dependencies[task2_id].status = TaskStatus.BLOCKED
        elif resolution == "task2":
            if task1_id in self.dependencies:
                self.dependencies[task1_id].status = TaskStatus.BLOCKED
        
        self._save_state()
        return {
            "conflict": f"{task1_id} vs {task2_id}",
            "resolution": resolution,
            "status": "resolved"
        }
    
    def cancel_workflow(self, workflow_id: str = None) -> Dict:
        """取消工作流"""
        with self.lock:
            cancelled = 0
            for task_id, dep in self.dependencies.items():
                if dep.status in [TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING]:
                    dep.status = TaskStatus.CANCELLED
                    cancelled += 1
            
            self._save_state()
            return {
                "workflow_id": workflow_id,
                "cancelled_tasks": cancelled,
                "status": "cancelled"
            }
    
    def reset(self) -> Dict:
        """重置协调器"""
        with self.lock:
            self.dependencies.clear()
            self.task_results.clear()
            self._save_state()
            return {"status": "reset"}


# 全局单例
_coordinator = None

def get_coordinator() -> CoordinatorAgent:
    global _coordinator
    if _coordinator is None:
        _coordinator = CoordinatorAgent()
    return _coordinator


# CLI接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="协调Agent")
    subparsers = parser.add_subparsers(dest="action", help="操作")
    
    # 初始化
    subparsers.add_parser("init", help="初始化协调Agent")
    
    # 注册Agent
    parser_reg = subparsers.add_parser("register", help="注册Agent")
    parser_reg.add_argument("--agent-id", required=True, help="Agent ID")
    parser_reg.add_argument("--name", required=True, help="Agent名称")
    parser_reg.add_argument("--capabilities", required=True, help="能力列表(逗号分隔)")
    
    # 状态
    subparsers.add_parser("status", help="查看状态")
    subparsers.add_parser("agents", help="查看Agent状态")
    
    # 创建工作流
    parser_wf = subparsers.add_parser("create", help="创建工作流")
    parser_wf.add_argument("--workflow-id", required=True, help="工作流ID")
    parser_wf.add_argument("--tasks", required=True, help="任务JSON文件")
    
    # 执行工作流
    parser_exec = subparsers.add_parser("execute", help="执行工作流")
    parser_exec.add_argument("--workflow-id", required=True, help="工作流ID")
    
    # 设置模式
    parser_mode = subparsers.add_parser("mode", help="设置协作模式")
    parser_mode.add_argument("--mode", required=True, 
                            choices=["sequential", "parallel", "pipeline", "fanout", "fanin"],
                            help="协作模式")
    
    args = parser.parse_args()
    
    coordinator = get_coordinator()
    
    if args.action == "init":
        result = coordinator.initialize()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "register":
        caps = args.capabilities.split(",")
        result = coordinator.register_agent(args.agent_id, args.name, caps)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "status":
        result = coordinator.get_workflow_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "agents":
        result = coordinator.get_agent_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "create":
        with open(args.tasks, 'r') as f:
            tasks = json.load(f)
        result = coordinator.create_workflow(args.workflow_id, tasks)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "execute":
        result = coordinator.execute_workflow(args.workflow_id)
        print(json.dumps({
            "workflow_id": result.workflow_id,
            "status": result.status,
            "total_tasks": result.total_tasks,
            "completed": result.completed,
            "failed": result.failed,
            "execution_time": result.execution_time,
            "timestamp": result.timestamp
        }, indent=2, ensure_ascii=False))
        
    elif args.action == "mode":
        result = coordinator.set_coordination_mode(args.mode)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    else:
        parser.print_help()