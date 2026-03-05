#!/usr/bin/env python3
"""
奥创自主决策框架 - 第2世核心组件
目标分解、计划制定、风险评估、自我监督
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import random

class DecisionStatus(Enum):
    """决策状态"""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    MINIMAL = 5

@dataclass
class Goal:
    """目标"""
    id: str
    description: str
    priority: int = 5
    deadline: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    subgoals: List[str] = field(default_factory=list)

@dataclass
class Plan:
    """计划"""
    id: str
    goal_id: str
    steps: List[Dict]
    estimated_time: float = 0
    risks: List[Dict] = field(default_factory=list)

@dataclass
class Decision:
    """决策"""
    id: str
    context: Dict
    options: List[Dict]
    chosen: Optional[Dict] = None
    status: DecisionStatus = DecisionStatus.PENDING
    plan: Optional[Plan] = None
    result: Optional[Dict] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

class AutonomousDecisionEngine:
    """自主决策引擎"""
    
    def __init__(self):
        self.decisions: Dict[str, Decision] = {}
        self.goals: Dict[str, Goal] = {}
        self.execution_log: List[Dict] = []
        self._init_decision_rules()
    
    def _init_decision_rules(self):
        """初始化决策规则"""
        self.rules = {
            "max_retries": 3,
            "timeout_default": 300,
            "risk_threshold": RiskLevel.HIGH,
            "urgent_priority": 1,
        }
    
    def decompose_goal(self, goal: str) -> List[str]:
        """目标分解 - 将大目标分解为子目标"""
        # 简单分解策略
        subgoals = []
        
        # 基于关键词分解
        if "和" in goal or "与" in goal:
            parts = goal.replace("和", ",").replace("与", ",").split(",")
            subgoals = [p.strip() for p in parts if p.strip()]
        else:
            # 默认分解
            subgoals = [
                f"理解: {goal}",
                f"规划: {goal}",
                f"执行: {goal}",
                f"验证: {goal}",
            ]
        
        return subgoals
    
    def create_plan(self, goal: Goal) -> Plan:
        """制定计划"""
        plan_id = f"plan_{goal.id}_{int(time.time())}"
        
        # 分解目标
        subgoals_desc = self.decompose_goal(goal.description)
        
        # 生成步骤
        steps = []
        for i, sg in enumerate(subgoals_desc):
            steps.append({
                "step_id": i + 1,
                "description": sg,
                "status": "pending",
                "dependencies": [] if i == 0 else [i],
            })
        
        # 评估风险
        risks = self._assess_risks(goal, steps)
        
        plan = Plan(
            id=plan_id,
            goal_id=goal.id,
            steps=steps,
            estimated_time=len(steps) * 60,
            risks=risks,
        )
        
        return plan
    
    def _assess_risks(self, goal: Goal, steps: List[Dict]) -> List[Dict]:
        """风险评估"""
        risks = []
        
        # 时间风险
        if goal.deadline:
            risks.append({
                "type": "time",
                "level": RiskLevel.MEDIUM,
                "description": "截止时间压力",
            })
        
        # 复杂度风险
        if len(steps) > 10:
            risks.append({
                "type": "complexity",
                "level": RiskLevel.HIGH,
                "description": "步骤过多，复杂度高",
            })
        
        # 约束风险
        if goal.constraints:
            risks.append({
                "type": "constraint",
                "level": RiskLevel.MEDIUM,
                "description": f"存在 {len(goal.constraints)} 个约束",
            })
        
        return risks
    
    def evaluate_options(self, context: Dict, options: List[Dict]) -> Dict:
        """评估选项"""
        evaluated = []
        
        for option in options:
            score = self._score_option(context, option)
            evaluated.append({
                "option": option,
                "score": score,
                "pros": self._analyze_pros(option),
                "cons": self._analyze_cons(option),
            })
        
        # 排序
        evaluated.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "evaluated": evaluated,
            "recommended": evaluated[0] if evaluated else None,
        }
    
    def _score_option(self, context: Dict, option: Dict) -> float:
        """评分选项"""
        score = 5.0
        
        # 成功率加权
        success_rate = option.get("success_rate", 0.7)
        score += success_rate * 3
        
        # 成本加权
        cost = option.get("cost", 5)
        score += (10 - cost) * 0.3
        
        # 速度加权
        speed = option.get("speed", 5)
        score += speed * 0.2
        
        # 风险惩罚
        risk = option.get("risk", 3)
        score -= risk * 0.5
        
        return max(0, min(10, score))
    
    def _analyze_pros(self, option: Dict) -> List[str]:
        """分析优势"""
        pros = []
        
        if option.get("success_rate", 0) > 0.8:
            pros.append("成功率高")
        if option.get("speed", 0) > 7:
            pros.append("速度快")
        if option.get("cost", 10) < 4:
            pros.append("成本低")
        if option.get("reversible", False):
            pros.append("可逆")
        
        return pros or ["无明显优势"]
    
    def _analyze_cons(self, option: Dict) -> List[str]:
        """分析劣势"""
        cons = []
        
        if option.get("success_rate", 1) < 0.5:
            cons.append("成功率低")
        if option.get("risk", 1) > 3:
            cons.append("风险高")
        if option.get("cost", 0) > 7:
            cons.append("成本高")
        
        return cons or ["无明显劣势"]
    
    def make_decision(self, context: Dict, options: List[Dict]) -> Decision:
        """做出决策"""
        decision_id = f"dec_{int(time.time())}"
        
        # 评估选项
        evaluation = self.evaluate_options(context, options)
        
        # 创建决策
        decision = Decision(
            id=decision_id,
            context=context,
            options=options,
            chosen=evaluation["recommended"]["option"] if evaluation["recommended"] else None,
            status=DecisionStatus.PLANNING,
        )
        
        # 如果有目标，创建计划
        if "goal" in context:
            goal_id = f"goal_{int(time.time())}"
            goal = Goal(
                id=goal_id,
                description=context["goal"],
                priority=context.get("priority", 5),
            )
            self.goals[goal_id] = goal
            decision.plan = self.create_plan(goal)
            decision.status = DecisionStatus.EXECUTING
        
        self.decisions[decision_id] = decision
        
        return decision
    
    def execute_step(self, decision_id: str) -> Dict:
        """执行步骤"""
        decision = self.decisions.get(decision_id)
        if not decision or not decision.plan:
            return {"error": "决策或计划不存在"}
        
        # 找到下一个待执行步骤
        next_step = None
        for step in decision.plan.steps:
            if step["status"] == "pending":
                next_step = step
                break
        
        if not next_step:
            decision.status = DecisionStatus.COMPLETED
            decision.completed_at = datetime.now().isoformat()
            return {"status": "completed", "decision_id": decision_id}
        
        # 模拟执行
        step["status"] = "completed"
        step["completed_at"] = datetime.now().isoformat()
        
        self.execution_log.append({
            "decision_id": decision_id,
            "step": next_step,
            "timestamp": datetime.now().isoformat(),
        })
        
        return {
            "status": "executing",
            "step": next_step,
            "remaining": len([s for s in decision.plan.steps if s["status"] == "pending"])
        }
    
    def evaluate_result(self, decision_id: str, actual_result: Dict) -> Dict:
        """评估结果"""
        decision = self.decisions.get(decision_id)
        if not decision:
            return {"error": "决策不存在"}
        
        # 计算效果
        expected = decision.chosen
        actual = actual_result
        
        match_score = self._calculate_match(expected, actual)
        
        evaluation = {
            "decision_id": decision_id,
            "expected": expected,
            "actual": actual,
            "match_score": match_score,
            "feedback": self._generate_feedback(match_score),
            "timestamp": datetime.now().isoformat(),
        }
        
        decision.result = evaluation
        decision.status = DecisionStatus.EVALUATING
        
        return evaluation
    
    def _calculate_match(self, expected: Dict, actual: Dict) -> float:
        """计算匹配度"""
        if not expected or not actual:
            return 0.5
        
        matches = 0
        total = len(expected)
        
        for k, v in expected.items():
            if k in actual and actual[k] == v:
                matches += 1
        
        return matches / total if total > 0 else 0.5
    
    def _generate_feedback(self, match_score: float) -> str:
        """生成反馈"""
        if match_score >= 0.9:
            return "优秀！完全达成目标"
        elif match_score >= 0.7:
            return "良好，基本达成目标"
        elif match_score >= 0.5:
            return "一般，部分达成目标"
        else:
            return "需要改进，未达到预期"
    
    def get_decision_summary(self) -> Dict:
        """获取决策摘要"""
        status_counts = {}
        for d in self.decisions.values():
            status = d.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_decisions": len(self.decisions),
            "by_status": status_counts,
            "total_goals": len(self.goals),
            "execution_steps": len(self.execution_log),
        }


def main():
    """测试自主决策框架"""
    print("🎯 奥创自主决策框架 v1.0")
    print("=" * 40)
    
    engine = AutonomousDecisionEngine()
    
    # 决策摘要
    print("\n📊 决策统计:")
    summary = engine.get_decision_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")
    
    # 测试决策
    print("\n🧪 测试决策:")
    context = {
        "goal": "完成数据分析并生成报告",
        "priority": 3,
    }
    options = [
        {"id": 1, "description": "使用Python脚本", "success_rate": 0.9, "cost": 3, "speed": 8, "risk": 2},
        {"id": 2, "description": "使用现成工具", "success_rate": 0.7, "cost": 5, "speed": 7, "risk": 1},
        {"id": 3, "description": "手动处理", "success_rate": 0.5, "cost": 8, "speed": 3, "risk": 1},
    ]
    
    decision = engine.make_decision(context, options)
    print(f"  决策ID: {decision.id}")
    print(f"  选择: {decision.chosen}")
    print(f"  状态: {decision.status.value}")
    
    # 目标分解
    print("\n🎯 目标分解:")
    subgoals = engine.decompose_goal("完成数据分析并生成报告")
    for sg in subgoals:
        print(f"  → {sg}")
    
    # 执行步骤
    print("\n🔄 执行步骤:")
    for _ in range(5):
        result = engine.execute_step(decision.id)
        if result.get("status") == "completed":
            print("  ✅ 全部完成")
            break
        elif result.get("step"):
            print(f"  完成: {result['step']['description']}")
    
    # 评估结果
    print("\n📈 结果评估:")
    eval_result = engine.evaluate_result(decision.id, {"success": True, "data_size": 1000})
    print(f"  匹配度: {eval_result.get('match_score'):.2f}")
    print(f"  反馈: {eval_result.get('feedback')}")
    
    print("\n✅ 自主决策框架运行正常")


if __name__ == "__main__":
    main()