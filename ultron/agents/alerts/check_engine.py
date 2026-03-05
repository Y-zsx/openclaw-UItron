#!/usr/bin/env python3
"""
Agent告警规则引擎 - 定时检查脚本
第86世: 告警通知渠道集成
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入告警引擎和通知器
import importlib.util

# 加载 ops-alert-engine.py
spec = importlib.util.spec_from_file_location(
    "ops_alert_engine", 
    "/root/.openclaw/workspace/ultron/ops-alert-engine.py"
)
ops_alert_engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops_alert_engine)
AlertEngine = ops_alert_engine.AlertEngine

# 加载 ops-alert-notifier.py
spec = importlib.util.spec_from_file_location(
    "ops_alert_notifier", 
    "/root/.openclaw/workspace/ultron/ops-alert-notifier.py"
)
ops_alert_notifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops_alert_notifier)
AlertNotifier = ops_alert_notifier.AlertNotifier


def get_system_metrics():
    """获取系统指标"""
    metrics = {}
    
    # CPU
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[:3]
            metrics['system.cpu.usage'] = float(load[0]) * 10  # 近似百分比
    except:
        pass
    
    # 内存
    try:
        with open('/proc/meminfo', 'r') as f:
            mem = {}
            for line in f:
                if ':' in line:
                    k, v = line.split(':', 1)
                    mem[k.strip()] = int(v.strip().split()[0])
            
            total = mem.get('MemTotal', 1)
            available = mem.get('MemAvailable', 0)
            used = total - available
            metrics['system.memory.usage'] = (used / total) * 100
    except:
        pass
    
    # 磁盘
    try:
        result = subprocess.run(
            ['df', '-h', '/'],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            metrics['system.disk.usage'] = float(parts[4].replace('%', ''))
    except:
        pass
    
    # 进程数
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True, text=True
        )
        metrics['system.process_count'] = len(result.stdout.strip().split('\n'))
    except:
        pass
    
    return metrics


def get_openclaw_metrics():
    """获取OpenClaw指标"""
    metrics = {}
    
    # Gateway状态
    try:
        result = subprocess.run(
            ['openclaw', 'status', '--json'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            status = json.loads(result.stdout)
            metrics['agent.gateway.status'] = status.get('gateway', {}).get('status', 0)
    except:
        metrics['agent.gateway.status'] = 0
    
    # 端口检查
    ports = {
        'agent.gateway': 18789,
        'agent.browser': 18800,
        'agent.api': 8110,
    }
    
    for name, port in ports.items():
        try:
            result = subprocess.run(
                ['nc', '-z', '127.0.0.1', str(port)],
                capture_output=True, timeout=2
            )
            metrics[f'{name}.health'] = 1 if result.returncode == 0 else 0
        except:
            metrics[f'{name}.health'] = 0
    
    return metrics


def main():
    """主函数"""
    print(f"🔔 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 告警规则引擎检查")
    
    # 初始化引擎和通知器
    engine = AlertEngine()
    notifier = AlertNotifier()
    
    # 获取指标
    system_metrics = get_system_metrics()
    openclaw_metrics = get_openclaw_metrics()
    
    # 合并指标
    all_metrics = {}
    all_metrics.update(system_metrics)
    all_metrics.update(openclaw_metrics)
    
    # 添加模拟的Agent指标（用于演示）
    all_metrics['agent.cpu.percent'] = system_metrics.get('system.cpu.usage', 0) * 0.5
    all_metrics['agent.memory.percent'] = system_metrics.get('system.memory.usage', 0) * 0.6
    all_metrics['agent.queue.pending'] = 0
    all_metrics['agent.tasks.failure_rate'] = 0
    all_metrics['agent.latency.p99'] = 100
    
    print(f"  指标数: {len(all_metrics)}")
    
    # 检查规则
    alerts = engine.check(all_metrics)
    
    if alerts:
        print(f"\n⚠️  触发 {len(alerts)} 条告警:")
        for alert in alerts:
            level_emoji = {
                'CRITICAL': '🔴',
                'WARNING': '🟡',
                'INFO': '🔵'
            }.get(alert.get('level', 'INFO'), '⚪')
            
            print(f"  {level_emoji} [{alert['level']}] {alert['message']}")
            
            # 记录到日志
            log_path = "/root/.openclaw/workspace/ultron/agents/alerts/alerts.log"
            with open(log_path, 'a') as f:
                f.write(f"{datetime.now().isoformat()} [{alert['level']}] {alert['message']}\n")
        
        # 🚀 发送通知到所有渠道
        print(f"\n📤 发送通知到 {len(notifier.channels)} 个渠道...")
        results = notifier.notify(alerts)
        
        print(f"  ✅ 发送完成: {results['total']} 条告警")
        for ch_name, stats in results.get('channels', {}).items():
            status = "✅" if stats['sent'] > 0 else "⚪"
            print(f"    {status} {ch_name}: {stats['sent']} 成功 / {stats['failed']} 失败")
        
        if results.get('failed'):
            print(f"  ⚠️ 失败渠道: {', '.join(results['failed'])}")
    else:
        print("  ✅ 无告警触发")
    
    # 统计
    summary = engine.get_alert_summary()
    print(f"\n📊 统计: {summary.get('firing_count', 0)} 活跃 / {summary.get('total_alerts', 0)} 总计")


if __name__ == "__main__":
    main()