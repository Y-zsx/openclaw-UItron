#!/usr/bin/env python3
"""
Agent协作网络压力测试CLI
Usage: python stress_test_cli.py [command] [options]
"""

import asyncio
import json
import sys
import time
import argparse
import random
from performance_tester import (
    PerformanceProfiler, StressTestRunner, BenchmarkSuite, PerformanceOptimizer
)


# 模拟Agent函数
def simulate_task_execution():
    """模拟任务执行"""
    time.sleep(random.uniform(0.001, 0.01))


async def simulate_async_task():
    """模拟异步任务"""
    await asyncio.sleep(random.uniform(0.001, 0.005))


def main():
    parser = argparse.ArgumentParser(description='Agent协作网络压力测试工具')
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # 负载测试
    load_parser = subparsers.add_parser('load', help='运行负载测试')
    load_parser.add_argument('--concurrency', '-c', type=int, default=10, help='并发数')
    load_parser.add_argument('--duration', '-d', type=float, default=10, help='持续时间(秒)')
    load_parser.add_argument('--name', '-n', default='test', help='测试名称')
    
    # 并发测试
    concurrent_parser = subparsers.add_parser('concurrent', help='运行并发测试')
    concurrent_parser.add_argument('--threads', '-t', type=int, default=10, help='线程数')
    concurrent_parser.add_argument('--iterations', '-i', type=int, default=100, help='迭代次数')
    concurrent_parser.add_argument('--name', '-n', default='test', help='测试名称')
    
    # 基准测试
    bench_parser = subparsers.add_parser('benchmark', help='运行基准测试')
    bench_parser.add_argument('--iterations', '-i', type=int, default=1000, help='迭代次数')
    
    # 分析
    analyze_parser = subparsers.add_parser('analyze', help='分析性能')
    analyze_parser.add_argument('--operation', '-o', help='操作名称')
    
    # 报告
    report_parser = subparsers.add_parser('report', help='生成优化报告')
    
    args = parser.parse_args()
    
    profiler = PerformanceProfiler()
    
    if args.command == 'load':
        runner = StressTestRunner(profiler)
        
        async def request_func():
            await simulate_async_task()
        
        print(f"开始负载测试: {args.name}")
        print(f"并发: {args.concurrency}, 持续: {args.duration}s")
        
        result = asyncio.run(
            runner.run_load_test(args.name, request_func, args.concurrency, args.duration)
        )
        
        print("\n=== 负载测试结果 ===")
        print(f"测试名称: {result.test_name}")
        print(f"总请求数: {result.total_requests}")
        print(f"成功: {result.success_count}, 失败: {result.error_count}")
        print(f"吞吐量: {result.throughput:.2f} req/s")
        print(f"平均延迟: {result.avg_latency*1000:.2f}ms")
        print(f"最大延迟: {result.max_latency*1000:.2f}ms")
        print(f"错误率: {result.error_rate:.2%}")
    
    elif args.command == 'concurrent':
        runner = StressTestRunner(profiler)
        
        print(f"开始并发测试: {args.name}")
        print(f"线程: {args.threads}, 迭代: {args.iterations}")
        
        result = runner.run_concurrent_test(
            args.name, simulate_task_execution, args.threads, args.iterations
        )
        
        print("\n=== 并发测试结果 ===")
        print(f"测试名称: {result.test_name}")
        print(f"总请求数: {result.total_requests}")
        print(f"成功: {result.success_count}, 失败: {result.error_count}")
        print(f"吞吐量: {result.throughput:.2f} ops/s")
        print(f"平均延迟: {result.avg_latency*1000:.2f}ms")
        print(f"最大延迟: {result.max_latency*1000:.2f}ms")
        print(f"错误率: {result.error_rate:.2%}")
    
    elif args.command == 'benchmark':
        suite = BenchmarkSuite(profiler)
        
        print("运行基准测试...")
        
        # 测试任务执行
        result1 = suite.benchmark_function('task_execution', simulate_task_execution, args.iterations)
        print(f"\n任务执行: {result1['avg_time']*1000:.3f}ms avg, {result1['throughput']:.0f} ops/s")
        
        # 测试异步任务
        result2 = suite.benchmark_async('async_task', simulate_async_task, min(args.iterations//10, 100))
        print(f"异步任务: {result2['avg_time']*1000:.3f}ms avg, P95: {result2['p95']*1000:.3f}ms")
    
    elif args.command == 'analyze':
        optimizer = PerformanceOptimizer(profiler)
        
        # 先填充一些测试数据
        for _ in range(50):
            profiler.record(args.operation or 'task_execution', random.uniform(0.01, 0.1))
        
        result = optimizer.analyze_bottlenecks(args.operation or 'task_execution')
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == 'report':
        optimizer = PerformanceOptimizer(profiler)
        
        # 填充测试数据
        for op in ['task_execution', 'message_delivery', 'agent_registration']:
            for _ in range(30):
                profiler.record(op, random.uniform(0.001, 0.1))
        
        report = optimizer.get_optimization_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()