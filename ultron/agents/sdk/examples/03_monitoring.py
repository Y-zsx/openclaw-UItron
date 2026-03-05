#!/usr/bin/env python3
"""
奥创SDK监控示例 - 健康监控与指标收集
展示系统监控和指标收集功能
"""

import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultron_agent_sdk import AgentClient
from ultron_agent_sdk.client import MeshClient, MobileClient

def monitor_system_health(agent_client: AgentClient):
    """系统健康监控"""
    print("=" * 50)
    print("🏥 系统健康监控")
    print("=" * 50)
    
    # 基础健康检查
    print("\n1. 健康检查:")
    health = agent_client.health_check()
    print(f"   状态: {health.status}")
    print(f"   版本: {health.version}")
    print(f"   运行时间: {health.uptime}秒")
    
    # 组件状态
    if hasattr(health, 'components') and health.components:
        print("   组件状态:")
        for component, status in health.components.items():
            print(f"     - {component}: {status}")
    
    return health


def collect_metrics(agent_client: AgentClient):
    """指标收集"""
    print("\n2. 指标收集:")
    
    # 不同时间段的指标
    periods = ["1m", "5m", "15m", "1h"]
    
    for period in periods:
        try:
            metrics = agent_client.metrics(period=period)
            print(f"\n   [{period}] 指标:")
            
            # 打印关键指标
            if isinstance(metrics, dict):
                for key, value in list(metrics.items())[:5]:
                    print(f"     {key}: {value}")
        except Exception as e:
            print(f"   [{period}] 获取失败: {e}")


def monitor_agents(agent_client: AgentClient):
    """Agent监控"""
    print("\n3. Agent监控:")
    
    # 按状态分组统计
    all_agents = agent_client.list()
    
    status_counts = {}
    for agent in all_agents:
        status = agent.status
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("   Agent状态分布:")
    for status, count in status_counts.items():
        print(f"     {status}: {count}")
    
    # 统计能力分布
    capability_counts = {}
    for agent in all_agents:
        for cap in agent.capabilities:
            capability_counts[cap] = capability_counts.get(cap, 0) + 1
    
    print("   能力分布:")
    for cap, count in sorted(capability_counts.items(), key=lambda x: -x[1])[:5]:
        print(f"     {cap}: {count}")


def monitor_mesh_services(mesh_client: MeshClient):
    """服务网格监控"""
    print("\n4. 服务网格监控:")
    
    try:
        # 获取服务列表
        services = mesh_client.list_services()
        print(f"   服务总数: {len(services)}")
        
        for service in services[:5]:
            print(f"   - {service.get('name', 'N/A')}: {service.get('status', 'N/A')}")
        
        # 获取熔断器状态
        print("\n   熔断器状态:")
        breakers = mesh_client.circuit_breakers()
        if breakers:
            for name, status in list(breakers.items())[:3]:
                print(f"     - {name}: {status}")
        else:
            print("     无熔断器数据")
            
    except Exception as e:
        print(f"   监控失败: {e}")


def run_monitoring_loop(agent_client: AgentClient, duration: int = 30):
    """持续监控循环"""
    print(f"\n5. 持续监控 ({duration}秒):")
    
    start_time = time.time()
    interval = 5  # 每5秒检查一次
    
    iteration = 0
    while time.time() - start_time < duration:
        iteration += 1
        elapsed = int(time.time() - start_time)
        
        try:
            health = agent_client.health_check()
            agents = agent_client.list(status="active")
            
            print(f"   [{elapsed}s] 健康: {health.status}, 活跃Agent: {len(agents)}")
        except Exception as e:
            print(f"   [{elapsed}s] 错误: {e}")
        
        if elapsed < duration:
            time.sleep(interval)
    
    print("   监控完成")


def main():
    base_url = os.getenv("ULTRON_API_URL", "http://localhost:18789/api/v3")
    
    print("=" * 50)
    print("📊 奥创SDK监控示例")
    print("=" * 50)
    
    agent_client = AgentClient(base_url=base_url)
    mesh_client = MeshClient(base_url=base_url)
    
    try:
        # 系统健康监控
        health = monitor_system_health(agent_client)
        
        # 指标收集
        collect_metrics(agent_client)
        
        # Agent监控
        monitor_agents(agent_client)
        
        # 服务网格监控
        monitor_mesh_services(mesh_client)
        
        # 简短持续监控
        run_monitoring_loop(agent_client, duration=10)
        
    except Exception as e:
        print(f"\n❌ 监控错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ 监控示例完成!")

if __name__ == "__main__":
    main()