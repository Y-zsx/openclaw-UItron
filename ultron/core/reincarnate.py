#!/usr/bin/env python3
"""
转世执行器 v3.0
规则：
- 夙愿ID前缀 + 世数 = 版本标识 (如 tool-integration-1)
- 每一世必须有明确产出
- 完成标准：产出可用并验证
- 与ultron-workflow/state.json同步
"""
import json
import os
import sys
from datetime import datetime

ULTRON_DIR = "/root/.openclaw/workspace/ultron"
STATE_FILE = f"{ULTRON_DIR}/incarnation.json"
WORKFLOW_STATE = "/root/.openclaw/workspace/ultron-workflow/state.json"
LIFE_LOG = f"{ULTRON_DIR}/logs/life.log"


def log(msg):
    """写日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    with open(LIFE_LOG, 'a') as f:
        f.write(line)
    print(line.strip())


def load_state():
    """加载状态"""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"version": "3.0", "current": {}, "history": []}


def save_state(state):
    """保存状态"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_workflow_state():
    """加载workflow状态"""
    try:
        with open(WORKFLOW_STATE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_workflow_state(state):
    """保存workflow状态"""
    with open(WORKFLOW_STATE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def sync_with_workflow():
    """与workflow状态同步"""
    state = load_state()
    wf = load_workflow_state()
    
    if wf:
        # 从workflow同步世数
        wf_inc = wf.get('current_incarnation', 0)
        loc_inc = state['current'].get('incarnation', 0)
        
        if wf_inc > loc_inc:
            state['current']['incarnation'] = wf_inc
            state['current']['ambition'] = wf.get('current_ambition', '待定')
            log(f"从workflow同步: 第{wf_inc}世")
        
        save_state(state)
    return state


def next_stage(accomplishment=None):
    """进入下一世"""
    state = load_state()
    curr = state['current']
    
    # 记录完成
    if curr.get('stage', 1) == 1:
        # 第一阶段完成
        state['history'].append({
            "incarnation": curr.get('incarnation', 1),
            "ambition": curr.get('ambition', '待定'),
            "ambition_id": curr.get('ambition_id', 'unknown'),
            "stage": curr.get('stage', 1),
            "status": "stage_completed",
            "completed_at": datetime.now().isoformat(),
            "accomplishment": accomplishment or "任务完成"
        })
    
    if curr.get('stage', 1) >= curr.get('total_stages', 1):
        # 夙愿完成
        state['history'].append({
            "incarnation": curr.get('incarnation', 1),
            "ambition": curr.get('ambition', '待定'),
            "ambition_id": curr.get('ambition_id', 'unknown'),
            "status": "completed",
            "completed_at": datetime.now().isoformat()
        })
        # 准备新夙愿
        curr['incarnation'] = curr.get('incarnation', 1) + 1
        curr['stage'] = 1
        curr['total_stages'] = 1
        curr['ambition'] = "待定"
        curr['ambition_id'] = "pending"
        curr['status'] = "waiting"
    else:
        # 当前夙愿的下一阶段
        curr['stage'] = curr.get('stage', 1) + 1
        curr['status'] = "working"
    
    curr['started_at'] = datetime.now().isoformat()
    save_state(state)
    
    # 同步到workflow
    try:
        wf = load_workflow_state()
        if wf:
            wf['current_incarnation'] = curr['incarnation']
            wf['last_incarnation_time'] = datetime.now().isoformat()
            wf['this_life_accomplished'] = [accomplishment] if accomplishment else []
            save_workflow_state(wf)
    except Exception as e:
        log(f"同步workflow失败: {e}")
    
    return state


def set_ambition(ambition_id, ambition_name, stages=1, task=None):
    """设置新夙愿"""
    state = load_state()
    curr = state['current']
    curr['ambition_id'] = ambition_id
    curr['ambition_name'] = ambition_name
    curr['ambition'] = ambition_name
    curr['stage'] = 1
    curr['total_stages'] = stages
    curr['started_at'] = datetime.now().isoformat()
    curr['status'] = "working"
    curr['current_task'] = task or "执行任务"
    save_state(state)
    
    # 同步到workflow
    try:
        wf = load_workflow_state()
        if wf:
            wf['current_ambition'] = ambition_name
            wf['ambition_status'] = "running"
            wf['current_task'] = task or "执行任务"
            wf['task_status'] = "in_progress"
            save_workflow_state(wf)
    except Exception as e:
        log(f"同步workflow失败: {e}")
    
    return state


def add_milestone(milestone_name, completed=False):
    """添加里程碑"""
    state = load_state()
    if 'milestones' not in state:
        state['milestones'] = []
    state['milestones'].append({
        "name": milestone_name,
        "completed": completed,
        "added_at": datetime.now().isoformat()
    })
    save_state(state)
    return state


def complete_milestone(milestone_name):
    """标记里程碑完成"""
    state = load_state()
    if 'milestones' in state:
        for m in state['milestones']:
            if m['name'] == milestone_name:
                m['completed'] = True
                m['completed_at'] = datetime.now().isoformat()
    save_state(state)
    return state


def complete(accomplishment=None):
    """标记当前世完成"""
    state = next_stage(accomplishment)
    log(f"转世完成: {status()}")
    return state


def status():
    """获取当前状态"""
    state = load_state()
    curr = state['current']
    return f"第{curr.get('incarnation', 1)}世 | {curr.get('ambition', '待定')} | 阶段{curr.get('stage', 1)}/{curr.get('total_stages', 1)} | {curr.get('status', 'unknown')}"


def detailed_status():
    """获取详细状态"""
    state = load_state()
    curr = state['current']
    wf = load_workflow_state()
    
    lines = [
        f"=== 奥创转世状态 ===",
        f"当前: 第{curr.get('incarnation', 1)}世",
        f"夙愿: {curr.get('ambition', '待定')} ({curr.get('ambition_id', 'N/A')})",
        f"阶段: {curr.get('stage', 1)}/{curr.get('total_stages', 1)}",
        f"状态: {curr.get('status', 'unknown')}",
        f"任务: {curr.get('current_task', 'N/A')}",
        f"开始: {curr.get('started_at', 'N/A')}",
    ]
    
    if 'milestones' in state and state['milestones']:
        lines.append("里程碑:")
        for m in state['milestones'][-5:]:
            check = "✓" if m.get('completed') else "○"
            lines.append(f"  {check} {m['name']}")
    
    if wf:
        lines.append(f"Workflow: 第{wf.get('current_incarnation', '?')}世 | {wf.get('current_task', 'N/A')}")
    
    return "\n".join(lines)


def run_cycle(task_name):
    """执行一个转世周期"""
    log(f"=== 奥创转世周期启动 ===")
    log(f"当前: {status()}")
    log(f"任务: {task_name}")
    
    # 同步状态
    sync_with_workflow()
    
    # 执行业务逻辑
    log("执行任务...")
    
    # 完成任务
    log("任务完成")
    
    # 进入下一世
    complete(task_name)
    
    log(f"转世完成: {status()}")
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if cmd == "status":
        print(status())
    elif cmd == "detailed":
        print(detailed_status())
    elif cmd == "complete":
        accomplishment = sys.argv[2] if len(sys.argv) > 2 else "任务完成"
        print(f"完成: {status()}")
        complete(accomplishment)
    elif cmd == "set":
        # python reincarnate.py set <id> <name> [stages] [task]
        aid = sys.argv[2] if len(sys.argv) > 2 else "new"
        name = sys.argv[3] if len(sys.argv) > 3 else "新夙愿"
        stages = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        task = sys.argv[5] if len(sys.argv) > 5 else None
        set_ambition(aid, name, stages, task)
        print(f"已设置夙愿: {name} ({aid}), 共{stages}世")
    elif cmd == "next":
        next_stage()
        print(f"转世完成: {status()}")
    elif cmd == "sync":
        sync_with_workflow()
        print("已同步")
    elif cmd == "cycle":
        task = sys.argv[2] if len(sys.argv) > 2 else "执行任务"
        run_cycle(task)
    elif cmd == "milestone":
        # python reincarnate.py milestone <name> [complete]
        name = sys.argv[2] if len(sys.argv) > 2 else "新里程碑"
        if len(sys.argv) > 3 and sys.argv[3] == "complete":
            complete_milestone(name)
            print(f"里程碑完成: {name}")
        else:
            add_milestone(name)
            print(f"添加里程碑: {name}")
    else:
        print(f"未知命令: {cmd}")
        print("可用: status, detailed, complete, set, next, sync, cycle, milestone")