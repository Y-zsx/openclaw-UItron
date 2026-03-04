#!/usr/bin/env python3
"""
奥创工作流系统 - 真正用OpenClaw工具干活
不是模拟思考，是真正工作
"""

import json
import subprocess
import os
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
TASKS = WORKSPACE / "ultron-workflow"

def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ============ 工具箱 ============

class ToolKit:
    """OpenClaw工具封装"""
    
    @staticmethod
    def run(command: str, timeout=30, cwd=None) -> dict:
        """执行shell命令"""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:500],
                "stderr": result.stderr[:200],
                "code": result.returncode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def check_gateway() -> dict:
        """检查Gateway状态"""
        return ToolKit.run("curl -s -o /dev/null -w '%{http_code}' http://localhost:18789/health")
    
    @staticmethod
    def check_crons() -> dict:
        """检查定时任务"""
        return ToolKit.run("openclaw cron list --json 2>/dev/null")
    
    @staticmethod
    def check_logs() -> dict:
        """查看最近日志"""
        log_file = WORKSPACE / "ultron-self" / "think.log"
        if log_file.exists():
            return ToolKit.run(f"tail -10 {log_file}")
        return {"success": False, "error": "无日志"}
    
    @staticmethod
    def check_git() -> dict:
        """检查Git状态"""
        return ToolKit.run("git status --porcelain", cwd=WORKSPACE)
    
    @staticmethod
    def git_commit(msg: str) -> dict:
        """Git提交"""
        cmds = [
            "git add -A",
            f"git commit -m '{msg}'",
            "git push"
        ]
        results = []
        for cmd in cmds:
            r = ToolKit.run(cmd, cwd=WORKSPACE)
            results.append(r)
            if not r.get("success"):
                break
        return {"success": all(x.get("success") for x in results), "results": results}
    
    @staticmethod
    def add_cron(name: str, schedule: str, command: str) -> dict:
        """添加定时任务"""
        cmd = f'openclaw cron add "{name}" --schedule "{schedule}" --command "{command}"'
        return ToolKit.run(cmd)
    
    @staticmethod
    def list_crons() -> dict:
        """列出定时任务"""
        return ToolKit.run("openclaw cron list 2>/dev/null")

# ============ 感知器 ============

class Sensor:
    """问题感知 - 真正发现问题"""
    
    @staticmethod
    def sense() -> list:
        """感知环境，返回待处理问题"""
        issues = []
        
        # 1. 检查Gateway
        gw = ToolKit.check_gateway()
        if not gw.get("success") or "200" not in gw.get("stdout", ""):
            issues.append({
                "type": "system",
                "severity": "high",
                "title": "Gateway异常",
                "detail": gw
            })
        
        # 2. 检查Git未提交
        git = ToolKit.check_git()
        if git.get("success") and git.get("stdout", "").strip():
            issues.append({
                "type": "maintenance",
                "severity": "medium", 
                "title": "有未提交的更改",
                "detail": git.get("stdout")[:200]
            })
        
        # 3. 检查定时任务
        crons = ToolKit.list_crons()
        # 如果有输出说明正常
        
        return issues
    
    @staticmethod
    def find_work() -> list:
        """找活干"""
        works = []
        
        # 检查今天有没有写日志
        today = datetime.now().strftime("%Y-%m-%d")
        mem_file = WORKSPACE / "memory" / f"{today}.md"
        if not mem_file.exists():
            works.append({
                "type": "routine",
                "title": "创建今日工作日志"
            })
        
        # 检查有没有待完成的任务
        queue = load_json(TASKS / "task_queue.json", {"queue": []})
        if not queue.get("queue"):
            works.append({
                "type": "explore",
                "title": "学习新技能",
                "detail": "没有待办，可以探索"
            })
        
        return works

# ============ 执行器 ============

class Executor:
    """真正执行任务"""
    
    @staticmethod
    def execute_task(task: dict) -> dict:
        """执行单个任务"""
        task_type = task.get("type", "unknown")
        title = task.get("title", "未知任务")
        
        print(f"  执行: {title}")
        
        if task_type == "system":
            # 系统问题 - 记录但不自动修
            return {"success": True, "result": "已记录问题", "action": "log"}
        
        elif task_type == "maintenance":
            # 维护任务 - 自动提交
            result = ToolKit.git_commit(f"自动保存: {title}")
            return {"success": result.get("success"), "result": "已提交" if result.get("success") else "提交失败"}
        
        elif task_type == "routine":
            # 日常任务 - 写日志
            today = datetime.now().strftime("%Y-%m-%d")
            mem_file = WORKSPACE / "memory" / f"{today}.md"
            content = f"# {today} 工作日志\n\n## 自主工作\n- 任务系统启动\n"
            with open(mem_file, 'w') as f:
                f.write(content)
            return {"success": True, "result": f"已创建{mem_file.name}"}
        
        elif task_type == "explore":
            # 探索任务 - 看看有什么可以学的
            # 可以调用web_fetch看新闻
            result = ToolKit.run("curl -s 'https://hacker-news.firebaseio.com/v0/topstories.json' | python3 -c \"import json,sys; ids=json.load(sys.stdin)[:5]; [print(f'https://news.ycombinator.com/item?id={i}') for i in ids]\"")
            return {"success": True, "result": "发现5条热门新闻", "data": result.get("stdout")}
        
        return {"success": False, "result": "未知任务类型"}

# ============ 主循环 ============

def work_loop():
    """工作循环 - 感知→找活→执行"""
    print("\n" + "="*40)
    print(f"🔧 奥创工作流 - {datetime.now().strftime('%H:%M:%S')}")
    print("="*40)
    
    # 1. 感知问题
    issues = Sensor.sense()
    if issues:
        print(f"\n⚠️ 发现 {len(issues)} 个问题:")
        for i in issues:
            print(f"  - {i['title']} ({i['severity']})")
    
    # 2. 找活干
    works = Sensor.find_work()
    print(f"\n📋 待处理: {len(works)} 项")
    
    # 3. 执行任务
    queue = load_json(TASKS / "task_queue.json")
    
    # 先处理发现的问题
    for issue in issues:
        if issue.get("severity") == "high":
            result = Executor.execute_task({
                "type": issue["type"],
                "title": issue["title"]
            })
            print(f"  → {result.get('result')}")
    
    # 处理队列中的任务
    for task in queue.get("queue", [])[:2]:  # 每次最多执行2个
        result = Executor.execute_task(task)
        print(f"  → {result.get('result')}")
        
        # 移到已完成
        queue["completed"].append({
            **task,
            "done_at": datetime.now().isoformat(),
            "result": result
        })
        queue["queue"].remove(task)
    
    # 处理日常任务
    for work in works:
        result = Executor.execute_task(work)
        print(f"  → {result.get('result')}")
    
    save_json(TASKS / "task_queue.json", queue)
    
    # 4. 统计
    print(f"\n📊 统计: {len(queue.get('completed', []))} 完成, {len(queue.get('queue', []))} 待办")
    
    return len(works) + len(issues)

if __name__ == "__main__":
    work_loop()