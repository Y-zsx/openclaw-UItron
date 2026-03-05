#!/usr/bin/env python3
"""
协作网络健康监控CLI
"""
import requests
import json
import sys

BASE_URL = "http://localhost:18103"

def cmd_health():
    """系统健康状态"""
    resp = requests.get(f"{BASE_URL}/api/health")
    data = resp.json()
    print("=" * 50)
    print("🤖 多智能体协作网络健康状态")
    print("=" * 50)
    print(f"系统状态: {data['system_status'].upper()}")
    print(f"Agent总数: {data['total_agents']}")
    print(f"健康: {data['healthy_agents']} | 性能下降: {data['degraded_agents']} | 异常: {data['unhealthy_agents']}")
    print(f"平均健康分: {data['avg_health_score']}%")
    print(f"平均成功率: {data['avg_success_rate']}%")
    print(f"平均响应时间: {data['avg_response_time']}ms")
    print("=" * 50)

def cmd_agents():
    """所有Agent状态"""
    resp = requests.get(f"{BASE_URL}/api/agents")
    agents = resp.json()
    print("=" * 60)
    print(f"{'Agent':<15} {'状态':<10} {'健康分':<8} {'CPU':<8} {'内存':<8} {'成功率':<8}")
    print("=" * 60)
    for a in agents:
        print(f"{a['agent_name']:<15} {a['status']:<10} {a['health_score']:<8} {a['cpu_usage']:<8} {a['memory_usage']:<8} {a['task_success_rate']:<8}")
    print("=" * 60)

def cmd_alerts():
    """告警列表"""
    resp = requests.get(f"{BASE_URL}/api/alerts")
    alerts = resp.json()
    if not alerts:
        print("✅ 无告警")
        return
    print("=" * 60)
    print("⚠️ 告警列表")
    print("=" * 60)
    for a in alerts:
        print(f"[{a['severity'].upper()}] {a['message']}")
    print("=" * 60)

def cmd_history():
    """历史指标"""
    resp = requests.get(f"{BASE_URL}/api/metrics/history")
    history = resp.json()
    print("=" * 60)
    print("📈 历史指标 (最近10条)")
    print("=" * 60)
    for h in history[:10]:
        print(f"{h['timestamp'][:19]} | Agent: {h['healthy_agents']}/{h['total_agents']} | 成功率: {h['success_rate']}% | 响应: {h['avg_response_time']}ms")
    print("=" * 60)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'health'
    
    if cmd == 'health':
        cmd_health()
    elif cmd == 'agents':
        cmd_agents()
    elif cmd == 'alerts':
        cmd_alerts()
    elif cmd == 'history':
        cmd_history()
    elif cmd == 'all':
        cmd_health()
        print()
        cmd_agents()
        print()
        cmd_alerts()
    else:
        print(f"Usage: {sys.argv[0]} [health|agents|alerts|history|all]")