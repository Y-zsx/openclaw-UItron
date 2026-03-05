#!/usr/bin/env python3
"""
转世执行器 v2.0
规则：
- 夙愿ID前缀 + 世数 = 版本标识 (如 tool-integration-1)
- 每一世必须有明确产出
- 完成标准：产出可用并验证
"""
import json
import os
from datetime import datetime

ULTRON_DIR = "/root/.openclaw/workspace/ultron"
STATE_FILE = f"{ULTRON_DIR}/incarnation.json"


def load_state():
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def next_stage():
    """进入下一世"""
    state = load_state()
    curr = state['current']
    
    if curr['stage'] >= curr['total_stages']:
        # 夙愿完成，记录并准备新夙愿
        state['history'].append({
            "incarnation": curr['incarnation'],
            "ambition": curr['ambition'],
            "ambition_id": curr['ambition_id'],
            "status": "completed",
            "completed_at": datetime.now().isoformat()
        })
        curr['incarnation'] += 1
        curr['stage'] = 1
        curr['total_stages'] = 1
        curr['ambition'] = "待定"
        curr['ambition_id'] = "pending"
        curr['status'] = "waiting"
    else:
        # 当前夙愿的下一世
        curr['stage'] += 1
    
    curr['started_at'] = datetime.now().isoformat()
    save_state(state)
    return state


def set_ambition(ambition_id, ambition_name, stages=1):
    """设置新夙愿"""
    state = load_state()
    curr = state['current']
    curr['ambition_id'] = ambition_id
    curr['ambition_name'] = ambition_name
    curr['stage'] = 1
    curr['total_stages'] = stages
    curr['started_at'] = datetime.now().isoformat()
    curr['status'] = "working"
    save_state(state)
    return state


def complete():
    """标记当前世完成"""
    return next_stage()


def status():
    """获取当前状态"""
    state = load_state()
    curr = state['current']
    return f"第{curr['incarnation']}世 | {curr['ambition']} | 阶段{curr['stage']}/{curr['total_stages']} | {curr['status']}"


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if cmd == "status":
        print(status())
    elif cmd == "complete":
        print(f"完成: {status()}")
        next_stage()
    elif cmd == "set":
        # python reincarnate.py set <id> <name> [stages]
        aid = sys.argv[2] if len(sys.argv) > 2 else "new"
        name = sys.argv[3] if len(sys.argv) > 3 else "新夙愿"
        stages = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        set_ambition(aid, name, stages)
        print(f"已设置夙愿: {name} ({aid}), 共{stages}世")
    elif cmd == "next":
        next_stage()
        print(f"转世完成: {status()}")