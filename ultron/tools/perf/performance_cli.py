#!/usr/bin/env python3
"""
Agent性能分析CLI工具
"""
import argparse
import json
import requests
import sys

API_BASE = "http://localhost:8095"

def cmd_stats(args):
    """系统状态"""
    r = requests.get(f"{API_BASE}/stats")
    data = r.json()
    
    print("📊 系统状态")
    print(f"  CPU: {data['cpu']['avg_percent']:.1f}% (核心数: {data['cpu']['count']})")
    print(f"  负载: {data['cpu']['load_avg']}")
    print(f"  内存: {data['memory']['used_mb']:.0f}MB / {data['memory']['total_mb']:.0f}MB ({data['memory']['percent']:.1f}%)")
    print(f"  磁盘: {data['disk']['used_gb']:.1f}GB / {data['disk']['total_gb']:.1f}GB ({data['disk']['percent']:.1f}%)")
    print(f"  运行时间: {data['uptime_seconds']/3600:.1f}小时")

def cmd_analysis(args):
    """性能分析"""
    r = requests.get(f"{API_BASE}/analysis")
    data = r.json()
    
    print(f"🎯 性能评分: {data['overall_score']}/100")
    print(f"\nCPU状态: {data['cpu']['status']} ({data['cpu']['avg_percent']:.1f}%)")
    print(f"内存状态: {data['memory']['status']} ({data['memory']['avg_percent']:.1f}%)")
    
    if data['recommendations']:
        print("\n💡 建议:")
        for rec in data['recommendations']:
            print(f"  • {rec}")
            
    if data['agent_issues']:
        print("\n⚠️ Agent问题:")
        for issue in data['agent_issues']:
            print(f"  • {issue}")

def cmd_agents(args):
    """Agent指标"""
    r = requests.get(f"{API_BASE}/agents")
    agents = r.json()
    
    if not agents:
        print("暂无注册的Agent")
        return
        
    print("🤖 Agent性能")
    for agent_id, data in agents.items():
        m = data['metrics']
        if m['request_count'] > 0:
            avg_latency = m['total_latency_ms'] / m['request_count']
            error_rate = m['error_count'] / m['request_count'] * 100
            print(f"\n{agent_id}:")
            print(f"  请求数: {m['request_count']}")
            print(f"  错误率: {error_rate:.1f}%")
            print(f"  延迟: {m['min_latency_ms']:.0f}ms ~ {m['max_latency_ms']:.0f}ms (avg: {avg_latency:.0f}ms)")
        else:
            print(f"\n{agent_id}: 无请求数据")

def cmd_snapshot(args):
    """完整快照"""
    r = requests.get(f"{API_BASE}/snapshot")
    data = r.json()
    print(json.dumps(data, indent=2))

def cmd_register(args):
    """注册Agent"""
    data = {'agent_id': args.agent_id, 'metadata': {'name': args.name or args.agent_id}}
    r = requests.post(f"{API_BASE}/agents/register", json=data)
    print(f"✅ {r.json()}")

def main():
    parser = argparse.ArgumentParser(description='Agent Performance CLI')
    sub = parser.add_subparsers()
    
    sub.add_parser('stats', help='系统状态').set_defaults(func=cmd_stats)
    sub.add_parser('analysis', help='性能分析').set_defaults(func=cmd_analysis)
    sub.add_parser('agents', help='Agent指标').set_defaults(func=cmd_agents)
    sub.add_parser('snapshot', help='完整快照').set_defaults(func=cmd_snapshot)
    
    reg = sub.add_parser('register', help='注册Agent')
    reg.add_argument('agent_id')
    reg.add_argument('--name')
    reg.set_defaults(func=cmd_register)
    
    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()