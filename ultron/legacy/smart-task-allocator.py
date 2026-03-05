#!/usr/bin/env python3
"""
奥创智能任务分配器 - 智能任务分配与负载均衡
Smart Task Allocator - Intelligent Task Distribution & Load Balancing

功能:
- 任务优先级评估
- 资源感知分配
- 负载均衡策略
"""

import asyncio
import time
import uuid
import random
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading


class Priority(Enum):
    """任务优先级"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    IDLE = 5


class TaskCategory(Enum):
    """任务类别"""
    MONITORING = "monitoring"
    DATA_COLLECTION = "data_collection"
    REPORTING = "reporting"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"


@dataclass
class Resource:
    """资源定义"""
    id: str
    name: str
    type: str
    capacity: float  # 总容量
    available: float  # 可用容量
    load: float = 0.0  # 当前负载 0-1
    cost: float = 1.0  # 使用成本
    latency: float = 0  # 响应延迟
    status: str = "available"


@dataclass
class SmartTask:
    """智能任务"""
    id: str
    name: str
    category: TaskCategory
    priority: Priority
    resource_requirement: float  # 所需资源 0-1
    estimated_duration: float  # 预计耗时(秒)
    deadline: Optional[float] = None  # 截止时间
    dependencies: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    assigned_to: Optional[str] = None
    status: str = "pending"
    weight: float = 1.0  # 权重因子


class PriorityEvaluator:
    """任务优先级评估器"""
    
    def __init__(self):
        # 优先级权重配置
        self.weights = {
            "category": 0.3,
            "deadline": 0.4,
            "resource": 0.15,
            "age": 0.15
        }
    
    def evaluate(self, task: SmartTask, context: Dict = None) -> float:
        """评估任务优先级分数 (越高越优先)"""
        context = context or {}
        
        # 1. 类别优先级
        category_scores = {
            TaskCategory.EMERGENCY: 100,
            TaskCategory.MONITORING: 80,
            TaskCategory.DATA_COLLECTION: 60,
            TaskCategory.REPORTING: 40,
            TaskCategory.MAINTENANCE: 20
        }
        category_score = category_scores.get(task.category, 50)
        
        # 2. 截止时间紧迫性
        deadline_score = 0
        if task.deadline:
            time_left = task.deadline - time.time()
            if time_left < 0:
                deadline_score = 100  # 已过期，最高优先级
            elif time_left < 60:
                deadline_score = 80
            elif time_left < 300:
                deadline_score = 60
            elif time_left < 900:
                deadline_score = 40
            else:
                deadline_score = 20
        
        # 3. 资源需求紧迫性
        resource_score = task.resource_requirement * 20
        
        # 4. 等待时间（年龄）
        age = time.time() - task.created_at
        age_score = min(age / 300, 1) * 20  # 5分钟饱和
        
        # 综合得分
        total_score = (
            category_score * self.weights["category"] +
            deadline_score * self.weights["deadline"] +
            resource_score * self.weights["resource"] +
            age_score * self.weights["age"]
        )
        
        return total_score
    
    def get_priority_level(self, score: float) -> Priority:
        """根据分数确定优先级级别"""
        if score >= 80:
            return Priority.CRITICAL
        elif score >= 60:
            return Priority.HIGH
        elif score >= 40:
            return Priority.NORMAL
        elif score >= 20:
            return Priority.LOW
        else:
            return Priority.IDLE


class ResourceAwareAllocator:
    """资源感知分配器"""
    
    def __init__(self, resources: List[Resource]):
        self.resources = {r.id: r for r in resources}
        self.allocation_history: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    
    def find_best_resource(self, task: SmartTask) -> Optional[Resource]:
        """找到最佳资源"""
        candidates = []
        
        for resource in self.resources.values():
            if resource.status != "available":
                continue
            
            if resource.available < task.resource_requirement:
                continue
            
            # 计算适配分数
            score = self._calculate_fit_score(resource, task)
            candidates.append((resource, score))
        
        if not candidates:
            return None
        
        # 返回得分最高的
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def _calculate_fit_score(self, resource: Resource, task: SmartTask) -> float:
        """计算资源适配分数"""
        # 1. 负载分数 (负载越低越好)
        load_score = (1 - resource.load) * 40
        
        # 2. 容量匹配分数
        match_ratio = resource.available / task.resource_requirement
        capacity_score = min(match_ratio, 2) * 20  # 匹配度越高越好
        
        # 3. 成本分数 (成本越低越好)
        cost_score = (1 / resource.cost) * 20
        
        # 4. 延迟分数 (延迟越低越好)
        latency_score = max(0, 20 - resource.latency)
        
        # 5. 亲和性分数 (基于历史分配)
        affinity_score = self._get_affinity_score(resource.id, task.category)
        
        return load_score + capacity_score + cost_score + latency_score + affinity_score
    
    def _get_affinity_score(self, resource_id: str, category: TaskCategory) -> float:
        """获取亲和性分数"""
        history = self.allocation_history.get(resource_id, [])
        if not history:
            return 10
        
        # 计算同类任务的成功率
        recent = history[-10:]
        category_match = sum(1 for _, cat in recent if cat == category.value)
        return (category_match / len(recent)) * 20
    
    def allocate(self, task: SmartTask, resource: Resource) -> bool:
        """分配任务到资源"""
        if resource.available < task.resource_requirement:
            return False
        
        # 更新资源状态
        resource.available -= task.resource_requirement
        resource.load = (resource.capacity - resource.available) / resource.capacity
        
        # 记录分配历史
        self.allocation_history[resource.id].append(
            (task.id, task.category.value)
        )
        
        task.assigned_to = resource.id
        task.status = "allocated"
        return True
    
    def release(self, task: SmartTask):
        """释放任务占用的资源"""
        if task.assigned_to:
            resource = self.resources.get(task.assigned_to)
            if resource:
                resource.available += task.resource_requirement
                resource.load = (resource.capacity - resource.available) / resource.capacity


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, allocator: ResourceAwareAllocator):
        self.allocator = allocator
        self.strategy = "adaptive"
    
    def rebalance(self) -> Dict[str, Any]:
        """重新平衡负载"""
        resources = list(self.allocator.resources.values())
        
        if not resources:
            return {"status": "no_resources"}
        
        # 计算平均负载
        avg_load = sum(r.load for r in resources) / len(resources)
        
        # 找出过载和低负载资源
        overloaded = [r for r in resources if r.load > 0.8]
        underloaded = [r for r in resources if r.load < 0.3]
        
        moves = []
        
        # 从过载资源移动任务到低负载资源
        for over in overloaded:
            for under in underloaded:
                if over.available < 0.1:  # 接近满载
                    # 模拟任务迁移
                    moves.append({
                        "from": over.id,
                        "to": under.id,
                        "action": "migrate_task"
                    })
        
        return {
            "status": "balanced" if len(overloaded) == 0 else "rebalancing",
            "avg_load": avg_load,
            "overloaded": [r.id for r in overloaded],
            "underloaded": [r.id for r in underloaded],
            "suggested_moves": moves
        }
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        resources = list(self.allocator.resources.values())
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_resources": len(resources),
            "available": sum(1 for r in resources if r.status == "available"),
            "avg_load": sum(r.load for r in resources) / max(len(resources), 1),
            "total_capacity": sum(r.capacity for r in resources),
            "total_available": sum(r.available for r in resources),
            "resources": [
                {
                    "id": r.id,
                    "name": r.name,
                    "type": r.type,
                    "load": r.load,
                    "available": r.available,
                    "status": r.status
                }
                for r in resources
            ]
        }


class SmartTaskQueue:
    """智能任务队列"""
    
    def __init__(self):
        self.queue: List[SmartTask] = []
        self.processing: Dict[str, SmartTask] = {}
        self.completed: List[SmartTask] = []
        self._lock = threading.Lock()
    
    def add_task(self, task: SmartTask):
        """添任务"""
        with self._lock:
            self.queue.append(task)
            # 按优先级排序
            self.queue.sort(key=lambda t: t.priority.value)
    
    def get_next_task(self) -> Optional[SmartTask]:
        """获取下一个任务"""
        with self._lock:
            if self.queue:
                task = self.queue.pop(0)
                task.status = "processing"
                self.processing[task.id] = task
                return task
        return None
    
    def complete_task(self, task_id: str, success: bool = True):
        """完成任务"""
        with self._lock:
            if task_id in self.processing:
                task = self.processing.pop(task_id)
                task.status = "completed" if success else "failed"
                self.completed.append(task)
    
    def get_pending_count(self) -> int:
        """获取待处理任务数"""
        with self._lock:
            return len(self.queue)


class IntelligentAllocator:
    """智能分配器 - 整合所有功能"""
    
    def __init__(self):
        # 初始化资源
        self.resources = [
            Resource("res-1", "主服务器", "server", 1.0, 1.0, cost=1.0),
            Resource("res-2", "辅助服务器", "server", 0.8, 0.8, cost=1.2),
            Resource("res-3", "边缘节点", "edge", 0.5, 0.5, cost=0.8),
        ]
        
        self.allocator = ResourceAwareAllocator(self.resources)
        self.load_balancer = LoadBalancer(self.allocator)
        self.priority_evaluator = PriorityEvaluator()
        self.task_queue = SmartTaskQueue()
        
        self._running = False
        self._process_task: Optional[asyncio.Task] = None
    
    def add_task(self, name: str, category: TaskCategory, 
                 resource_req: float, duration: float,
                 priority: Priority = Priority.NORMAL,
                 deadline: Optional[float] = None):
        """添加任务"""
        task = SmartTask(
            id=str(uuid.uuid4())[:8],
            name=name,
            category=category,
            priority=priority,
            resource_requirement=resource_req,
            estimated_duration=duration,
            deadline=deadline
        )
        
        # 评估优先级
        score = self.priority_evaluator.evaluate(task)
        task.priority = self.priority_evaluator.get_priority_level(score)
        
        self.task_queue.add_task(task)
        return task.id
    
    async def start(self):
        """启动分配器"""
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
    
    async def stop(self):
        """停止分配器"""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
    
    async def _process_loop(self):
        """处理循环"""
        while self._running:
            # 获取任务
            task = self.task_queue.get_next_task()
            if not task:
                await asyncio.sleep(0.5)
                continue
            
            # 找到最佳资源
            resource = self.allocator.find_best_resource(task)
            if not resource:
                # 没有可用资源，重新放回队列
                task.status = "pending"
                self.task_queue.queue.insert(0, task)
                await asyncio.sleep(1)
                continue
            
            # 分配任务
            self.allocator.allocate(task, resource)
            print(f"✓ 任务 [{task.name}] 已分配到 {resource.name}")
            
            # 模拟执行
            await asyncio.sleep(task.estimated_duration)
            
            # 完成任务
            self.allocator.release(task)
            self.task_queue.complete_task(task.id)
            
            # 定期负载均衡
            if random.random() < 0.1:
                rebalance_result = self.load_balancer.rebalance()
                if rebalance_result["status"] != "balanced":
                    print(f"⚠ 负载均衡: {rebalance_result['status']}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "queue_length": self.task_queue.get_pending_count(),
            "processing_count": len(self.task_queue.processing),
            "completed_count": len(self.task_queue.completed),
            "resources": self.load_balancer.get_health_report()
        }


async def demo():
    """演示"""
    print("=== 智能任务分配器演示 ===\n")
    
    # 创建分配器
    allocator = IntelligentAllocator()
    
    # 添加测试任务
    print("添加任务:")
    tasks = [
        ("紧急监控", TaskCategory.EMERGENCY, 0.3, 0.5, Priority.CRITICAL),
        ("常规采集", TaskCategory.DATA_COLLECTION, 0.4, 1.0, Priority.NORMAL),
        ("日报生成", TaskCategory.REPORTING, 0.2, 2.0, Priority.NORMAL),
        ("日志清理", TaskCategory.MAINTENANCE, 0.1, 0.5, Priority.LOW),
        ("性能监控", TaskCategory.MONITORING, 0.3, 0.3, Priority.HIGH),
        ("备份任务", TaskCategory.MAINTENANCE, 0.5, 3.0, Priority.IDLE),
    ]
    
    for name, cat, req, dur, pri in tasks:
        task_id = allocator.add_task(name, cat, req, dur, pri)
        print(f"  - {name} [{cat.value}] (资源需求: {req*100:.0f}%)")
    
    print(f"\n初始状态:")
    status = allocator.get_status()
    print(f"  队列: {status['queue_length']} 个待处理")
    print(f"  资源: {status['resources']['total_resources']} 个")
    
    # 启动分配器
    print("\n开始处理任务:")
    await allocator.start()
    
    # 等待任务完成
    while True:
        await asyncio.sleep(1)
        status = allocator.get_status()
        if status['queue_length'] == 0 and len(status['resources']['resources']) > 0:
            break
    
    # 停止
    await allocator.stop()
    
    # 最终状态
    print(f"\n最终状态:")
    status = allocator.get_status()
    print(f"  已完成: {status['completed_count']} 个任务")
    
    health = status['resources']
    print(f"\n资源健康报告:")
    print(f"  平均负载: {health['avg_load']:.1%}")
    print(f"  总容量: {health['total_capacity']:.1f}")
    print(f"  可用: {health['total_available']:.1f}")
    
    for res in health['resources']:
        print(f"  - {res['name']}: {res['load']:.1%} 负载")
    
    return status


if __name__ == "__main__":
    asyncio.run(demo())