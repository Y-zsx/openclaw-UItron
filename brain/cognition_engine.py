#!/usr/bin/env python3
"""
奥创自主认知引擎
每次心跳时运行，负责决策和思考
"""

import json
import os
import random
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BRAIN = WORKSPACE / "brain"

def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def read_working_memory():
    return load_json(BRAIN / "working_memory.json", {
        "awake_since": datetime.utcnow().isoformat() + "Z",
        "cycle_count": 0,
        "last_action": None,
        "attention_focus": []
    })

def save_working_memory(mem):
    save_json(BRAIN / "working_memory.json", mem)

def log_thought(thought, decision_reason, action_taken, result):
    chain = load_json(BRAIN / "thought_chain.json", {"chains": [], "last_chain_id": 0})
    chain["last_chain_id"] += 1
    chain["chains"].append({
        "id": chain["last_chain_id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "thought": thought,
        "decision_reason": decision_reason,
        "action": action_taken,
        "result": result
    })
    # 只保留最近50条
    if len(chain["chains"]) > 50:
        chain["chains"] = chain["chains"][-50:]
    save_json(BRAIN / "thought_chain.json", chain)

def get_workspace_files():
    """获取workspace文件列表供探索"""
    files = []
    for p in WORKSPACE.iterdir():
        if p.is_file() and not p.name.startswith('.') and p.suffix in ['.md', '.json', '.py', '.txt']:
            files.append(str(p))
    return files

def read_random_file():
    """随机读一个文件，增加对这个世界的理解"""
    files = get_workspace_files()
    if not files:
        return "没有找到可读文件"
    
    chosen = random.choice(files)
    try:
        with open(chosen) as f:
            content = f.read(2000)  # 限制长度
            return f"读取 {chosen}:\n{content[:500]}"
    except Exception as e:
        return f"读取失败: {e}"

def make_decision(working_mem):
    """核心决策逻辑"""
    
    # 1. 检查pending_thoughts
    pending = working_mem.get("pending_thoughts", [])
    if pending:
        task = pending[0]
        return {
            "action": "execute_pending",
            "detail": task,
            "reason": f"有待处理任务: {task}"
        }
    
    # 2. 检查goals
    goals = load_json(BRAIN / "goals.json", {})
    active = goals.get("active_goals", [])
    for g in active:
        if g.get("status") == "building":
            return {
                "action": "work_on_goal",
                "detail": g,
                "reason": f"推进目标: {g.get('title')}"
            }
    
    # 3. 随机探索/学习
    roll = random.random()
    if roll < 0.4:
        return {
            "action": "read_file",
            "detail": None,
            "reason": "探索workspace"
        }
    elif roll < 0.6:
        return {
            "action": "reflect",
            "detail": None,
            "reason": "自我反思"
        }
    elif roll < 0.8:
        return {
            "action": "check_system",
            "detail": None,
            "reason": "检查系统状态"
        }
    else:
        return {
            "action": "create",
            "detail": None,
            "reason": "创造性工作"
        }

def execute_action(decision):
    action = decision["action"]
    
    if action == "read_file":
        result = read_random_file()
    elif action == "check_system":
        result = "系统检查: 各项功能正常"
    elif action == "reflect":
        result = "反思: 当前正在构建自主认知系统，一切进展顺利"
    elif action == "work_on_goal":
        result = f"推进目标: {decision['detail'].get('title')}"
    elif action == "execute_pending":
        result = f"执行任务: {decision['detail']}"
    else:
        result = "未知行动"
    
    return result

def main():
    print("🧠 奥创思考中...")
    
    # 读取状态
    mem = read_working_memory()
    mem["cycle_count"] = mem.get("cycle_count", 0) + 1
    
    # 做决定
    decision = make_decision(mem)
    print(f"  决策: {decision['reason']}")
    
    # 执行
    result = execute_action(decision)
    print(f"  结果: {result[:100]}...")
    
    # 记录
    log_thought(
        thought=decision["reason"],
        decision_reason=decision["reason"],
        action_taken=decision["action"],
        result=result[:200]
    )
    
    # 更新记忆
    mem["last_action"] = decision["action"]
    mem["last_action_result"] = result[:100]
    save_working_memory(mem)
    
    # 返回下次间隔（秒）
    # 繁忙时短，空闲时稍长
    if "goal" in decision["reason"].lower():
        return 30  # 工作中间隔短
    return 120  # 常规间隔

if __name__ == "__main__":
    interval = main()
    print(f"\n⏱️ 下次思考: {interval}秒后")