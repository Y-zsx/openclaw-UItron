#!/usr/bin/env python3
"""
多智能体协作网络 - 集成测试套件
Multi-Agent Collaboration Network - Integration Test Suite

测试覆盖:
1. Agent生命周期 (注册、心跳、注销)
2. 任务分发与协调
3. 工作流执行
4. 结果聚合
5. 错误处理与重试机制
"""

import json
import os
import sys
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# 测试结果追踪
class TestResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"

@dataclass
class TestCase:
    name: str
    description: str
    result: TestResult = TestResult.SKIP
    message: str = ""
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TestSuite:
    name: str
    description: str
    test_cases: List[TestCase] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def add_result(self, test: TestCase):
        self.test_cases.append(test)

    def summary(self) -> Dict[str, Any]:
        passed = sum(1 for t in self.test_cases if t.result == TestResult.PASS)
        failed = sum(1 for t in self.test_cases if t.result == TestResult.FAIL)
        skipped = sum(1 for t in self.test_cases if t.result == TestResult.SKIP)
        errors = sum(1 for t in self.test_cases if t.result == TestResult.ERROR)
        
        total_time = 0.0
        for t in self.test_cases:
            total_time += t.duration_ms
        
        return {
            "name": self.name,
            "total": len(self.test_cases),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total_duration_ms": total_time,
            "timestamp": datetime.now().isoformat()
        }

# 模拟Agent类
class MockAgent:
    def __init__(self, agent_id: str, agent_type: str, capabilities: List[str]):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.status = "offline"
        self.last_heartbeat = None
        self.task_history = []
    
    def register(self) -> bool:
        self.status = "online"
        self.last_heartbeat = datetime.now()
        return True
    
    def heartbeat(self) -> bool:
        self.last_heartbeat = datetime.now()
        return True
    
    def deregister(self) -> bool:
        self.status = "offline"
        return True
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.task_history.append(task)
        return {
            "agent_id": self.agent_id,
            "task_id": task.get("task_id"),
            "status": "completed",
            "result": f"Task executed by {self.agent_type}",
            "timestamp": datetime.now().isoformat()
        }

# 模拟注册中心
class AgentRegistry:
    def __init__(self):
        self.agents: Dict[str, MockAgent] = {}
    
    def register_agent(self, agent: MockAgent) -> Dict[str, Any]:
        self.agents[agent.agent_id] = agent
        agent.register()
        return {"status": "registered", "agent_id": agent.agent_id}
    
    def get_agent(self, agent_id: str) -> Optional[MockAgent]:
        return self.agents.get(agent_id)
    
    def get_agents_by_type(self, agent_type: str) -> List[MockAgent]:
        return [a for a in self.agents.values() if a.agent_type == agent_type]
    
    def list_agents(self) -> List[Dict[str, Any]]:
        return [
            {
                "agent_id": a.agent_id,
                "type": a.agent_type,
                "status": a.status,
                "capabilities": a.capabilities,
                "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None
            }
            for a in self.agents.values()
        ]
    
    def heartbeat(self, agent_id: str) -> bool:
        agent = self.agents.get(agent_id)
        if agent:
            return agent.heartbeat()
        return False
    
    def deregister(self, agent_id: str) -> bool:
        agent = self.agents.get(agent_id)
        if agent:
            agent.deregister()
            return True
        return False

# 模拟任务队列
class TaskQueue:
    def __init__(self):
        self.pending: List[Dict[str, Any]] = []
        self.in_progress: List[Dict[str, Any]] = []
        self.completed: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []
    
    def submit_task(self, task: Dict[str, Any]) -> str:
        task_id = f"task_{len(self.pending) + len(self.completed) + 1}"
        task["task_id"] = task_id
        task["status"] = "pending"
        task["created_at"] = datetime.now().isoformat()
        self.pending.append(task)
        return task_id
    
    def claim_task(self, agent_id: str) -> Optional[Dict[str, Any]]:
        if self.pending:
            task = self.pending.pop(0)
            task["status"] = "in_progress"
            task["claimed_by"] = agent_id
            task["started_at"] = datetime.now().isoformat()
            self.in_progress.append(task)
            return task
        return None
    
    def complete_task(self, task_id: str, result: Dict[str, Any]) -> bool:
        for task in self.in_progress:
            if task["task_id"] == task_id:
                task["status"] = "completed"
                task["result"] = result
                task["completed_at"] = datetime.now().isoformat()
                self.in_progress.remove(task)
                self.completed.append(task)
                return True
        return False
    
    def fail_task(self, task_id: str, error: str) -> bool:
        for task in self.in_progress:
            if task["task_id"] == task_id:
                task["status"] = "failed"
                task["error"] = error
                task["failed_at"] = datetime.now().isoformat()
                self.in_progress.remove(task)
                self.failed.append(task)
                return True
        return False
    
    def get_status(self) -> Dict[str, int]:
        return {
            "pending": len(self.pending),
            "in_progress": len(self.in_progress),
            "completed": len(self.completed),
            "failed": len(self.failed)
        }

# 模拟工作流编排器
class WorkflowEngine:
    def __init__(self, registry: AgentRegistry, task_queue: TaskQueue):
        self.registry = registry
        self.task_queue = task_queue
        self.workflows: Dict[str, Dict[str, Any]] = {}
    
    def register_workflow(self, workflow: Dict[str, Any]) -> str:
        workflow_id = workflow.get("workflow_id", f"wf_{len(self.workflows) + 1}")
        workflow["workflow_id"] = workflow_id
        workflow["status"] = "registered"
        self.workflows[workflow_id] = workflow
        return workflow_id
    
    def execute_workflow(self, workflow_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {"status": "error", "message": "Workflow not found"}
        
        steps = workflow.get("steps", [])
        results = []
        
        for step in steps:
            step_type = step.get("type")
            step_config = step.get("config", {})
            
            if step_type == "task":
                task = {
                    "type": step_config.get("task_type"),
                    "params": params,
                    "workflow_id": workflow_id
                }
                task_id = self.task_queue.submit_task(task)
                results.append({"step": step.get("name"), "task_id": task_id, "status": "submitted"})
            
            elif step_type == "aggregate":
                results.append({"step": step.get("name"), "type": "aggregate", "status": "aggregated"})
        
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "results": results
        }


# ============================================================
# 测试用例实现
# ============================================================

def test_agent_registration(registry: AgentRegistry) -> TestCase:
    test = TestCase(
        name="test_agent_registration",
        description="测试Agent注册功能"
    )
    start = time.time()
    
    try:
        # 创建测试Agent
        agent = MockAgent("test-agent-1", "analyzer", ["analysis", "reporting"])
        
        # 执行注册
        result = registry.register_agent(agent)
        
        # 验证结果
        if result["status"] == "registered" and result["agent_id"] == "test-agent-1":
            retrieved = registry.get_agent("test-agent-1")
            if retrieved and retrieved.status == "online":
                test.result = TestResult.PASS
                test.message = "Agent注册成功，状态正确"
            else:
                test.result = TestResult.FAIL
                test.message = "Agent注册后状态不正确"
        else:
            test.result = TestResult.FAIL
            test.message = f"注册返回结果异常: {result}"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test

def test_agent_heartbeat(registry: AgentRegistry) -> TestCase:
    test = TestCase(
        name="test_agent_heartbeat",
        description="测试Agent心跳功能"
    )
    start = time.time()
    
    try:
        # 先注册Agent
        agent = MockAgent("test-agent-2", "executor", ["execution"])
        registry.register_agent(agent)
        
        # 发送心跳
        result = registry.heartbeat("test-agent-2")
        
        if result and agent.last_heartbeat:
            test.result = TestResult.PASS
            test.message = "心跳功能正常"
        else:
            test.result = TestResult.FAIL
            test.message = "心跳更新失败"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test

def test_agent_deregistration(registry: AgentRegistry) -> TestCase:
    test = TestCase(
        name="test_agent_deregistration",
        description="测试Agent注销功能"
    )
    start = time.time()
    
    try:
        agent = MockAgent("test-agent-3", "coordinator", ["coordination"])
        registry.register_agent(agent)
        
        result = registry.deregister("test-agent-3")
        
        if result and agent.status == "offline":
            test.result = TestResult.PASS
            test.message = "Agent注销成功"
        else:
            test.result = TestResult.FAIL
            test.message = "Agent注销状态异常"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test

def test_task_submission(task_queue: TaskQueue) -> TestCase:
    test = TestCase(
        name="test_task_submission",
        description="测试任务提交功能"
    )
    start = time.time()
    
    try:
        task = {"type": "analysis", "params": {"data": "test"}}
        task_id = task_queue.submit_task(task)
        
        status = task_queue.get_status()
        
        if task_id and status["pending"] == 1:
            test.result = TestResult.PASS
            test.message = f"任务提交成功，task_id: {task_id}"
        else:
            test.result = TestResult.FAIL
            test.message = "任务队列状态异常"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test

def test_task_execution(task_queue: TaskQueue, registry: AgentRegistry) -> TestCase:
    test = TestCase(
        name="test_task_execution",
        description="测试任务执行流程"
    )
    start = time.time()
    
    try:
        # 注册执行Agent
        executor = MockAgent("executor-1", "executor", ["execute"])
        registry.register_agent(executor)
        
        # 提交任务
        task = {"type": "execute", "params": {"command": "test"}}
        task_queue.submit_task(task)
        
        # Agent认领任务
        claimed = task_queue.claim_task("executor-1")
        
        # 执行并完成任务
        result = executor.execute_task(claimed)
        task_queue.complete_task(claimed["task_id"], result)
        
        status = task_queue.get_status()
        
        if status["completed"] == 1:
            test.result = TestResult.PASS
            test.message = "任务执行流程完成"
        else:
            test.result = TestResult.FAIL
            test.message = f"任务状态异常: {status}"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test

def test_task_retry(task_queue: TaskQueue) -> TestCase:
    test = TestCase(
        name="test_task_retry",
        description="测试任务失败重试机制"
    )
    start = time.time()
    
    try:
        # 先提交一个任务
        task = {"type": "risky_task", "params": {}, "max_retries": 2}
        task_id = task_queue.submit_task(task)
        
        # Agent认领任务
        claimed = task_queue.claim_task("test-agent")
        
        # 模拟执行失败
        task_queue.fail_task(claimed["task_id"], "Simulated failure")
        
        status = task_queue.get_status()
        
        # 验证失败任务记录
        if status["failed"] == 1:
            # 重试逻辑 - 重新提交
            new_task_id = task_queue.submit_task({"type": "risky_task", "params": {}, "retry_of": task_id})
            status_after_retry = task_queue.get_status()
            
            if status_after_retry["pending"] >= 1:
                test.result = TestResult.PASS
                test.message = "重试机制工作正常"
            else:
                test.result = TestResult.FAIL
                test.message = "重试任务提交失败"
        else:
            test.result = TestResult.FAIL
            test.message = f"失败任务未正确记录: {status}"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test

def test_workflow_execution(registry: AgentRegistry, task_queue: TaskQueue) -> TestCase:
    test = TestCase(
        name="test_workflow_execution",
        description="测试工作流编排执行"
    )
    start = time.time()
    
    try:
        engine = WorkflowEngine(registry, task_queue)
        
        workflow = {
            "workflow_id": "test-workflow-1",
            "name": "Test Workflow",
            "steps": [
                {"name": "step1", "type": "task", "config": {"task_type": "analysis"}},
                {"name": "step2", "type": "task", "config": {"task_type": "execution"}},
                {"name": "step3", "type": "aggregate", "config": {}}
            ]
        }
        
        wf_id = engine.register_workflow(workflow)
        result = engine.execute_workflow(wf_id, {"input": "test"})
        
        if result["status"] == "completed" and len(result["results"]) == 3:
            test.result = TestResult.PASS
            test.message = "工作流执行成功"
        else:
            test.result = TestResult.FAIL
            test.message = f"工作流执行异常: {result}"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test

def test_agent_type_filter(registry: AgentRegistry) -> TestCase:
    test = TestCase(
        name="test_agent_type_filter",
        description="测试按类型筛选Agent"
    )
    start = time.time()
    
    try:
        # 注册多个不同类型的Agent
        agents = [
            MockAgent("filter-a1", "analyzer", ["a"]),
            MockAgent("filter-a2", "analyzer", ["b"]),
            MockAgent("filter-e1", "executor", ["c"]),
            MockAgent("filter-c1", "coordinator", ["d"])
        ]
        
        for agent in agents:
            registry.register_agent(agent)
        
        analyzers = registry.get_agents_by_type("analyzer")
        executors = registry.get_agents_by_type("executor")
        
        # 至少有我们在本测试中注册的 (2个analyzer, 1个executor)
        analyzer_count = sum(1 for a in analyzers if a.agent_id.startswith("filter-"))
        executor_count = sum(1 for e in executors if e.agent_id.startswith("filter-"))
        
        if analyzer_count >= 2 and executor_count >= 1:
            test.result = TestResult.PASS
            test.message = f"本测试注册: Analyzer: {analyzer_count}, Executor: {executor_count}"
        else:
            test.result = TestResult.FAIL
            test.message = f"Agent类型筛选结果异常 (a={analyzer_count}, e={executor_count})"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test

def test_concurrent_agents(registry: AgentRegistry, task_queue: TaskQueue) -> TestCase:
    test = TestCase(
        name="test_concurrent_agents",
        description="测试多Agent并发协作"
    )
    start = time.time()
    
    try:
        # 模拟多个Agent并发处理任务
        executors = []
        for i in range(3):
            agent = MockAgent(f"concurrent-executor-{i}", "executor", ["execute"])
            registry.register_agent(agent)
            executors.append(agent)
        
        # 提交多个任务
        task_ids = []
        for i in range(5):
            task_id = task_queue.submit_task({"type": "parallel", "params": {"id": i}})
            task_ids.append(task_id)
        
        # 模拟并发执行
        results = []
        for executor in executors:
            task = task_queue.claim_task(executor.agent_id)
            if task:
                result = executor.execute_task(task)
                task_queue.complete_task(task["task_id"], result)
                results.append(result)
        
        status = task_queue.get_status()
        
        if status["completed"] >= 3:
            test.result = TestResult.PASS
            test.message = f"并发执行完成 {len(results)} 个任务"
        else:
            test.result = TestResult.FAIL
            test.message = f"并发执行异常: {status}"
    except Exception as e:
        test.result = TestResult.ERROR
        test.message = f"测试执行出错: {str(e)}"
    
    test.duration_ms = (time.time() - start) * 1000
    return test


# ============================================================
# 主测试运行器
# ============================================================

def run_all_tests() -> TestSuite:
    suite = TestSuite(
        name="多智能体协作网络集成测试",
        description="全面测试多智能体系统的核心功能"
    )
    
    suite.start_time = datetime.now()
    
    # 初始化组件
    registry = AgentRegistry()
    task_queue = TaskQueue()
    
    # 执行测试用例
    tests = [
        test_agent_registration,
        test_agent_heartbeat,
        test_agent_deregistration,
        test_agent_type_filter,
        test_task_submission,
        test_task_execution,
        test_task_retry,
        test_workflow_execution,
        test_concurrent_agents
    ]
    
    # 测试函数需要的参数映射 (按函数签名顺序)
    test_mapping = {
        test_agent_registration: (registry,),
        test_agent_heartbeat: (registry,),
        test_agent_deregistration: (registry,),
        test_agent_type_filter: (registry,),
        test_task_submission: (task_queue,),
        test_task_execution: (task_queue, registry),
        test_task_retry: (task_queue,),
        test_workflow_execution: (registry, task_queue),
        test_concurrent_agents: (registry, task_queue)  # 修复: registry在前
    }
    
    for test_func in tests:
        args = test_mapping.get(test_func, (registry,))
        test = test_func(*args)
        suite.add_result(test)
        print(f"[{test.result.value}] {test.name}: {test.message}")
    
    suite.end_time = datetime.now()
    return suite


def main():
    print("=" * 60)
    print("多智能体协作网络 - 集成测试套件")
    print("=" * 60)
    print()
    
    suite = run_all_tests()
    
    print()
    print("=" * 60)
    summary = suite.summary()
    print(f"测试完成!")
    print(f"  总计: {summary['total']}")
    print(f"  通过: {summary['passed']} ✅")
    print(f"  失败: {summary['failed']} ❌")
    print(f"  跳过: {summary['skipped']} ⏭️")
    print(f"  错误: {summary['errors']} ⚠️")
    print(f"  耗时: {summary['total_duration_ms']:.2f}ms")
    print("=" * 60)
    
    # 返回退出码
    if summary['failed'] > 0 or summary['errors'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()