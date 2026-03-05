#!/usr/bin/env python3
"""
Reincarnation Status Script - 转世状态查看脚本

这个脚本被 ultron-reincarnate.py 调用，返回当前转世状态
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
            
            incarnation = state.get('current_incarnation', 0)
            ambition = state.get('current_ambition', 'unknown')
            task = state.get('current_task', 'N/A')
            
            print(f"第{incarnation}世 | {ambition} | {task} | working")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()