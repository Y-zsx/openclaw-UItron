#!/usr/bin/env python3
"""
任务监控集成模块
用于将任意任务集成到任务监控系统中
"""

import sys
import os

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/ultron-workflow')

from task_exec_monitor import log_task_start, log_task_end
import traceback

class TaskMonitor:
    """任务监控上下文管理器"""
    
    def __init__(self, task_id, task_name=None, triggered_by=None):
        self.task_id = task_id
        self.task_name = task_name or task_id
        self.triggered_by = triggered_by or "unknown"
        self.execution_id = None
    
    def __enter__(self):
        self.execution_id = log_task_start(self.task_id, self.task_name, self.triggered_by)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # 任务失败
            error_msg = str(exc_val)
            log_task_end(self.execution_id, "fail", error_message=error_msg)
        else:
            # 任务成功
            log_task_end(self.execution_id, "success")
        
        return False  # 不抑制异常


def monitored_task(task_id, task_name=None):
    """
    装饰器：用于装饰需要监控的函数
    
    用法:
        @monitored_task("my_task", "我的任务")
        def my_function():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with TaskMonitor(task_id, task_name or func.__name__, "function_call"):
                return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # 测试
    print("Task Monitor Integration Test")
    print("=" * 40)
    
    # 方式1: 上下文管理器
    print("\n[测试1] 使用上下文管理器")
    with TaskMonitor("demo_task_001", "演示任务", "test") as m:
        import time
        time.sleep(0.2)
        print(f"  任务执行中... (execution_id: {m.execution_id})")
    print("  任务完成!")
    
    # 方式2: 手动调用
    print("\n[测试2] 手动调用")
    exec_id = log_task_start("demo_task_002", "手动任务", "test")
    print(f"  任务开始: {exec_id}")
    
    try:
        # 模拟任务执行
        result = 10 / 2
        log_task_end(exec_id, "success", result=f"计算结果: {result}")
        print("  任务成功!")
    except Exception as e:
        log_task_end(exec_id, "fail", error_message=str(e))
        print("  任务失败!")
    
    print("\n测试完成!")