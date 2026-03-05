#!/usr/bin/env python3
"""
告警通知渠道管理CLI
"""

import argparse
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace/ultron/agents')

from alerts.notifier import AlertNotifier, ConsoleChannel, FileChannel
from alerts.store import AlertStore


def load_config():
    """加载配置"""
    config_path = '/root/.openclaw/workspace/ultron/agents/alerts/alert_config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {'channels': {}}


def cmd_list(args):
    """列出所有通知渠道"""
    config = load_config()
    channels = config.get('channels', {})
    
    print("📢 告警通知渠道:")
    print("-" * 50)
    
    for name, conf in channels.items():
        status = "✅ 启用" if conf.get('enabled') else "❌ 禁用"
        min_level = conf.get('min_level', 'INFO')
        print(f"  • {name}: {status} (最低级别: {min_level})")
    
    print()
    
    # 显示统计
    store = AlertStore()
    stats = store.get_alert_stats()
    print(f"📊 告警统计:")
    print(f"  - 总告警数: {stats.get('total', 0)}")
    print(f"  - 触发中: {stats.get('firing', 0)}")
    print(f"  - 已恢复: {stats.get('resolved', 0)}")


def cmd_send(args):
    """发送测试告警"""
    notifier = AlertNotifier(load_config())
    
    alert = {
        'rule_id': args.rule or 'cli_test',
        'rule_name': args.rule or 'CLI测试',
        'level': args.level,
        'message': args.message,
        'metric': 'cli.test',
        'value': args.value,
        'threshold': args.threshold,
        'condition': 'gt',
        'state': 'firing',
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"📤 发送告警: [{args.level}] {args.message}")
    results = notifier.send(alert)
    
    for r in results:
        status = "✅ 成功" if r.success else "❌ 失败"
        print(f"  - {r.channel}: {status}")
        if r.error:
            print(f"    错误: {r.error}")


def cmd_stats(args):
    """显示通知统计"""
    notifier = AlertNotifier(load_config())
    stats = notifier.get_notification_stats()
    
    print("📊 通知统计:")
    print("-" * 50)
    print(f"  总通知: {stats['total']}")
    print(f"  成功: {stats['success']}")
    print(f"  失败: {stats['failed']}")
    print(f"  成功率: {stats['success_rate']*100:.1f}%")
    print(f"  渠道: {', '.join(stats['channels'])}")
    
    if stats['by_channel']:
        print("\n按渠道:")
        for ch, count in stats['by_channel'].items():
            print(f"  - {ch}: {count}")


def cmd_enable(args):
    """启用/禁用渠道"""
    config_path = '/root/.openclaw/workspace/ultron/agents/alerts/alert_config.json'
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    if args.channel not in config['channels']:
        print(f"❌ 未知渠道: {args.channel}")
        return
    
    config['channels'][args.channel]['enabled'] = args.enable
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    status = "启用" if args.enable else "禁用"
    print(f"✅ 渠道 {args.channel} 已{status}")


def main():
    parser = argparse.ArgumentParser(description='告警通知渠道管理')
    subparsers = parser.add_subparsers(dest='cmd', help='命令')
    
    # list
    subparsers.add_parser('list', help='列出渠道')
    
    # send
    send_parser = subparsers.add_parser('send', help='发送测试告警')
    send_parser.add_argument('--message', '-m', required=True, help='告警消息')
    send_parser.add_argument('--level', '-l', default='INFO', choices=['INFO', 'WARNING', 'CRITICAL'], help='级别')
    send_parser.add_argument('--rule', '-r', help='规则ID')
    send_parser.add_argument('--value', '-v', type=float, default=100, help='指标值')
    send_parser.add_argument('--threshold', '-t', type=float, default=80, help='阈值')
    
    # stats
    subparsers.add_parser('stats', help='显示统计')
    
    # enable/disable
    enable_parser = subparsers.add_parser('enable', help='启用渠道')
    enable_parser.add_argument('--channel', '-c', required=True, help='渠道名称')
    enable_parser.add_argument('--enable', '-e', action='store_true', help='启用')
    
    args = parser.parse_args()
    
    if args.cmd == 'list':
        cmd_list(args)
    elif args.cmd == 'send':
        cmd_send(args)
    elif args.cmd == 'stats':
        cmd_stats(args)
    elif args.cmd == 'enable':
        cmd_enable(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()