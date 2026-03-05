#!/usr/bin/env python3
"""
多智能体协作网络 - 性能监控CLI
Performance Monitoring CLI for Multi-Agent Collaboration Network
"""

import argparse
import json
import sys
import time
import requests
from datetime import datetime

DEFAULT_HOST = "http://localhost:8899"

def get_metrics(host=DEFAULT_HOST):
    """获取性能指标"""
    try:
        r = requests.get(f"{host}/api/metrics", timeout=5)
        return r.json()
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return None

def get_history(host=DEFAULT_HOST, hours=1):
    """获取历史数据"""
    try:
        r = requests.get(f"{host}/api/history?hours={hours}", timeout=5)
        return r.json()
    except Exception as e:
        print(f"❌ 获取历史数据失败: {e}")
        return None

def print_metrics(metrics):
    """打印指标"""
    if not metrics:
        return
    
    print("\n" + "="*50)
    print("📊 多智能体协作网络 - 性能指标")
    print("="*50)
    print(f"🕐 更新时间: {datetime.now().strftime('%H:%M:%S')}")
    print("-"*50)
    print(f"📥 总请求数:    {metrics.get('requests_total', 0)}")
    print(f"✅ 成功请求:    {metrics.get('requests_success', 0)}")
    print(f"❌ 失败请求:    {metrics.get('requests_failed', 0)}")
    
    success_rate = 0
    total = metrics.get('requests_total', 0)
    if total > 0:
        success_rate = (metrics.get('requests_success', 0) / total) * 100
    print(f"📈 成功率:      {success_rate:.1f}%")
    
    print(f"⏱️  平均响应:    {metrics.get('avg_response_time', 0):.2f}ms")
    print(f"🤖 活跃Agent:   {metrics.get('active_agents', 0)}")
    print(f"📋 队列任务:    {metrics.get('tasks_queued', 0)}")
    print(f"✅ 已完成任务:   {metrics.get('tasks_completed', 0)}")
    print("="*50)

def print_history(history):
    """打印历史数据"""
    if not history:
        return
    
    print("\n📈 请求趋势 (最近1小时):")
    print("-"*60)
    for minute, count, avg_time in history.get('request_trend', [])[:10]:
        bar = "█" * min(int(count / 10), 30)
        print(f"{minute} | {bar} {count} req (avg: {avg_time:.1f}ms)")
    
    print("\n🤖 Agent性能:")
    print("-"*60)
    for agent_id, agent_type, avg_cpu, avg_mem, tasks in history.get('agent_performance', []):
        cpu_bar = "█" * int(avg_cpu / 5)
        mem_bar = "█" * int(avg_mem / 5)
        print(f"{agent_id[:16]:16} | CPU: {cpu_bar} {avg_cpu:.1f}%")
        print(f"                   | MEM: {mem_bar} {avg_mem:.1f}% | 任务: {tasks}")

def monitor(host=DEFAULT_HOST, interval=5):
    """持续监控"""
    print(f"\n🔄 开始监控 (每{interval}秒刷新, Ctrl+C退出)\n")
    try:
        while True:
            metrics = get_metrics(host)
            print_metrics(metrics)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")

def main():
    parser = argparse.ArgumentParser(description='多智能体协作网络 - 性能监控')
    parser.add_argument('--host', default=DEFAULT_HOST, help='监控面板地址')
    parser.add_argument('--watch', '-w', action='store_true', help='持续监控')
    parser.add_argument('--interval', '-i', type=int, default=5, help='监控间隔(秒)')
    parser.add_argument('--history', '-h', type=int, default=1, help='历史数据小时数')
    
    args = parser.parse_args()
    
    if args.watch:
        monitor(args.host, args.interval)
    else:
        metrics = get_metrics(args.host)
        print_metrics(metrics)
        
        history = get_history(args.host, args.history)
        if history:
            print_history(history)

if __name__ == '__main__':
    main()