#!/usr/bin/env python3
"""
Reincarnation Loop - 自主循环执行脚本

用法:
  python reincarnate.py init --project <路径> --ambition "<目标>"
  python reincarnate.py run --project <路径>
  python reincarnate.py status --project <路径>
"""

import os
import json
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

TEMPLATE_AMBITION = """# {ambition}

## 当前目标
{ambition}

## 里程碑
- [ ] 调研阶段
- [ ] 实现阶段
- [ ] 测试阶段

## 验收标准
- [具体可衡量的标准]
"""

TEMPLATE_STATE = {
    "current_incarnation": 1,
    "current_ambition": "",
    "ambition_status": "running",
    "last_incarnation_time": "",
    "current_task": "初始化项目",
    "task_status": "in_progress",
    "history": [],
    "this_life_accomplished": [],
    "next_life_task": "开始调研"
}

def init_project(project_path: str, ambition: str):
    """初始化项目结构"""
    path = Path(project_path)
    path.mkdir(parents=True, exist_ok=True)
    
    # 创建 ambition.md
    ambition_file = path / "ambition.md"
    ambition_file.write_text(TEMPLATE_AMBITION.format(ambition=ambition))
    
    # 创建 state.json
    state_file = path / "state.json"
    state = TEMPLATE_STATE.copy()
    state["current_ambition"] = ambition
    state["last_incarnation_time"] = datetime.now(UTC).isoformat()
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    
    print(f"✅ 项目初始化完成: {project_path}")
    print(f"   夙愿: {ambition}")
    print(f"   下一步: 编辑 ambition.md 和 state.json，然后开始执行")

def get_status(project_path: str):
    """查看项目状态"""
    path = Path(project_path)
    state_file = path / "state.json"
    
    if not state_file.exists():
        print("❌ 项目未初始化")
        return
    
    state = json.loads(state_file.read_text())
    
    print(f"\n{'='*40}")
    print(f"🎯 夙愿: {state['current_ambition']}")
    print(f"📍 状态: {state['ambition_status']}")
    print(f"🔄 转世: 第 {state['current_incarnation']} 次")
    print(f"📌 当前任务: {state['current_task']}")
    print(f"   任务状态: {state['task_status']}")
    print(f"   下次任务: {state['next_life_task']}")
    print(f"\n📝 本次完成:")
    for item in state.get('this_life_accomplished', []):
        print(f"   - {item}")
    print(f"\n📜 历史 ({len(state.get('history', []))} 次转世)")
    for h in state.get('history', [])[-3:]:
        print(f"   #{h['incarnation']}: {h.get('action', 'N/A')}")
    print(f"{'='*40}\n")

def main():
    parser = argparse.ArgumentParser(description="Reincarnation Loop CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化项目")
    init_parser.add_argument("--project", required=True, help="项目路径")
    init_parser.add_argument("--ambition", required=True, help="夙愿/目标")
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查看状态")
    status_parser.add_argument("--project", required=True, help="项目路径")
    
    # run 命令 (模板，实际执行由AI完成)
    run_parser = subparsers.add_parser("run", help="执行转世循环")
    run_parser.add_argument("--project", required=True, help="项目路径")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_project(args.project, args.ambition)
    elif args.command == "status":
        get_status(args.project)
    elif args.command == "run":
        print("请在OpenClaw中使用此skill，由AI自主执行循环")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()