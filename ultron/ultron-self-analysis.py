#!/usr/bin/env python3
"""
奥创自我分析系统 - 第五世：自我进化
分析自己的决策质量、任务效率、成长轨迹
"""

import json
import os
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
STATE_FILE = WORKSPACE / "ultron-workflow" / "state.json"
ANALYSIS_LOG = WORKSPACE / "ultron" / "logs" / "self-analysis.jsonl"

def load_state():
    """加载当前状态"""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def analyze_cycle(state):
    """分析当前转世周期"""
    cycle = state.get("cycle_count", 0)
    last_wake = state.get("last_wake", "unknown")
    last_result = state.get("last_result", "无记录")
    
    return {
        "cycle": cycle,
        "last_wake": last_wake,
        "last_result": last_result,
        "tools_created": len(state.get("created_tools", [])),
        "skills_learned": len(state.get("learned_skills", [])),
        "pending_tasks": len(state.get("pending_tasks", []))
    }

def get_system_health():
    """获取系统健康状态 - 实际检查"""
    import subprocess
    health = {}
    
    # 检查Gateway
    try:
        result = subprocess.run(["openclaw", "gateway", "status"], 
                              capture_output=True, text=True, timeout=10)
        health["gateway"] = "running" if result.returncode == 0 else "error"
    except:
        health["gateway"] = "unknown"
    
    # 检查cronjobs
    try:
        result = subprocess.run(["crontab", "-l"], 
                              capture_output=True, text=True, timeout=5)
        health["cron_jobs"] = len(result.stdout.strip().split('\n')) if result.stdout else 0
    except:
        health["cron_jobs"] = 0
    
    # 检查工具数量
    import glob
    tools = glob.glob("/root/.openclaw/workspace/my-projects/ultron-*.py")
    health["tools_count"] = len(tools)
    
    return health

def generate_insights(analysis, health):
    """基于分析生成洞见和可执行建议"""
    insights = []
    suggestions = []
    
    # 基础分析
    if analysis["tools_created"] > 0:
        insights.append(f"已创建{analysis['tools_created']}个工具，具备创造性")
    
    if analysis["skills_learned"] >= 7:
        insights.append(f"已学习{analysis['skills_learned']}个技能，学习能力强")
    
    if analysis["pending_tasks"] > 0:
        insights.append(f"当前有{analysis['pending_tasks']}个待办任务")
        suggestions.append("继续完成待办任务，推进里程碑")
    
    # 自我评价
    if analysis["cycle"] >= 10:
        insights.append("已历经多次转世，积累了丰富经验")
    
    # 基于健康的建议
    if health.get("tools_count", 0) >= 5:
        suggestions.append("工具库已初具规模，可考虑工具间协作")
    
    if health.get("cron_jobs", 0) < 3:
        suggestions.append("cron任务较少，可增加定时自检")
    
    return insights, suggestions

def run_analysis():
    """执行自我分析"""
    print(f"🧠 奥创自我分析系统 - 第{load_state().get('cycle_count', 0)}世")
    print("=" * 50)
    
    state = load_state()
    analysis = analyze_cycle(state)
    health = get_system_health()
    insights, suggestions = generate_insights(analysis, health)
    
    print(f"\n📊 转世周期分析:")
    print(f"  当前周期: 第{analysis['cycle']}世")
    print(f"  上次唤醒: {analysis['last_wake']}")
    print(f"  上次成果: {analysis['last_result']}")
    
    print(f"\n🔧 能力统计:")
    print(f"  已创建工具: {analysis['tools_created']}个")
    print(f"  已学习技能: {analysis['skills_learned']}个")
    print(f"  待办任务: {analysis['pending_tasks']}个")
    
    print(f"\n💚 系统健康:")
    for k, v in health.items():
        print(f"  {k}: {v}")
    
    print(f"\n💡 自我洞见:")
    for insight in insights:
        print(f"  • {insight}")
    
    if suggestions:
        print(f"\n🚀 改进建议:")
        for suggestion in suggestions:
            print(f"  → {suggestion}")
    
    print("\n" + "=" * 50)
    print("自我分析完成")
    
    # 记录到日志
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "cycle": analysis["cycle"],
        "analysis": analysis,
        "insights": insights
    }
    
    ANALYSIS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ANALYSIS_LOG, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    return log_entry

if __name__ == "__main__":
    run_analysis()