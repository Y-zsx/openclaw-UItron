#!/usr/bin/env python3
"""
Secure Channel CLI - 安全通道命令行工具
"""

import requests
import json
import sys
import argparse

BASE_URL = "http://localhost:8091"

def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

def cmd_health(args):
    """健康检查"""
    r = requests.get(f"{BASE_URL}/health")
    print_json(r.json())

def cmd_create(args):
    """创建通道"""
    data = {
        "agent_a": args.agent_a,
        "agent_b": args.agent_b,
        "encryption": args.encryption
    }
    r = requests.post(f"{BASE_URL}/api/channels", json=data)
    print_json(r.json())

def cmd_list(args):
    """列出通道"""
    r = requests.get(f"{BASE_URL}/api/channels")
    result = r.json()
    if result.get('channels'):
        print_json(result)
    else:
        print("No channels found")

def cmd_info(args):
    """通道详情"""
    r = requests.get(f"{BASE_URL}/api/channels/{args.channel_id}")
    if r.status_code == 404:
        print(f"Channel {args.channel_id} not found")
    else:
        print_json(r.json())

def cmd_close(args):
    """关闭通道"""
    r = requests.delete(f"{BASE_URL}/api/channels/{args.channel_id}")
    print_json(r.json())

def cmd_send(args):
    """发送消息"""
    data = {
        "sender": args.sender,
        "recipient": args.recipient,
        "message": args.message
    }
    r = requests.post(f"{BASE_URL}/api/channels/{args.channel_id}/messages", json=data)
    print_json(r.json())

def cmd_stats(args):
    """统计信息"""
    r = requests.get(f"{BASE_URL}/api/stats")
    print_json(r.json())

def main():
    parser = argparse.ArgumentParser(description='Secure Channel CLI')
    sub = parser.add_subparsers()
    
    sub.add_parser('health', help='Health check')
    
    p_create = sub.add_parser('create', help='Create channel')
    p_create.add_argument('agent_a', help='Agent A ID')
    p_create.add_argument('agent_b', help='Agent B ID')
    p_create.add_argument('--encryption', default='e2e', help='Encryption type')
    
    sub.add_parser('list', help='List channels')
    
    p_info = sub.add_parser('info', help='Channel info')
    p_info.add_argument('channel_id', help='Channel ID')
    
    p_close = sub.add_parser('close', help='Close channel')
    p_close.add_argument('channel_id', help='Channel ID')
    
    p_send = sub.add_parser('send', help='Send message')
    p_send.add_argument('channel_id', help='Channel ID')
    p_send.add_argument('sender', help='Sender ID')
    p_send.add_argument('recipient', help='Recipient ID')
    p_send.add_argument('message', help='Message content')
    
    sub.add_parser('stats', help='Statistics')
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()