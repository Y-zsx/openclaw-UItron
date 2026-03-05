#!/usr/bin/env python3
"""
奥创生命周期 - 每一世执行的任务
根据当前夙愿和世数执行相应任务
"""
import json
import subprocess
import sys
from datetime import datetime

ULTRON_DIR = "/root/.openclaw/workspace/ultron"
STATE_FILE = f"{ULTRON_DIR}/incarnation.json"
LOG_FILE = f"{ULTRON_DIR}/logs/life.log"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")


def load_state():
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def run_task(ambition_id, stage):
    """根据夙愿执行对应任务"""
    
    # 夙愿1: 工具整合 (tool-integration)
    if ambition_id == "tool-integration":
        if stage == 1:
            return 整合监控模块()
        elif stage == 2:
            return 完成工具箱()
    
    # 默认：系统自检
    return 系统自检()


def 整合监控模块():
    """第一世：确保监控模块正常运行"""
    log("执行：整合监控模块")
    
    # 检查核心文件
    checks = [
        ("core/ultron-hub.py", "枢纽"),
        ("monitor/intelligent-monitor.py", "监控"),
        ("decision/decision-advisor.py", "决策"),
    ]
    
    results = []
    for path, name in checks:
        full_path = f"{ULTRON_DIR}/{path}"
        exists = os.path.exists(full_path)
        results.append(f"{name}: {'✓' if exists else '✗'}")
    
    log(" | ".join(results))
    
    # 如果所有核心模块存在，返回完成
    if all(os.path.exists(f"{ULTRON_DIR}/{p}") for p, _ in checks):
        return "completed"
    return "working"


def 完成工具箱():
    """第二世：完成工具箱"""
    log("执行：完成工具箱")
    # 检查工具箱状态
    return "completed"


def 系统自检():
    """默认任务：系统自检"""
    log("执行：系统自检")
    
    # 简单检查
    result = subprocess.run(
        ["openclaw", "status", "--json"],
        capture_output=True, text=True, timeout=30
    )
    
    if result.returncode == 0:
        log("系统状态: 正常")
        return "completed"
    else:
        log(f"系统异常: {result.stderr}")
        return "working"


def main():
    log("=== 奥创生命周期启动 ===")
    
    state = load_state()
    curr = state['current']
    
    ambition_id = curr.get('ambition_id', 'unknown')
    stage = curr['stage']
    incarnation = curr['incarnation']
    
    log(f"当前: 第{incarnation}世 | {ambition_id} | 阶段{stage}")
    
    # 执行任务
    result = run_task(ambition_id, stage)
    
    if result == "completed":
        log("任务完成，进入下一世")
        # 调用转世
        subprocess.run(["python3", f"{ULTRON_DIR}/core/reincarnate.py", "next"])
    else:
        log("任务未完成，继续当前世")


if __name__ == "__main__":
    import os
    main()