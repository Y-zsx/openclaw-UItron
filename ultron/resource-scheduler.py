#!/usr/bin/env python3
"""
奥创智能资源调度系统 - 第2世：资源调度
功能：自适应资源分配、负载均衡、优先级调度
"""

import os
import json
import time
import psutil
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import subprocess

class Priority(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    IDLE = 5

class ResourceType(Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"

@dataclass
class ResourceMetrics:
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_avg: tuple
    io_counters: dict
    
@dataclass
class Task:
    id: str
    name: str
    priority: Priority
    resource_type: ResourceType
    weight: float = 1.0
    max_cpu: float = 100.0
    max_memory: float = 100.0
    burst_allowed: bool = False
    created_at: str = ""
    last_scheduled: str = ""
    execution_time: float = 0.0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

@dataclass
class SchedulerPolicy:
    name: str
    enabled: bool = True
    weight: float = 1.0
    threshold: float = 80.0
    
class AdaptiveResourceAllocator:
    """自适应资源分配器"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.resource_history: List[ResourceMetrics] = []
        self.allocation_rules: Dict[str, Dict] = {}
        self.quotas: Dict[str, Dict] = defaultdict(lambda: {
            "cpu_quota": 100.0,
            "memory_quota": 100.0,
            "burst_used": 0.0,
            "burst_limit": 20.0
        })
        
    def add_task(self, task: Task):
        """添加任务到调度队列"""
        self.tasks[task.id] = task
        self._initialize_quota(task)
        
    def _initialize_quota(self, task: Task):
        """初始化任务资源配额"""
        base_quota = 100.0 / len(self.tasks) if self.tasks else 100.0
        self.quotas[task.id]["cpu_quota"] = min(task.max_cpu, base_quota * task.weight)
        self.quotas[task.id]["memory_quota"] = min(task.max_memory, base_quota * task.weight)
        
    def collect_metrics(self) -> ResourceMetrics:
        """收集当前资源指标"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        load = os.getloadavg()
        io = psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {}
        
        metrics = ResourceMetrics(
            timestamp=datetime.now().isoformat(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            load_avg=load,
            io_counters=io
        )
        self.resource_history.append(metrics)
        
        # 保留最近1小时历史
        cutoff = datetime.now() - timedelta(hours=1)
        self.resource_history = [
            m for m in self.resource_history 
            if datetime.fromisoformat(m.timestamp) > cutoff
        ]
        
        return metrics
    
    def calculate_adaptive_allocation(self) -> Dict[str, Dict]:
        """计算自适应资源分配"""
        metrics = self.collect_metrics()
        
        # 资源压力评分
        cpu_pressure = metrics.cpu_percent / 100.0
        memory_pressure = metrics.memory_percent / 100.0
        disk_pressure = metrics.disk_percent / 100.0
        
        total_pressure = (cpu_pressure + memory_pressure + disk_pressure) / 3
        
        allocations = {}
        
        for task_id, task in self.tasks.items():
            base_alloc = 100.0 / len(self.tasks) if self.tasks else 100.0
            
            # 优先级调整
            priority_multiplier = {
                Priority.CRITICAL: 2.0,
                Priority.HIGH: 1.5,
                Priority.NORMAL: 1.0,
                Priority.LOW: 0.7,
                Priority.IDLE: 0.3
            }.get(task.priority, 1.0)
            
            # 压力调整
            pressure_adjustment = 1.0
            if total_pressure > 0.8:
                pressure_adjustment = 0.5  # 高压时缩减
            elif total_pressure < 0.4:
                pressure_adjustment = 1.3  # 低压时扩展
                
            # 突发允许调整
            burst_adjustment = 1.0
            if task.burst_allowed and self.quotas[task_id]["burst_used"] < self.quotas[task_id]["burst_limit"]:
                burst_adjustment = 1.5
                
            final_cpu = base_alloc * task.weight * priority_multiplier * pressure_adjustment * burst_adjustment
            final_memory = base_alloc * task.weight * priority_multiplier
            
            allocations[task_id] = {
                "cpu": min(final_cpu, task.max_cpu),
                "memory": min(final_memory, task.max_memory),
                "priority": task.priority.name,
                "pressure": total_pressure
            }
            
        return allocations
    
    def get_resource_status(self) -> Dict[str, Any]:
        """获取资源状态摘要"""
        metrics = self.collect_metrics()
        
        return {
            "timestamp": metrics.timestamp,
            "cpu": {
                "percent": round(metrics.cpu_percent, 2),
                "status": self._get_status(metrics.cpu_percent, 80, 90)
            },
            "memory": {
                "percent": round(metrics.memory_percent, 2),
                "status": self._get_status(metrics.memory_percent, 80, 90)
            },
            "disk": {
                "percent": round(metrics.disk_percent, 2),
                "status": self._get_status(metrics.disk_percent, 85, 95)
            },
            "load": {
                "avg": metrics.load_avg,
                "cores": psutil.cpu_count(),
                "status": "normal" if metrics.load_avg[0] < psutil.cpu_count() else "high"
            }
        }
    
    def _get_status(self, value: float, warning: float, critical: float) -> str:
        if value >= critical:
            return "critical"
        elif value >= warning:
            return "warning"
        return "normal"

class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self):
        self.nodes: Dict[str, Dict] = {}
        self.health_checks: Dict[str, Dict] = {}
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.algorithm: str = "weighted_round_robin"
        
    def add_node(self, node_id: str, capacity: Dict[str, float], weight: int = 100):
        """添加节点"""
        self.nodes[node_id] = {
            "capacity": capacity,
            "weight": weight,
            "active": True,
            "added_at": datetime.now().isoformat()
        }
        self.request_counts[node_id] = 0
        
    def remove_node(self, node_id: str):
        """移除节点"""
        if node_id in self.nodes:
            self.nodes[node_id]["active"] = False
            
    def get_available_nodes(self) -> List[str]:
        """获取可用节点"""
        return [n for n, data in self.nodes.items() if data["active"]]
    
    def select_node(self, strategy: str = None) -> Optional[str]:
        """选择最佳节点"""
        available = self.get_available_nodes()
        if not available:
            return None
            
        strategy = strategy or self.algorithm
        
        if strategy == "weighted_round_robin":
            return self._weighted_round_robin(available)
        elif strategy == "least_connections":
            return self._least_connections(available)
        elif strategy == "least_load":
            return self._least_load(available)
        elif strategy == "random":
            import random
            return random.choice(available)
            
        return available[0]
    
    def _weighted_round_robin(self, nodes: List[str]) -> str:
        """加权轮询"""
        weights = [(n, self.nodes[n]["weight"]) for n in nodes]
        total = sum(w for _, w in weights)
        
        import random
        r = random.randint(0, total)
        
        cumulative = 0
        for node, weight in weights:
            cumulative += weight
            if r <= cumulative:
                return node
        return nodes[0]
    
    def _least_connections(self, nodes: List[str]) -> str:
        """最少连接"""
        return min(nodes, key=lambda n: self.request_counts[n])
    
    def _least_load(self, nodes: List[str]) -> str:
        """最低负载 - 简化版"""
        # 实际应该获取节点的实际负载
        return min(nodes, key=lambda n: self.request_counts[n])
    
    def record_request(self, node_id: str):
        """记录请求"""
        self.request_counts[node_id] += 1
        
    def release_connection(self, node_id: str):
        """释放连接"""
        if self.request_counts[node_id] > 0:
            self.request_counts[node_id] -= 1
            
    def get_status(self) -> Dict[str, Any]:
        """获取负载均衡状态"""
        return {
            "algorithm": self.algorithm,
            "total_nodes": len(self.nodes),
            "active_nodes": len(self.get_available_nodes()),
            "nodes": {
                n: {
                    "active": data["active"],
                    "weight": data["weight"],
                    "connections": self.request_counts[n]
                }
                for n, data in self.nodes.items()
            }
        }

class PriorityScheduler:
    """优先级调度器"""
    
    def __init__(self):
        self.queues: Dict[Priority, List[Task]] = {
            Priority.CRITICAL: [],
            Priority.HIGH: [],
            Priority.NORMAL: [],
            Priority.LOW: [],
            Priority.IDLE: []
        }
        self.completed_tasks: List[Task] = []
        self.running_task: Optional[Task] = None
        self.time_quantum: float = 1.0  # 秒
        
    def add_task(self, task: Task):
        """添加任务到对应优先级队列"""
        self.queues[task.priority].append(task)
        
    def get_next_task(self) -> Optional[Task]:
        """获取下一个要执行的任务"""
        # 按优先级从高到低
        for priority in Priority:
            if self.queues[priority]:
                task = self.queues[priority].pop(0)
                task.last_scheduled = datetime.now().isoformat()
                return task
        return None
    
    def execute_task(self, task: Task, run_func) -> bool:
        """执行任务"""
        self.running_task = task
        start_time = time.time()
        
        try:
            result = run_func(task)
            task.execution_time = time.time() - start_time
            self.completed_tasks.append(task)
            return True
        except Exception as e:
            print(f"Task {task.id} failed: {e}")
            return False
        finally:
            self.running_task = None
            
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "queues": {
                p.name: len(q) for p, q in self.queues.items()
            },
            "completed": len(self.completed_tasks),
            "running": self.running_task.id if self.running_task else None,
            "total_pending": sum(len(q) for q in self.queues.values())
        }

class ResourceScheduler:
    """综合资源调度器 - 主类"""
    
    def __init__(self):
        self.allocator = AdaptiveResourceAllocator()
        self.load_balancer = LoadBalancer()
        self.priority_scheduler = PriorityScheduler()
        self.scheduling_enabled = True
        self.monitor_thread: Optional[threading.Thread] = None
        self.running = False
        
        # 调度策略配置
        self.policies: Dict[str, SchedulerPolicy] = {
            "auto_scale": SchedulerPolicy("auto_scale", True, 1.0, 80.0),
            "load_balance": SchedulerPolicy("load_balance", True, 1.0, 70.0),
            "priority_inherit": SchedulerPolicy("priority_inherit", True, 0.8),
        }
        
    def add_task(self, task: Task):
        """添加任务"""
        self.allocator.add_task(task)
        self.priority_scheduler.add_task(task)
        
    def start_monitoring(self, interval: int = 30):
        """启动监控"""
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            
    def _monitor_loop(self, interval: int):
        """监控循环"""
        while self.running:
            try:
                self._perform_scheduling_cycle()
            except Exception as e:
                print(f"Scheduling cycle error: {e}")
            time.sleep(interval)
            
    def _perform_scheduling_cycle(self):
        """执行调度周期"""
        # 1. 收集资源指标
        status = self.allocator.get_resource_status()
        
        # 2. 检查是否需要自动扩展
        if self.policies["auto_scale"].enabled:
            self._check_auto_scale(status)
            
        # 3. 更新资源分配
        allocations = self.allocator.calculate_adaptive_allocation()
        
        # 4. 记录状态
        self._log_schedule_status(status, allocations)
        
    def _check_auto_scale(self, status: Dict):
        """检查自动扩展"""
        cpu = status.get("cpu", {}).get("percent", 0)
        
        if cpu > 90:
            print(f"⚠️ 高CPU警告: {cpu}% - 触发自动扩展")
            # 实际部署时可以触发容器扩展等
        elif cpu < 20:
            print(f"ℹ️ 低CPU: {cpu}% - 可考虑收缩资源")
            
    def _log_schedule_status(self, status: Dict, allocations: Dict):
        """记录调度状态"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "allocations": allocations
        }
        
        log_file = "/root/.openclaw/workspace/ultron/logs/scheduler.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """获取综合状态"""
        return {
            "resource_allocator": self.allocator.get_resource_status(),
            "load_balancer": self.load_balancer.get_status(),
            "priority_scheduler": self.priority_scheduler.get_queue_status(),
            "policies": {
                name: {"enabled": p.enabled, "weight": p.weight} 
                for name, p in self.policies.items()
            },
            "active": self.running
        }
    
    def generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        status = self.allocator.get_resource_status()
        
        # CPU建议
        cpu = status.get("cpu", {}).get("percent", 0)
        if cpu > 85:
            recommendations.append(f"🔥 CPU使用率过高({cpu}%)，建议降低优先级低的任务或增加资源")
        elif cpu < 20:
            recommendations.append(f"💡 CPU利用率低({cpu}%)，可增加并发任务")
            
        # 内存建议
        mem = status.get("memory", {}).get("percent", 0)
        if mem > 85:
            recommendations.append(f"🔥 内存使用率过高({mem}%)，建议清理缓存或增加内存")
            
        # 负载建议
        load = status.get("load", {})
        if load.get("status") == "high":
            recommendations.append(f"⚠️ 系统负载偏高，建议优化任务调度")
            
        if not recommendations:
            recommendations.append("✅ 系统资源状态良好")
            
        return recommendations

def main():
    """主函数 - 测试和演示"""
    scheduler = ResourceScheduler()
    
    # 添加测试任务
    tasks = [
        Task("task1", "关键业务", Priority.CRITICAL, ResourceType.CPU, weight=2.0),
        Task("task2", "数据分析", Priority.HIGH, ResourceType.CPU, weight=1.5),
        Task("task3", "日志收集", Priority.LOW, ResourceType.DISK, weight=0.5),
        Task("task4", "健康检查", Priority.NORMAL, ResourceType.NETWORK, weight=1.0),
    ]
    
    for task in tasks:
        scheduler.add_task(task)
        
    # 添加测试节点
    scheduler.load_balancer.add_node("node1", {"cpu": 100, "memory": 100}, weight=100)
    scheduler.load_balancer.add_node("node2", {"cpu": 80, "memory": 80}, weight=80)
    
    # 获取状态
    print("=" * 50)
    print("📊 资源调度系统状态")
    print("=" * 50)
    
    status = scheduler.get_comprehensive_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    
    print("\n💡 优化建议:")
    for rec in scheduler.generate_recommendations():
        print(f"  {rec}")
        
    return scheduler

if __name__ == "__main__":
    scheduler = main()