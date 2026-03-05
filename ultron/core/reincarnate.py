#!/usr/bin/env python3
"""
Reincarnation Status Script - 转世状态查看脚本

这个脚本被 ultron-reincarnate.py 调用，返回当前转世状态
使用夙愿前缀计数 (v3格式)
"""
import json
import sys
from datetime import datetime, timezone

WORKSPACE = "/root/.openclaw/workspace"
STATE_FILE = f"{WORKSPACE}/ultron-workflow/state.json"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if cmd == "status":
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            
            # v3格式: ambition.id + life count
            ambition = state.get('ambition', {})
            ambition_id = ambition.get('id', 0)
            ambition_name = ambition.get('name', 'unknown')
            life_count = ambition.get('count', 1)
            
            task = state.get('this_life', {}).get('task', 'N/A')
            
            print(f"夙愿{ambition_id} | {ambition_name} | 任务{life_count} | {task}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()