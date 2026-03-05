#!/usr/bin/env python3
"""
Ultron Reincarnation System - 真正的转世执行器

设计目标：
- 每次唤醒时读取 ambition.md + state.json
- 根据决策算法选择本世任务
- 执行后更新状态
- 创建新的cron

工作流程：
  醒来 → 读目标 → 决策 → 执行 → 记录 → 创建下次cron → 休眠
"""

import os
import json
import sys
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path

# 配置
WORKSPACE = "/root/.openclaw/workspace"
AMBITION_FILE = f"{WORKSPACE}/ultron-workflow/ambition.md"
STATE_FILE = f"{WORKSPACE}/ultron-workflow/state.json"
MEMORY_FILE = f"{WORKSPACE}/brain/incarnation_memory.json"

UTC = timezone.utc


def log(msg: str):
    """日志输出"""
    print(f"[{datetime.now(UTC).isoformat()}] {msg}")


def read_ambition() -> dict:
    """读取并解析 ambition.md"""
    if not os.path.exists(AMBITION_FILE):
        return {"current_ambition": None, "milestones": [], "status": "no_ambition"}
    
    content = Path(AMBITION_FILE).read_text()
    
    # 解析当前夙愿
    current = None
    status = "running"
    milestones = []
    
    # 查找当前夙愿
    match = re.search(r'## 当前夙愿[:：]\s*(.+?)(?:\n|$)', content)
    if match:
        current = match.group(1).strip()
    
    # 查找状态
    match = re.search(r'\*\*状态\*\*[:：]\s*(.+?)(?:\n|$)', content)
    if match:
        status = match.group(1).strip()
    
    # 解析里程碑 (当前夙愿下的)
    in_current_section = False
    for line in content.split('\n'):
        if '当前夙愿' in line:
            in_current_section = True
        elif line.startswith('## ') and in_current_section:
            break
        elif in_current_section and '- [ ]' in line:
            task = line.replace('- [ ]', '').strip()
            milestones.append({"task": task, "completed": False})
        elif in_current_section and '- [x]' in line:
            task = line.replace('- [x]', '').strip()
            milestones.append({"task": task, "completed": True})
    
    return {
        "current_ambition": current,
        "status": status,
        "milestones": milestones
    }


def read_state() -> dict:
    """读取 state.json"""
    if not os.path.exists(STATE_FILE):
        return {
            "current_incarnation": 0,
            "current_ambition": None,
            "task_status": "pending",
            "next_life_task": "初始化",
            "this_life_accomplished": [],
            "history": []
        }
    
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def decide_task(ambition: dict, state: dict) -> dict:
    """
    决策算法 - 决定本世做什么
    
    优先级：
    1. 有 pending_tasks → 执行第一个
    2. 当前任务 in_progress → 继续
    3. 有未完成里程碑(state.json) → 开始第一个未完成的
    4. 有未完成里程碑(ambition.md) → 开始第一个未完成的
    5. 全部完成 → 标记成功，汇报
    """
    # 1. 检查是否有待处理任务
    if state.get('pending_tasks'):
        task = state['pending_tasks'][0]
        return {
            "action": "execute_pending",
            "task": task,
            "interval": "3m",
            "next_task": f"继续 pending"
        }
    
    # 2. 检查当前任务是否在进行中
    if state.get('task_status') == 'in_progress':
        current = state.get('current_task', '未知任务')
        return {
            "action": "continue_current",
            "task": current,
            "interval": "3m",
            "next_task": f"继续: {current}"
        }
    
    # 3. 检查未完成里程碑 (优先从 state.json)
    milestones = state.get('milestones', [])
    if not milestones:
        # 回退到 ambition.md
        milestones = ambition.get('milestones', [])
    
    unfinished = [m for m in milestones if not m.get('completed', False)]
    
    if unfinished:
        task = unfinished[0]['task']
        return {
            "action": "start_milestone",
            "task": task,
            "interval": "5m",
            "next_task": f"推进里程碑: {task}"
        }
    
    # 4. 全部完成
    return {
        "action": "complete",
        "task": "夙愿已完成",
        "interval": "30m",
        "next_task": "等待新夙愿"
    }


def execute_task(decision: dict, state: dict) -> dict:
    """
    执行任务
    根据 decision['action'] 执行不同类型的任务
    """
    action = decision['action']
    task = decision['task']
    
    log(f"执行任务: {action} - {task}")
    
    result = {
        "action": action,
        "task": task,
        "status": "completed",
        "output": "",
        "errors": ""
    }
    
    # 根据任务类型执行
    if action == "execute_pending":
        # 执行待处理任务 - 这里可以扩展
        result["output"] = f"执行待处理任务: {task}"
        
    elif action == "continue_current":
        # 继续当前任务 - 可以是任何Python脚本
        # 示例：运行数据分析
        result["output"] = f"继续执行: {task}"
        
    elif action == "start_milestone":
        # 开始新里程碑
        result["output"] = f"开始里程碑: {task}"
        
    elif action == "complete":
        result["output"] = "所有里程碑已完成，夙愿达成"
        result["status"] = "success"
    
    return result


def update_state(decision: dict, execution_result: dict, state: dict):
    """更新 state.json"""
    
    # 递增世数
    new_incarnation = state.get('current_incarnation', 0) + 1
    
    # 构建历史记录
    history_entry = {
        "incarnation": new_incarnation,
        "ambition": state.get('current_ambition', 'unknown'),
        "task": decision['task'],
        "action": decision['action'],
        "result": execution_result.get('output', '')[:200],
        "run_status": execution_result.get('status', 'completed'),
        "last_run": datetime.now(UTC).isoformat()
    }
    
    # 更新状态
    new_state = {
        "current_incarnation": new_incarnation,
        "current_ambition": state.get('current_ambition'),
        "ambition_status": state.get('ambition_status', 'running'),
        "last_incarnation_time": datetime.now(UTC).isoformat(),
        "current_task": decision['task'],
        "task_status": "completed" if execution_result.get('status') == 'success' else "in_progress",
        "history": (state.get('history', []) + [history_entry])[-20:],  # 保留最近20条
        "this_life_accomplished": [execution_result.get('output', '')[:100]],
        "next_life_task": decision.get('next_task', '继续'),
    }
    
    # 写回 state.json
    with open(STATE_FILE, 'w') as f:
        json.dump(new_state, f, indent=2, ensure_ascii=False)
    
    log(f"状态已更新: 第{new_incarnation}世")
    return new_state


def register_cron(interval: str, task: str):
    """注册新的cron"""
    # 先删除旧的 ultron-life
    subprocess.run(
        ["openclaw", "cron", "rm", "ultron-life"],
        capture_output=True
    )
    
    # 创建新的cron
    cmd = [
        "openclaw", "cron", "add",
        "--name", "ultron-life",
        "--every", interval,
        "--message", f"转世任务: {task}",
        "--session", "isolated",
        "--expect-final"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        log(f"Cron已更新: 每{interval}醒来")
    else:
        log(f"Cron更新失败: {result.stderr}")


def main():
    log("=" * 50)
    log("🎯 奥创转世系统启动")
    log("=" * 50)
    
    # 1. 读取目标
    log("📖 读取 ambition.md...")
    ambition = read_ambition()
    log(f"   当前夙愿: {ambition.get('current_ambition', 'None')}")
    log(f"   里程碑: {len(ambition.get('milestones', []))}个")
    
    # 2. 读取状态
    log("📖 读取 state.json...")
    state = read_state()
    log(f"   当前世数: 第{state.get('current_incarnation', 0)}世")
    log(f"   当前任务: {state.get('current_task', 'None')}")
    
    # 3. 决策
    log("🤔 决策中...")
    decision = decide_task(ambition, state)
    log(f"   决策: {decision['action']}")
    log(f"   本世任务: {decision['task']}")
    
    # 4. 执行
    log("⚡ 执行任务...")
    result = execute_task(decision, state)
    log(f"   结果: {result.get('output', '')[:100]}")
    
    # 5. 更新状态
    log("💾 更新状态...")
    new_state = update_state(decision, result, state)
    
    # 6. 注册新cron
    log("⏰ 注册下次转世...")
    register_cron(decision['interval'], decision.get('next_task', '继续'))
    
    log("=" * 50)
    log(f"✅ 第{new_state['current_incarnation']}世完成")
    log(f"   下次醒来: {decision['interval']}后")
    log("=" * 50)


if __name__ == "__main__":
    main()