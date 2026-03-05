#!/usr/bin/env python3
"""
协作网络监控与现有系统集成
Integration helper for collab monitor with existing agent systems
"""

import json
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.collab_monitor import CollabMonitor
import time

def integrate_with_existing_systems():
    """与现有系统集成"""
    monitor = CollabMonitor()
    
    # 1. 从任务队列收集指标
    task_queue_path = "/root/.openclaw/workspace/ultron/agents/data/task_queue.json"
    if os.path.exists(task_queue_path):
        with open(task_queue_path) as f:
            data = json.load(f)
            pending = len(data.get("pending_tasks", []))
            running = len(data.get("running_tasks", []))
            completed = len(data.get("completed_tasks", []))
            
            monitor.record_metric("task_queue_length", float(pending), tags={"source": "task_queue"})
            monitor.record_metric("task_running", float(running), tags={"source": "task_queue"})
            monitor.record_metric("task_completed", float(completed), tags={"source": "task_queue"})
            
            # 计算失败率
            total = pending + running + completed
            if total > 0:
                failures = data.get("failed_tasks", [])
                failure_rate = len(failures) / total
                monitor.record_metric("task_failure_rate", failure_rate, tags={"source": "task_queue"})
    
    # 2. 从通信状态收集指标
    comm_path = "/root/.openclaw/workspace/ultron/agents/communication_state.json"
    if os.path.exists(comm_path):
        with open(comm_path) as f:
            data = json.load(f)
            msg_count = data.get("total_messages", 0)
            avg_latency = data.get("avg_latency", 0)
            
            monitor.record_metric("message_count", float(msg_count), tags={"source": "communication"})
            monitor.record_metric("message_latency", avg_latency, tags={"source": "communication"})
    
    # 3. 从生命周期管理器收集Agent状态
    lifecycle_path = "/root/.openclaw/workspace/ultron/agents/agent_lifecycle_state.json"
    if os.path.exists(lifecycle_path):
        with open(lifecycle_path) as f:
            data = json.load(f)
            active_agents = len(data.get("active_agents", []))
            total_agents = len(data.get("all_agents", []))
            
            monitor.record_metric("agent_online", float(active_agents), tags={"source": "lifecycle"})
            monitor.record_metric("agent_registered", float(total_agents), tags={"source": "lifecycle"})
            
            # 计算离线Agent
            offline = total_agents - active_agents
            if offline > 0:
                monitor.record_metric("agent_offline", float(offline), tags={"source": "lifecycle"})
    
    # 4. 从健康检查收集指标
    health_path = "/root/.openclaw/workspace/ultron/agents/data/health_status.json"
    if os.path.exists(health_path):
        with open(health_path) as f:
            data = json.load(f)
            healthy = data.get("healthy_count", 0)
            unhealthy = data.get("unhealthy_count", 0)
            
            monitor.record_metric("health_check_pass", float(healthy), tags={"source": "health"})
            monitor.record_metric("health_check_fail", float(unhealthy), tags={"source": "health"})
    
    # 5. 从负载均衡器收集指标
    lb_path = "/root/.openclaw/workspace/ultron/agents/data/load_balancer_state.json"
    if os.path.exists(lb_path):
        with open(lb_path) as f:
            data = json.load(f)
            load = data.get("current_load", 0)
            monitor.record_metric("network_load", load, tags={"source": "load_balancer"})
    
    return monitor.get_network_stats()

if __name__ == "__main__":
    stats = integrate_with_existing_systems()
    print(json.dumps(stats, indent=2, ensure_ascii=False))