#!/usr/bin/env python3
"""
Agent Collaboration Network Stress Test Module
多智能体协作网络压力测试模块

功能：
- 并发任务压力测试
- 负载均衡策略验证
- 系统稳定性测试
- 性能指标收集

第72世: 多智能体协作网络 - 压力测试模块
"""

import asyncio
import aiohttp
import time
import random
import json
import sys
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import argparse


@dataclass
class TestResult:
    """测试结果数据类"""
    test_name: str
    start_time: float
    end_time: float
    total_requests: int
    success_count: int
    failure_count: int
    avg_latency: float
    max_latency: float
    min_latency: float
    throughput: float  # requests per second
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentCollabStressTest:
    """Agent协作网络压力测试器"""
    
    def __init__(self, base_url: str = "http://localhost:18290", concurrency: int = 10):
        self.base_url = base_url
        self.concurrency = concurrency
        self.results: List[TestResult] = []
        
    async def create_task(self, session: aiohttp.ClientSession, task_type: str = "test") -> Dict:
        """创建任务"""
        task_data = {
            "name": f"stress_test_{task_type}_{int(time.time()*1000)}",
            "type": task_type,
            "capability": "execution",
            "priority": random.choice(["LOW", "NORMAL", "HIGH"]),
            "payload": {
                "action": "stress_test",
                "timestamp": datetime.now().isoformat(),
                "data": "x" * random.randint(100, 1000)
            }
        }
        
        try:
            async with session.post(
                f"{self.base_url}/api/tasks",
                json=task_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                return {"status": resp.status, "data": await resp.json()} if resp.status == 200 else {"status": resp.status}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def register_test_agent(self, session: aiohttp.ClientSession, agent_id: str) -> Dict:
        """注册测试Agent"""
        agent_data = {
            "agent_id": agent_id,
            "name": f"TestAgent-{agent_id}",
            "capabilities": ["execution", "analysis", "monitoring"],
            "endpoint": f"http://localhost:18200",
            "metadata": {"test": True}
        }
        
        try:
            async with session.post(
                f"{self.base_url}/api/agents",
                json=agent_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def get_agents(self, session: aiohttp.ClientSession) -> Dict:
        """获取Agent列表"""
        try:
            async with session.get(f"{self.base_url}/api/agents") as resp:
                return await resp.json() if resp.status == 200 else {}
        except Exception as e:
            return {"error": str(e)}
    
    async def run_concurrent_tasks(self, num_requests: int, task_type: str = "test") -> TestResult:
        """运行并发任务测试"""
        print(f"  启动 {num_requests} 个并发请求 (并发度: {self.concurrency})...")
        
        start_time = time.time()
        latencies = []
        success_count = 0
        failure_count = 0
        
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        async with aiohttp.ClientSession(connector=connector) as session:
            # 使用信号量控制并发
            semaphore = asyncio.Semaphore(self.concurrency)
            
            async def bounded_task():
                nonlocal success_count, failure_count
                req_start = time.time()
                async with semaphore:
                    result = await self.create_task(session, task_type)
                    req_end = time.time()
                    
                    latencies.append(req_end - req_start)
                    if result.get("status") == 200:
                        success_count += 1
                    else:
                        failure_count += 1
            
            tasks = [bounded_task() for _ in range(num_requests)]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        throughput = num_requests / duration if duration > 0 else 0
        
        result = TestResult(
            test_name=f"concurrent_{task_type}",
            start_time=start_time,
            end_time=end_time,
            total_requests=num_requests,
            success_count=success_count,
            failure_count=failure_count,
            avg_latency=avg_latency,
            max_latency=max_latency,
            min_latency=min_latency,
            throughput=throughput
        )
        
        print(f"  完成: 成功 {success_count}, 失败 {failure_count}, 吞吐 {throughput:.2f} req/s")
        return result
    
    async def run_sustained_load_test(self, duration_seconds: int, rps: int) -> TestResult:
        """持续负载测试"""
        print(f"  启动持续负载测试: {duration_seconds}s, {rps} req/s...")
        
        start_time = time.time()
        latencies = []
        success_count = 0
        failure_count = 0
        request_count = 0
        
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        async with aiohttp.ClientSession(connector=connector) as session:
            while time.time() - start_time < duration_seconds:
                semaphore = asyncio.Semaphore(self.concurrency)
                batch_size = min(rps, self.concurrency)
                
                async def single_request():
                    nonlocal success_count, failure_count, request_count
                    req_start = time.time()
                    async with semaphore:
                        result = await self.create_task(session, "sustained")
                        req_end = time.time()
                        
                        request_count += 1
                        latencies.append(req_end - req_start)
                        if result.get("status") == 200:
                            success_count += 1
                        else:
                            failure_count += 1
                
                tasks = [single_request() for _ in range(batch_size)]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                await asyncio.sleep(1)  # 每秒一批
        
        end_time = time.time()
        duration = end_time - start_time
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        throughput = request_count / duration if duration > 0 else 0
        
        result = TestResult(
            test_name="sustained_load",
            start_time=start_time,
            end_time=end_time,
            total_requests=request_count,
            success_count=success_count,
            failure_count=failure_count,
            avg_latency=avg_latency,
            max_latency=max_latency,
            min_latency=min_latency,
            throughput=throughput
        )
        
        print(f"  完成: 请求 {request_count}, 成功 {success_count}, 失败 {failure_count}")
        return result
    
    async def run_load_balancing_test(self, num_tasks: int) -> Dict:
        """负载均衡测试 - 验证任务是否均匀分布"""
        print(f"  启动负载均衡测试: {num_tasks} 个任务...")
        
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        async with aiohttp.ClientSession(connector=connector) as session:
            # 获取初始Agent状态
            initial_agents = await self.get_agents(session)
            
            # 提交多个任务
            tasks = []
            for i in range(num_tasks):
                tasks.append(self.create_task(session, f"lb_test_{i}"))
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 等待处理
            await asyncio.sleep(2)
            
            # 获取最终Agent状态
            final_agents = await self.get_agents(session)
        
        return {
            "initial_agents": initial_agents,
            "final_agents": final_agents,
            "tasks_submitted": num_tasks
        }
    
    async def run_all_tests(self, mode: str = "full") -> List[TestResult]:
        """运行所有测试"""
        print(f"\n{'='*60}")
        print(f"Agent协作网络压力测试")
        print(f"模式: {mode}")
        print(f"目标: {self.base_url}")
        print(f"{'='*60}\n")
        
        # 测试1: 健康检查
        print("[1/5] 健康检查测试...")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/health") as resp:
                    health = await resp.json()
                    print(f"  健康状态: {health.get('status', 'unknown')}")
            except Exception as e:
                print(f"  错误: 无法连接到 {self.base_url}")
                return []
        
        # 测试2: 并发任务测试
        print("\n[2/5] 并发任务压力测试...")
        
        # 先注册测试Agent
        async with aiohttp.ClientSession() as session:
            for i in range(3):
                await self.register_test_agent(session, f"stress-test-agent-{i}")
        
        result1 = await self.run_concurrent_tasks(50, "stress")
        self.results.append(result1)
        
        # 测试3: 高并发测试
        print("\n[3/5] 高并发压力测试...")
        result2 = await self.run_concurrent_tasks(100, "high_load")
        self.results.append(result2)
        
        # 测试4: 负载均衡测试
        print("\n[4/5] 负载均衡测试...")
        lb_result = await self.run_load_balancing_test(20)
        
        # 测试5: 持续负载测试(短时间)
        if mode == "full":
            print("\n[5/5] 持续负载测试...")
            result3 = await self.run_sustained_load_test(10, 5)  # 10秒, 5 req/s
            self.results.append(result3)
        
        return self.results
    
    def print_summary(self):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print("测试结果摘要")
        print(f"{'='*60}")
        
        for result in self.results:
            print(f"\n测试: {result.test_name}")
            print(f"  总请求: {result.total_requests}")
            print(f"  成功: {result.success_count} ({result.success_count/result.total_requests*100:.1f}%)")
            print(f"  失败: {result.failure_count}")
            print(f"  平均延迟: {result.avg_latency*1000:.2f}ms")
            print(f"  最大延迟: {result.max_latency*1000:.2f}ms")
            print(f"  吞吐量: {result.throughput:.2f} req/s")
        
        # 保存结果到文件
        output_file = f"/root/.openclaw/workspace/ultron/logs/stress_test_{int(time.time())}.json"
        import os
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump({
                "test_time": datetime.now().isoformat(),
                "results": [r.to_dict() for r in self.results]
            }, f, indent=2)
        
        print(f"\n结果已保存到: {output_file}")


async def main():
    parser = argparse.ArgumentParser(description="Agent协作网络压力测试")
    parser.add_argument("--url", default="http://localhost:18290", help="API网关地址")
    parser.add_argument("--concurrency", type=int, default=10, help="并发数")
    parser.add_argument("--mode", choices=["quick", "full"], default="full", help="测试模式")
    
    args = parser.parse_args()
    
    tester = AgentCollabStressTest(args.url, args.concurrency)
    await tester.run_all_tests(args.mode)
    tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())