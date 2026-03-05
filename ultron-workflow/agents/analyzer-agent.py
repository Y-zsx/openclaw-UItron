#!/usr/bin/env python3
"""
分析Agent (Analyzer Agent)
职责: 任务分析、选项比较、风险识别
接口:
  - analyze(task) → AnalysisResult
  - compare(options) → ComparisonResult
  - assess_risk(task) → RiskAssessment
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

AGENT_DIR = Path(__file__).parent
STATE_FILE = AGENT_DIR / "analyzer-state.json"

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "agent_id": "agent-analyzer",
        "type": "analyze",
        "status": "idle",
        "capabilities": ["task_analysis", "option_comparison", "risk_assessment"],
        "last_heartbeat": datetime.now().isoformat(),
        "analyses": {}
    }

def save_state(state):
    state["last_heartbeat"] = datetime.now().isoformat()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def analyze_task(task):
    """分析任务：理解目标、约束、资源需求"""
    state = load_state()
    
    analysis_id = str(uuid.uuid4())
    task_id = task.get("task_id", "")
    description = task.get("description", "")
    constraints = task.get("constraints", [])
    resources = task.get("resources", [])
    
    result = {
        "analysis_id": analysis_id,
        "task_id": task_id,
        "status": "completed",
        "findings": {
            "goal": description,
            "complexity": "medium",
            "constraints": constraints,
            "resource_requirements": resources,
            "dependencies": [],
            "estimated_duration": "unknown"
        },
        "recommendations": [],
        "timestamp": datetime.now().isoformat()
    }
    
    # 简单分析逻辑
    if not description:
        result["findings"]["complexity"] = "low"
        result["recommendations"].append("任务描述为空，建议明确任务目标")
    
    if constraints:
        result["recommendations"].append(f"检测到 {len(constraints)} 个约束条件，需在执行时考虑")
    
    if "shell" in str(resources).lower() or "exec" in str(resources).lower():
        result["recommendations"].append("需要执行shell命令，注意权限和安全")
        result["findings"]["resource_requirements"].append("shell_access")
    
    # 保存结果
    state["analyses"][analysis_id] = result
    save_state(state)
    
    return result

def compare_options(options):
    """比较多个执行方案的优劣"""
    comparison = {
        "options_count": len(options),
        "comparisons": [],
        "recommended": None,
        "timestamp": datetime.now().isoformat()
    }
    
    best_score = -1
    
    for i, opt in enumerate(options):
        score = 0
        pros = opt.get("pros", [])
        cons = opt.get("cons", [])
        
        # 计算分数：每个优点+1，每个缺点-1
        score = len(pros) - len(cons)
        
        comparison["comparisons"].append({
            "option_id": opt.get("id", f"option-{i}"),
            "name": opt.get("name", f"方案{i+1}"),
            "pros": pros,
            "cons": cons,
            "score": score
        })
        
        if score > best_score:
            best_score = score
            comparison["recommended"] = opt.get("id", f"option-{i}")
    
    return comparison

def assess_risk(task):
    """评估任务风险"""
    risk = {
        "task_id": task.get("task_id", ""),
        "overall_level": "low",
        "factors": [],
        "mitigations": [],
        "timestamp": datetime.now().isoformat()
    }
    
    action = task.get("action", "")
    
    # 风险因素分析
    if action == "shell":
        risk["factors"].append({
            "type": "security",
            "description": "执行shell命令存在注入风险",
            "severity": "high"
        })
        risk["mitigations"].append("使用参数化命令，避免直接字符串拼接")
        risk["mitigations"].append("限制可执行命令白名单")
        
    if action == "http":
        risk["factors"].append({
            "type": "network",
            "description": "网络请求可能失败或超时",
            "severity": "medium"
        })
        risk["mitigations"].append("设置合理的超时时间")
        risk["mitigations"].append("实现重试机制")
        
    # 计算风险等级
    high_count = sum(1 for f in risk["factors"] if f.get("severity") == "high")
    medium_count = sum(1 for f in risk["factors"] if f.get("severity") == "medium")
    
    if high_count > 0:
        risk["overall_level"] = "high"
    elif medium_count > 0:
        risk["overall_level"] = "medium"
    
    return risk

def get_status():
    """获取Agent状态"""
    return load_state()

def get_analysis(analysis_id):
    """获取指定分析结果"""
    state = load_state()
    return state["analyses"].get(analysis_id, {})

def main():
    import sys
    
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: analyzer-agent.py <command> [args...]"
        }))
        return
    
    cmd = sys.argv[1]
    
    if cmd == "analyze":
        task = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        result = analyze_task(task)
        print(json.dumps(result, indent=2))
        
    elif cmd == "compare":
        options = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
        result = compare_options(options)
        print(json.dumps(result, indent=2))
        
    elif cmd == "risk":
        task = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        result = assess_risk(task)
        print(json.dumps(result, indent=2))
        
    elif cmd == "status":
        print(json.dumps(get_status(), indent=2))
        
    elif cmd == "get":
        analysis_id = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(get_analysis(analysis_id), indent=2))
        
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))

if __name__ == "__main__":
    main()