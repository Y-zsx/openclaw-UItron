#!/usr/bin/env python3
"""
协作网络监控CLI
Collab Network Monitor CLI
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.collab_monitor import CollabMonitor, CollabAlertNotifier
import json

def cmd_status(args):
    monitor = CollabMonitor()
    stats = monitor.get_network_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

def cmd_alerts(args):
    monitor = CollabMonitor()
    alerts = monitor.get_active_alerts()
    if not alerts:
        print("✅ 无活跃告警")
        return
    print(json.dumps(alerts, indent=2, ensure_ascii=False))

def cmd_metrics(args):
    monitor = CollabMonitor()
    metrics = monitor.get_metrics(args.type, limit=args.limit)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

def cmd_start(args):
    monitor = CollabMonitor()
    notifier = CollabAlertNotifier(monitor)
    monitor.register_alert_callback(notifier.send_dingtalk_alert)
    monitor.start_monitoring(args.interval)
    print(f"🚀 监控已启动 (间隔 {args.interval}s)")
    
    # 模拟一些测试指标
    import time
    for i in range(5):
        monitor.record_metric("agent_online", 5 - i * 0.1)
        monitor.record_metric("task_queue_length", 10 + i * 2)
        time.sleep(1)
    
    stats = monitor.get_network_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    monitor.stop_monitoring()

def cmd_summary(args):
    monitor = CollabMonitor()
    alerts = monitor.get_active_alerts()
    notifier = CollabAlertNotifier(monitor)
    print(notifier.format_alert_summary(alerts))

def main():
    import argparse
    parser = argparse.ArgumentParser(description="协作网络监控")
    sub = parser.add_subparsers(dest="cmd", required=True)
    
    sub.add_parser("status", help="网络状态")
    sub.add_parser("alerts", help="活跃告警")
    sub.add_parser("summary", help="告警摘要")
    
    m = sub.add_parser("metrics", help="查询指标")
    m.add_argument("--type", help="指标类型")
    m.add_argument("--limit", type=int, default=20)
    
    s = sub.add_parser("start", help="启动监控")
    s.add_argument("--interval", type=float, default=10.0)
    
    args = parser.parse_args()
    
    cmds = {
        "status": cmd_status,
        "alerts": cmd_alerts,
        "metrics": cmd_metrics,
        "start": cmd_start,
        "summary": cmd_summary
    }
    
    cmds[args.cmd](args)

if __name__ == "__main__":
    main()