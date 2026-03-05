#!/usr/bin/env python3
"""
安全加固CLI工具
用法: python security_cli.py <command> [options]
"""
import sys
import json
import argparse
from security_layer import get_security_config, get_auditor, SECURITY_HEADERS

def cmd_key(args):
    cfg = get_security_config()
    if args.list:
        print("=== API密钥列表 ===")
        for name, data in cfg.api_keys.items():
            print(f"  {name}: {data['key'][:16]}... (创建于: {data['created']})")
    elif args.add:
        key = cfg.add_api_key(args.add)
        print(f"✅ 新密钥 '{args.add}': {key}")
    elif args.remove:
        if args.remove in cfg.api_keys:
            del cfg.api_keys[args.remove]
            cfg._save_config()
            print(f"✅ 已删除密钥: {args.remove}")
        else:
            print(f"❌ 密钥不存在: {args.remove}")
    else:
        print("用法: --list | --add <name> | --remove <name>")

def cmd_rate(args):
    cfg = get_security_config()
    if args.list:
        print("=== 速率限制规则 ===")
        for endpoint, (limit, window) in cfg.rate_limits.items():
            print(f"  {endpoint}: {limit}请求/{window}秒")
    elif args.set:
        limit, window = map(int, args.set.split('/'))
        cfg.rate_limits[args.endpoint] = (limit, window)
        cfg._save_config()
        print(f"✅ 已设置 {args.endpoint}: {limit}请求/{window}秒")
    else:
        print("用法: --list | --set <endpoint> <limit>/<window>")

def cmd_audit(args):
    auditor = get_auditor()
    hours = args.hours or 24
    event_type = args.event
    
    logs = auditor.get_recent_logs(hours=hours, event_type=event_type)
    print(f"=== 最近{hours}小时审计日志 ({len(logs)}条) ===")
    
    if args.json:
        print(json.dumps(logs, indent=2, ensure_ascii=False))
    else:
        for log in logs[-20:]:  # 只显示最近20条
            print(f"  [{log['timestamp'][:19]}] {log['severity']}: {log['event']} - {log['endpoint']}")

def cmd_headers(args):
    print("=== 安全响应头 ===")
    for header, value in SECURITY_HEADERS.items():
        print(f"  {header}: {value}")

def main():
    parser = argparse.ArgumentParser(description="奥创安全加固CLI")
    subparsers = parser.add_subparsers()
    
    # API密钥管理
    p_key = subparsers.add_parser('key', help="API密钥管理")
    p_key.add_argument('--list', action='store_true', help="列出所有密钥")
    p_key.add_argument('--add', metavar='NAME', help="添加新密钥")
    p_key.add_argument('--remove', metavar='NAME', help="删除密钥")
    p_key.set_defaults(func=cmd_key)
    
    # 速率限制
    p_rate = subparsers.add_parser('rate', help="速率限制管理")
    p_rate.add_argument('--list', action='store_true', help="列出所有规则")
    p_rate.add_argument('--set', metavar='ENDPOINT', help="设置规则 (格式: endpoint limit/window)")
    p_rate.add_argument('endpoint', nargs='?', help="端点路径")
    p_rate.set_defaults(func=cmd_rate)
    
    # 审计日志
    p_audit = subparsers.add_parser('audit', help="审计日志查看")
    p_audit.add_argument('--hours', type=int, help="查看最近N小时")
    p_audit.add_argument('--event', help="过滤事件类型")
    p_audit.add_argument('--json', action='store_true', help="JSON格式输出")
    p_audit.set_defaults(func=cmd_audit)
    
    # 安全头
    p_headers = subparsers.add_parser('headers', help="显示安全响应头")
    p_headers.set_defaults(func=cmd_headers)
    
    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()