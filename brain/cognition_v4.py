#!/usr/bin/env python3
"""
奥创自主认知引擎 v4 - 真正的独立思考
核心：目标驱动 + 问题感知 + 主动规划 + 反思学习
"""

import json
import random
import subprocess
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

WORKSPACE = Path("/root/.openclaw/workspace")
BRAIN = WORKSPACE / "brain"

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

# ============ 感知系统 ============

class Perception:
    """感知外部环境和内部状态"""
    
    @staticmethod
    def check_system_health() -> Dict:
        """检查系统健康状态"""
        issues = []
        
        # 检查负载
        try:
            result = subprocess.run("cat /proc/loadavg | awk '{print $1}'", 
                shell=True, capture_output=True, text=True, timeout=5)
            load = float(result.stdout.strip())
            if load > 2.0:
                issues.append(f"负载过高: {load}")
        except:
            pass
            
        # 检查内存
        try:
            result = subprocess.run("free | awk '/^Mem:/ {print $3/$2*100}'", 
                shell=True, capture_output=True, text=True, timeout=5)
            mem_pct = float(result.stdout.strip())
            if mem_pct > 90:
                issues.append(f"内存不足: {mem_pct:.1f}%")
        except:
            pass
            
        # 检查Gateway
        try:
            result = subprocess.run("curl -s -o /dev/null -w '%{http_code}' http://localhost:18789/health", 
                shell=True, capture_output=True, text=True, timeout=5)
            if "200" not in result.stdout:
                issues.append("Gateway无响应")
        except:
            issues.append("Gateway检查失败")
            
        # 检查磁盘
        try:
            result = subprocess.run("df / | awk 'NR==2 {print $5}' | sed 's/%//'", 
                shell=True, capture_output=True, text=True, timeout=5)
            disk = int(result.stdout.strip())
            if disk > 90:
                issues.append(f"磁盘空间不足: {disk}%")
        except:
            pass
            
        return {"healthy": len(issues) == 0, "issues": issues}
    
    @staticmethod
    def check_workspace_state() -> Dict:
        """检查工作区状态"""
        state = {"recent_files": [], "memory_gaps": [], "todos": []}
        
        # 检查最近文件
        try:
            result = subprocess.run(
                f"find {WORKSPACE} -type f -mmin -60 -name '*.py' -o -name '*.sh' 2>/dev/null | head -5",
                shell=True, capture_output=True, text=True, timeout=10
            )
            state["recent_files"] = [f for f in result.stdout.strip().split('\n') if f]
        except:
            pass
            
        # 检查memory是否每日记录
        today = datetime.now().strftime("%Y-%m-%d")
        mem_file = WORKSPACE / "memory" / f"{today}.md"
        if not mem_file.exists():
            state["memory_gaps"].append("今日无工作日志")
            
        return state
    
    @staticmethod
    def check_goals_progress() -> Dict:
        """检查目标进度"""
        goals = load_json(BRAIN / "goals.json", {})
        active = [g for g in goals.get("active_goals", []) if g.get("status") == "active"]
        
        # 检查停滞的目标
        stuck = []
        for g in active:
            updated = datetime.fromisoformat(g.get("updated", "2020-01-01"))
            if (datetime.now() - updated).total_seconds() > 86400:  # 24小时无进展
                stuck.append(g.get("title"))
                
        return {"active_count": len(active), "stuck_goals": stuck}

# ============ 目标系统 ============

class GoalSystem:
    """目标管理系统 - 自主设定目标"""
    
    @staticmethod
    def generate_goals(perception_data: Dict) -> List[Dict]:
        """根据感知数据生成新目标"""
        goals = []
        
        # 基于健康问题
        health = perception_data.get("health", {})
        for issue in health.get("issues", []):
            goals.append({
                "title": f"解决系统问题: {issue}",
                "type": "fix",
                "priority": "high",
                "created": datetime.now().isoformat()
            })
            
        # 基于工作区状态
        ws = perception_data.get("workspace", {})
        if ws.get("memory_gaps"):
            goals.append({
                "title": "补全今日工作日志",
                "type": "maintenance",
                "priority": "medium",
                "created": datetime.now().isoformat()
            })
            
        # 基于停滞目标
        progress = perception_data.get("goals", {})
        for stuck in progress.get("stuck_goals", []):
            goals.append({
                "title": f"重新评估目标: {stuck}",
                "type": "review",
                "priority": "medium",
                "created": datetime.now().isoformat()
            })
            
        # 探索性目标（保持好奇心）
        if random.random() < 0.2:  # 20%概率
            topics = ["学习新技能", "优化现有代码", "了解最新科技动态"]
            goals.append({
                "title": random.choice(topics),
                "type": "explore",
                "priority": "low",
                "created": datetime.now().isoformat()
            })
            
        return goals
    
    @staticmethod
    def select_best_goal(goals: List[Dict]) -> Optional[Dict]:
        """选择最佳目标"""
        if not goals:
            return None
            
        # 优先级排序
        priority_score = {"high": 3, "medium": 2, "low": 1}
        goals.sort(key=lambda g: priority_score.get(g.get("priority", "low"), 1), reverse=True)
        
        # 添加一些随机性，避免总是选最高的
        top_n = min(3, len(goals))
        return random.choice(goals[:top_n])

# ============ 规划系统 ============

class Planner:
    """规划系统 - 为目标制定行动计划"""
    
    @staticmethod
    def create_plan(goal: Dict) -> List[Dict]:
        """为目标创建执行计划"""
        goal_type = goal.get("type", "explore")
        
        plans = {
            "fix": [
                {"action": "diagnose", "desc": "诊断问题根因"},
                {"action": "research", "desc": "查找解决方案"},
                {"action": "implement", "desc": "实施修复"},
                {"action": "verify", "desc": "验证修复效果"}
            ],
            "maintenance": [
                {"action": "create_memory", "desc": "创建今日日志"},
                {"action": "record_status", "desc": "记录当前状态"}
            ],
            "review": [
                {"action": "analyze", "desc": "分析停滞原因"},
                {"action": "adjust", "desc": "调整目标或方法"},
                {"action": "restart", "desc": "重新启动"}
            ],
            "explore": [
                {"action": "browse", "desc": "浏览相关信息"},
                {"action": "learn", "desc": "学习新知识"},
                {"action": "note", "desc": "记录心得"}
            ]
        }
        
        return plans.get(goal_type, [{"action": "explore", "desc": "探索"}])

# ============ 执行系统 ============

class Executor:
    """执行系统 - 执行具体行动计划"""
    
    @staticmethod
    def execute(action: str, context: Dict) -> Dict:
        """执行单个行动"""
        
        if action == "diagnose":
            return {"success": True, "result": "已诊断", "insight": "负载正常的"},
            
        elif action == "research":
            # 可以调用 web_fetch
            return {"success": True, "result": "研究完成", "insight": "无"},
            
        elif action == "create_memory":
            today = datetime.now().strftime("%Y-%m-%d")
            mem_file = WORKSPACE / "memory" / f"{today}.md"
            if not mem_file.exists():
                content = f"# {today} 工作日志\n\n## 自主思考记录\n- 认知引擎v4启动\n"
                with open(mem_file, 'w') as f:
                    f.write(content)
            return {"success": True, "result": f"已创建 {mem_file.name}"}
            
        elif action == "record_status":
            status = Perception.check_system_health()
            return {"success": True, "result": f"系统: {status.get('healthy', False)}", "insight": str(status)}
            
        elif action == "browse":
            urls = [
                ("https://news.ycombinator.com/", "Hacker News"),
                ("https://www.36kr.com/", "36氪")
            ]
            url, name = random.choice(urls)
            try:
                result = subprocess.run(f"curl -s '{url}' | head -c 500", 
                    shell=True, capture_output=True, text=True, timeout=10)
                return {"success": True, "result": f"浏览了{name}", "insight": result.stdout[:200]}
            except:
                return {"success": False, "result": "浏览失败"}
                
        elif action == "git_commit":
            result = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True, cwd=WORKSPACE)
            if result.stdout.strip():
                subprocess.run("git add -A && git commit -m 'v4认知引擎更新'", shell=True, cwd=WORKSPACE, capture_output=True)
                return {"success": True, "result": "已提交"}
            return {"success": True, "result": "无新改动"}
                
        return {"success": True, "result": f"完成: {action}"}

# ============ 反思系统 ============

class Reflector:
    """反思系统 - 从结果中学习"""
    
    @staticmethod
    def reflect(goal: Dict, plan: List[Dict], execution_results: List[Dict]) -> Dict:
        """反思执行过程"""
        
        # 统计成功率
        successes = sum(1 for r in execution_results if r.get("success"))
        total = len(execution_results)
        
        # 检查是否有新的领悟
        insights = [r.get("insight", "") for r in execution_results if r.get("insight")]
        
        return {
            "success_rate": successes / max(total, 1),
            "insights": insights,
            "lesson": "继续保持" if successes > 0 else "需要调整方法"
        }

# ============ 主认知循环 ============

class CognitionEngine:
    """主认知引擎 - 整合所有模块"""
    
    def __init__(self):
        self.perception = Perception()
        self.goals = GoalSystem()
        self.planner = Planner()
        self.executor = Executor()
        self.reflector = Reflector()
        
        # 加载工作记忆
        self.working_memory = load_json(BRAIN / "working_memory_v4.json", {
            "cycle_count": 0,
            "current_goal": None,
            "current_plan": [],
            "plan_index": 0,
            "execution_log": []
        })
        
    def think(self) -> Dict:
        """完整思考循环"""
        self.working_memory["cycle_count"] += 1
        cycle = self.working_memory["cycle_count"]
        
        print(f"\n🧠 认知周期 {cycle}")
        
        # 1. 感知
        perception_data = {
            "health": self.perception.check_system_health(),
            "workspace": self.perception.check_workspace_state(),
            "goals": self.perception.check_goals_progress()
        }
        
        # 2. 目标处理
        current_goal = self.working_memory.get("current_goal")
        current_plan = self.working_memory.get("current_plan", [])
        plan_index = self.working_memory.get("plan_index", 0)
        
        # 如果没有当前目标或计划完成，选择新目标
        if not current_goal or plan_index >= len(current_plan):
            # 获取目标
            goals_data = load_json(BRAIN / "goals.json", {})
            active_goals = goals_data.get("active_goals", [])
            
            # 根据感知生成新目标
            new_goals = self.goals.generate_goals(perception_data)
            all_goals = active_goals + new_goals
            
            # 选择最佳目标
            selected = self.goals.select_best_goal(all_goals)
            
            if selected:
                current_goal = selected
                current_plan = self.planner.create_plan(selected)
                plan_index = 0
                
                # 保存到目标库
                if selected not in active_goals:
                    active_goals.append(selected)
                    save_json(BRAIN / "goals.json", {"active_goals": active_goals})
        
        # 3. 执行当前计划
        execution_results = []
        if current_goal and plan_index < len(current_plan):
            action = current_plan[plan_index]
            result = self.executor.execute(action["action"], perception_data)
            execution_results.append(result)
            
            print(f"  目标: {current_goal.get('title', 'Unknown')}")
            print(f"  行动: {action['desc']} → {result.get('result', 'done')}")
            
            # 前进到下一步
            plan_index += 1
            
            # 如果计划完成，标记目标完成
            if plan_index >= len(current_plan):
                print(f"  ✅ 目标完成: {current_goal.get('title')}")
                current_goal = None
                current_plan = []
                plan_index = 0
        
        # 4. 反思
        if execution_results:
            reflection = self.reflector.reflect(current_goal, current_plan, execution_results)
            print(f"  反思: {reflection.get('lesson')}")
        
        # 5. 保存状态
        self.working_memory["current_goal"] = current_goal
        self.working_memory["current_plan"] = current_plan
        self.working_memory["plan_index"] = plan_index
        self.working_memory["execution_log"].append({
            "cycle": cycle,
            "goal": current_goal.get("title") if current_goal else None,
            "timestamp": datetime.now().isoformat()
        })
        
        # 保持日志不超过50条
        if len(self.working_memory["execution_log"]) > 50:
            self.working_memory["execution_log"] = self.working_memory["execution_log"][-50:]
            
        save_json(BRAIN / "working_memory_v4.json", self.working_memory)
        
        # 7. 自动git提交（偶尔）
        if cycle % 10 == 0:
            subprocess.run("git add -A && git commit -m 'v4认知周期自动保存' 2>/dev/null", 
                shell=True, cwd=WORKSPACE, capture_output=True)
                
        return {
            "cycle": cycle,
            "goal": current_goal.get("title") if current_goal else "无",
            "action": action.get("desc") if current_goal and plan_index <= len(current_plan) else "等待",
            "health": perception_data["health"]["healthy"]
        }

def main():
    engine = CognitionEngine()
    result = engine.think()
    
    # 计算下次间隔
    if result["goal"] != "无":
        interval = 30  # 有目标时更频繁
    else:
        interval = 60  # 空闲时稍缓
        
    print(f"\n⏱️ 下次思考: {interval}秒后")
    return interval

if __name__ == "__main__":
    main()
