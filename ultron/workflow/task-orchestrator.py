#!/usr/bin/env python3
"""
奥创任务编排器 - 第2世：任务编排
功能：依赖解析 + 并发控制 + 失败恢复
作者：奥创 (Ultron)
创建：2026-03-04
"""

import json
import time
import uuid
import asyncio
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    WAITING = "waiting"       # 等待依赖
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class ConcurrencyMode(Enum):
    """并发模式"""
    SEQUENTIAL = "sequential"     # 顺序执行
    PARALLEL = "parallel"         # 完全并行
    LIMITED = "limited"           # 限制并发数
    PIPELINE = "pipeline"         # 流水线


@dataclass
class TaskDependency:
    """任务依赖"""
    task_id: str
    required: bool = True          # 是否必须满足
    optional: bool = False         # 可选依赖


@dataclass
class Task:
    """任务定义"""
    id: str
    name: str
    command: str                   # 执行命令
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0              # 优先级（越大越高）
    timeout: int = 300             # 超时时间（秒）
    retry_count: int = 3           # 重试次数
    retry_delay: int = 5           # 重试延迟（秒）
    env: Dict[str, str] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attempt: int = 0               # 当前尝试次数

    def __hash__(self):
        return hash(self.id)


@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: str
    success: bool
    output: str = ""
    error: Optional[str] = None
    duration: float = 0
    attempts: int = 1


class DependencyResolver:
    """依赖解析器"""
    
    def __init__(self):
        self.graph: Dict[str, Set[str]] = defaultdict(set)  # task -> dependencies
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)  # task -> dependents
    
    def add_dependency(self, task_id: str, depends_on: str):
        """添加依赖"""
        self.graph[task_id].add(depends_on)
        self.reverse_graph[depends_on].add(task_id)
    
    def get_execution_order(self) -> List[List[str]]:
        """
        获取执行顺序（拓扑排序）
        返回：每批可以并行执行的任务列表
        """
        # 计算入度
        in_degree = defaultdict(int)
        all_tasks = set(self.graph.keys())
        for deps in self.graph.values():
            all_tasks.update(deps)
        
        for task in all_tasks:
            in_degree[task] = len(self.graph.get(task, set()))
        
        # 拓扑排序（Kahn算法）
        result = []
        queue = deque([t for t in all_tasks if in_degree[t] == 0])
        
        while queue:
            batch = []
            for _ in range(len(queue)):
                task = queue.popleft()
                batch.append(task)
                
                # 更新依赖任务的入度
                for dependent in self.reverse_graph[task]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
            
            if batch:
                result.append(batch)
        
        # 检测循环依赖
        if sum(in_degree.values()) > 0:
            raise ValueError("循环依赖 detected!")
        
        return result
    
    def get_waiting_tasks(self, completed: Set[str]) -> Set[str]:
        """获取等待执行的任务（依赖已满足）"""
        waiting = set()
        for task, deps in self.graph.items():
            if deps and deps.issubset(completed):
                waiting.add(task)
        return waiting
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """检测循环依赖"""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(task: str, path: List[str]) -> bool:
            visited.add(task)
            rec_stack.add(task)
            path.append(task)
            
            for dep in self.graph.get(task, set()):
                if dep not in visited:
                    if dfs(dep, path.copy()):
                        return True
                elif dep in rec_stack:
                    cycle_start = path.index(dep)
                    cycles.append(path[cycle_start:])
                    return True
            
            rec_stack.remove(task)
            return False
        
        for task in self.graph:
            if task not in visited:
                dfs(task, [])
        
        return cycles


class ConcurrencyController:
    """并发控制器"""
    
    def __init__(self, mode: ConcurrencyMode = ConcurrencyMode.LIMITED, max_concurrent: int = 5):
        self.mode = mode
        self.max_concurrent = max_concurrent
        self.running: Set[str] = set()
        self.lock = threading.Lock()
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def acquire(self, task_id: str) -> bool:
        """获取执行许可"""
        if self.mode == ConcurrencyMode.SEQUENTIAL:
            async with self.lock:
                if len(self.running) > 0:
                    return False
                self.running.add(task_id)
                return True
        
        elif self.mode == ConcurrencyMode.PARALLEL:
            self.running.add(task_id)
            return True
        
        elif self.mode == ConcurrencyMode.LIMITED:
            await self.semaphore.acquire()
            with self.lock:
                self.running.add(task_id)
            return True
        
        elif self.mode == ConcurrencyMode.PIPELINE:
            with self.lock:
                if len(self.running) >= self.max_concurrent:
                    return False
                self.running.add(task_id)
                return True
        
        return False
    
    def release(self, task_id: str):
        """释放执行许可"""
        with self.lock:
            self.running.discard(task_id)
        if self.mode == ConcurrencyMode.LIMITED:
            self.semaphore.release()
    
    def get_running_count(self) -> int:
        """获取正在运行的任务数"""
        return len(self.running)


class FailureRecovery:
    """失败恢复机制"""
    
    def __init__(self, max_retries: int = 3, retry_delay: int = 5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.failure_history: Dict[str, List[dict]] = defaultdict(list)
        self.fallback_handlers: Dict[str, callable] = {}
    
    def should_retry(self, task: Task) -> bool:
        """判断是否应该重试"""
        return task.attempt < task.retry_count
    
    async def retry_with_backoff(self, task: Task, executor: 'TaskExecutor'):
        """带退避的重试"""
        if not self.should_retry(task):
            return False
        
        # 计算退避时间
        delay = self.retry_delay * (2 ** task.attempt)
        await asyncio.sleep(delay)
        
        task.attempt += 1
        task.status = TaskStatus.RETRYING
        return True
    
    def record_failure(self, task_id: str, error: str, context: dict = None):
        """记录失败"""
        self.failure_history[task_id].append({
            'timestamp': datetime.now().isoformat(),
            'error': error,
            'context': context or {}
        })
    
    def get_failure_count(self, task_id: str) -> int:
        """获取失败次数"""
        return len(self.failure_history.get(task_id, []))
    
    def register_fallback(self, task_id: str, handler: callable):
        """注册降级处理器"""
        self.fallback_handlers[task_id] = handler
    
    async def execute_fallback(self, task: Task) -> Optional[Any]:
        """执行降级处理"""
        handler = self.fallback_handlers.get(task.id)
        if handler:
            try:
                return await handler(task)
            except Exception as e:
                self.record_failure(task.id, f"Fallback failed: {e}")
        return None
    
    def get_recovery_suggestions(self, task_id: str) -> List[str]:
        """获取恢复建议"""
        failures = self.failure_history.get(task_id, [])
        if not failures:
            return []
        
        suggestions = []
        error_types = [f['error'] for f in failures]
        
        if any('timeout' in e.lower() for e in error_types):
            suggestions.append("增加超时时间")
        if any('connection' in e.lower() for e in error_types):
            suggestions.append("检查网络连接")
        if any('memory' in e.lower() for e in error_types):
            suggestions.append("释放内存资源")
        if any('permission' in e.lower() for e in error_types):
            suggestions.append("检查权限设置")
        
        return suggestions


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, concurrency_mode: ConcurrencyMode = ConcurrencyMode.LIMITED):
        self.resolver = DependencyResolver()
        self.controller = ConcurrencyController(mode=concurrency_mode)
        self.recovery = FailureRecovery()
        self.tasks: Dict[str, Task] = {}
        self.execution_order: List[List[str]] = []
        self.completed: Set[str] = set()
        self.failed: Set[str] = set()
        self.lock = threading.Lock()
    
    def add_task(self, task: Task):
        """添加任务"""
        self.tasks[task.id] = task
        for dep in task.dependencies:
            self.resolver.add_dependency(task.id, dep)
    
    def build_execution_plan(self) -> bool:
        """构建执行计划"""
        try:
            self.execution_order = self.resolver.get_execution_order()
            
            # 按优先级排序每批任务
            for batch in self.execution_order:
                batch.sort(key=lambda t: self.tasks[t].priority, reverse=True)
            
            return True
        except ValueError as e:
            print(f"执行计划构建失败: {e}")
            return False
    
    async def execute_task(self, task: Task) -> ExecutionResult:
        """执行单个任务"""
        start_time = time.time()
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.now()
        
        try:
            # 模拟执行（实际应该执行真实命令）
            proc = await asyncio.create_subprocess_shell(
                task.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=task.env or None
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=task.timeout
                )
                
                duration = time.time() - start_time
                task.end_time = datetime.now()
                
                if proc.returncode == 0:
                    task.status = TaskStatus.COMPLETED
                    task.result = stdout.decode()
                    return ExecutionResult(
                        task_id=task.id,
                        success=True,
                        output=stdout.decode(),
                        duration=duration
                    )
                else:
                    raise Exception(stderr.decode())
                    
            except asyncio.TimeoutError:
                proc.kill()
                raise Exception(f"Task timeout after {task.timeout}s")
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.end_time = datetime.now()
            
            self.recovery.record_failure(task.id, str(e))
            
            # 尝试重试
            if await self.recovery.retry_with_backoff(task, self):
                return await self.execute_task(task)
            
            # 尝试降级处理
            fallback_result = await self.recovery.execute_fallback(task)
            if fallback_result is not None:
                task.status = TaskStatus.COMPLETED
                task.result = fallback_result
                return ExecutionResult(
                    task_id=task.id,
                    success=True,
                    output=f"Fallback executed: {fallback_result}",
                    duration=time.time() - start_time,
                    attempts=task.attempt
                )
            
            duration = time.time() - start_time
            return ExecutionResult(
                task_id=task.id,
                success=False,
                error=str(e),
                duration=duration,
                attempts=task.attempt
            )
    
    async def execute_batch(self, batch: List[str]) -> List[ExecutionResult]:
        """执行一批任务（并行）"""
        pending_tasks = [self.tasks[tid] for tid in batch 
                        if self.tasks[tid].status == TaskStatus.PENDING]
        
        if not pending_tasks:
            return []
        
        # 并发执行
        tasks_coroutines = [self.execute_task(task) for task in pending_tasks]
        results = await asyncio.gather(*tasks_coroutines, return_exceptions=True)
        
        valid_results = []
        for r in results:
            if isinstance(r, Exception):
                continue
            valid_results.append(r)
            
            if r.success:
                self.completed.add(r.task_id)
            else:
                self.failed.add(r.task_id)
        
        return valid_results
    
    async def execute_all(self) -> Dict[str, ExecutionResult]:
        """执行所有任务"""
        if not self.execution_order:
            if not self.build_execution_plan():
                return {}
        
        all_results = {}
        
        for batch_idx, batch in enumerate(self.execution_order):
            print(f"\n执行批次 {batch_idx + 1}/{len(self.execution_order)}: {batch}")
            
            # 等待依赖完成
            while True:
                ready = True
                for task_id in batch:
                    task = self.tasks[task_id]
                    deps = set(task.dependencies)
                    if not deps.issubset(self.completed):
                        ready = False
                        break
                
                if ready:
                    break
                await asyncio.sleep(0.5)
            
            # 执行当前批次
            results = await self.execute_batch(batch)
            
            for r in results:
                all_results[r.task_id] = r
            
            # 检查是否需要终止
            if self.failed:
                print(f"任务失败，终止执行。失败任务: {self.failed}")
                break
        
        return all_results
    
    def get_status(self) -> Dict[str, Any]:
        """获取执行状态"""
        return {
            'total': len(self.tasks),
            'completed': len(self.completed),
            'failed': len(self.failed),
            'pending': len(self.tasks) - len(self.completed) - len(self.failed),
            'running': sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING),
            'execution_order': self.execution_order,
            'failure_history': dict(self.recovery.failure_history)
        }
    
    def visualize_dag(self) -> str:
        """可视化DAG"""
        lines = ["Task Dependency Graph:", "=" * 40]
        
        for task_id, deps in self.resolver.graph.items():
            if deps:
                for dep in deps:
                    lines.append(f"{dep} --> {task_id}")
            else:
                lines.append(f"{task_id} (root)")
        
        return "\n".join(lines)


class TaskOrchestrator:
    """任务编排器主类"""
    
    def __init__(self, name: str = "default", concurrency: int = 5):
        self.name = name
        self.executor = TaskExecutor(concurrency_mode=ConcurrencyMode.LIMITED)
        self.executor.controller.max_concurrent = concurrency
        self.listeners: List[callable] = []
    
    def add_task(self, name: str, command: str, 
                 dependencies: List[str] = None,
                 priority: int = 0,
                 timeout: int = 300,
                 retry: int = 3) -> str:
        """添加任务"""
        task_id = str(uuid.uuid4())[:8]
        task = Task(
            id=task_id,
            name=name,
            command=command,
            dependencies=dependencies or [],
            priority=priority,
            timeout=timeout,
            retry_count=retry
        )
        self.executor.add_task(task)
        return task_id
    
    def add_simple_task(self, name: str, command: str) -> str:
        """添加简单任务（无依赖）"""
        return self.add_task(name, command, [], 0, 300, 3)
    
    def on_event(self, event_type: str, handler: callable):
        """注册事件监听器"""
        self.listeners.append((event_type, handler))
    
    async def run(self) -> Dict[str, ExecutionResult]:
        """运行编排任务"""
        # 触发开始事件
        for event_type, handler in self.listeners:
            if event_type == 'start':
                try:
                    handler(self)
                except:
                    pass
        
        # 执行
        results = await self.executor.execute_all()
        
        # 触发完成事件
        for event_type, handler in self.listeners:
            if event_type == 'complete':
                try:
                    handler(self, results)
                except:
                    pass
        
        return results
    
    def get_dashboard(self) -> Dict[str, Any]:
        """获取仪表板数据"""
        status = self.executor.get_status()
        return {
            'orchestrator': self.name,
            'status': status,
            'dag': self.executor.visualize_dag()
        }


# ============ 示例用法 ============

async def main():
    """示例：多阶段构建任务"""
    print("=" * 60)
    print("奥创任务编排器 - 第2世：任务编排")
    print("=" * 60)
    
    # 创建编排器
    orchestrator = TaskOrchestrator(name="multi-stage-build", concurrency=3)
    
    # 添加任务（模拟真实场景）
    # 阶段1：准备
    task1 = orchestrator.add_task("准备环境", "echo 'Preparing environment...'", priority=10)
    task2 = orchestrator.add_task("拉取代码", "echo 'Pulling code...'", priority=10)
    
    # 阶段2：构建（依赖阶段1）
    task3 = orchestrator.add_task(
        "安装依赖", 
        "echo 'Installing dependencies...'",
        dependencies=[task1],
        priority=5
    )
    task4 = orchestrator.add_task(
        "编译代码",
        "echo 'Building...'", 
        dependencies=[task2, task3],
        priority=5
    )
    
    # 阶段3：测试（依赖构建）
    task5 = orchestrator.add_task(
        "单元测试",
        "echo 'Running unit tests...'",
        dependencies=[task4],
        priority=3
    )
    task6 = orchestrator.add_task(
        "集成测试",
        "echo 'Running integration tests...'",
        dependencies=[task4],
        priority=3
    )
    
    # 阶段4：部署（依赖测试）
    task7 = orchestrator.add_task(
        "部署到测试环境",
        "echo 'Deploying to staging...'",
        dependencies=[task5, task6],
        priority=1
    )
    
    # 打印DAG
    print(orchestrator.get_dashboard()['dag'])
    print()
    
    # 注册事件
    def on_complete(orch, results):
        print("\n任务完成!")
        for task_id, result in results.items():
            status = "✅" if result.success else "❌"
            print(f"  {status} {task_id}: {result.duration:.2f}s")
    
    orchestrator.on_event('complete', on_complete)
    
    # 执行
    print("\n开始执行...\n")
    results = await orchestrator.run()
    
    # 状态
    print("\n最终状态:")
    status = orchestrator.get_dashboard()
    print(f"  总任务: {status['status']['total']}")
    print(f"  已完成: {status['status']['completed']}")
    print(f"  失败: {status['status']['failed']}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())