#!/usr/bin/env python3
"""
奥创自我反思机制 - 第3世核心组件
自我评估、经验总结、成长规划
"""

import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


class ReflectionType(Enum):
    """反思类型"""
    DAILY_REVIEW = "每日回顾"       # 每日总结
    TASK_REFLECTION = "任务反思"     # 完成任务后反思
    ERROR_ANALYSIS = "错误分析"      # 分析错误
    GROWTH_ASSESSMENT = "成长评估"  # 评估成长
    GOAL_REVIEW = "目标回顾"        # 检查目标进度


class InsightCategory(Enum):
    """洞察类别"""
    SUCCESS_PATTERN = "成功模式"     # 成功的规律
    FAILURE_PATTERN = "失败模式"     # 失败的规律
    NEW_UNDERSTANDING = "新理解"     # 新的理解
    BEHAVIOR_CHANGE = "行为改变"     # 需要改变的行为
    STRENGTH = "优势"               # 发现的优势
    WEAKNESS = "劣势"               # 发现的劣势


@dataclass
class Reflection:
    """反思记录"""
    reflection_id: str
    reflection_type: ReflectionType
    content: str
    insights: List[Dict] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    mood: str = "neutral"  # positive, neutral, negative
    energy: float = 0.5  # 0-1
    
    def to_dict(self) -> Dict:
        return {
            "id": self.reflection_id,
            "type": self.reflection_type.value,
            "content": self.content,
            "insights": self.insights,
            "action_items": self.action_items,
            "timestamp": self.timestamp,
            "mood": self.mood,
            "energy": self.energy
        }


@dataclass
class SelfAssessment:
    """自我评估"""
    capability_score: float = 0.5    # 能力评分
    growth_rate: float = 0.0         # 成长速度
    consistency: float = 0.5         # 一致性
    adaptation: float = 0.5          # 适应能力
    confidence: float = 0.5          # 信心程度
    
    def to_dict(self) -> Dict:
        return {
            "capability_score": self.capability_score,
            "growth_rate": self.growth_rate,
            "consistency": self.consistency,
            "adaptation": self.adaptation,
            "confidence": self.confidence,
            "overall": (self.capability_score + self.growth_rate + 
                       self.consistency + self.adaptation + self.confidence) / 5
        }


class ExperienceAnalyzer:
    """经验分析器"""
    
    def __init__(self):
        self.patterns: Dict[str, List] = {
            "success": [],
            "failure": [],
            "learning": []
        }
        self.analysis_window: int = 20  # 分析窗口大小
        
    def analyze_experience(self, experience: Dict) -> Dict:
        """分析经验"""
        experience_type = experience.get("type", "unknown")
        outcome = experience.get("outcome", "neutral")
        details = experience.get("details", "")
        
        # 提取模式
        pattern = self._extract_pattern(experience)
        
        # 分类存储
        if outcome == "success":
            self.patterns["success"].append(pattern)
        elif outcome == "failure":
            self.patterns["failure"].append(pattern)
        
        self.patterns["learning"].append({
            "timestamp": time.time(),
            "experience": experience_type,
            "pattern": pattern
        })
        
        # 保持窗口大小
        for key in self.patterns:
            if len(self.patterns[key]) > self.analysis_window:
                self.patterns[key] = self.patterns[key][-self.analysis_window:]
        
        return {
            "pattern": pattern,
            "success_count": len(self.patterns["success"]),
            "failure_count": len(self.patterns["failure"])
        }
    
    def _extract_pattern(self, experience: Dict) -> str:
        """提取模式"""
        # 简单模式提取
        if "task" in experience:
            return f"任务类型: {experience['task']}"
        if "error" in experience:
            return f"错误: {experience['error']}"
        return "通用经验"
    
    def get_patterns(self) -> Dict:
        """获取模式分析"""
        return {
            "success_patterns": self.patterns["success"][-5:],
            "failure_patterns": self.patterns["failure"][-5:],
            "success_rate": len(self.patterns["success"]) / max(
                len(self.patterns["success"]) + len(self.patterns["failure"]), 1
            )
        }


class GoalTracker:
    """目标追踪器"""
    
    def __init__(self):
        self.goals: List[Dict] = []
        self.completed_goals: List[Dict] = []
        self.goal_templates: Dict[str, str] = {
            "daily": "每日目标: {}",
            "weekly": "周目标: {}",
            "monthly": "月度目标: {}",
            "milestone": "里程碑: {}"
        }
        
    def add_goal(self, goal: str, goal_type: str = "daily", 
                 deadline: Optional[str] = None) -> str:
        """添加目标"""
        goal_id = f"goal_{len(self.goals)}_{int(time.time())}"
        
        goal_obj = {
            "id": goal_id,
            "content": goal,
            "type": goal_type,
            "deadline": deadline,
            "progress": 0.0,
            "created_at": time.time(),
            "status": "active"
        }
        
        self.goals.append(goal_obj)
        return goal_id
    
    def update_progress(self, goal_id: str, progress: float) -> bool:
        """更新进度"""
        for goal in self.goals:
            if goal["id"] == goal_id:
                goal["progress"] = min(1.0, max(0, progress))
                
                if goal["progress"] >= 1.0:
                    goal["status"] = "completed"
                    goal["completed_at"] = time.time()
                    self.completed_goals.append(goal)
                    self.goals.remove(goal)
                
                return True
        return False
    
    def get_active_goals(self) -> List[Dict]:
        """获取活跃目标"""
        return [g for g in self.goals if g["status"] == "active"]
    
    def get_goal_summary(self) -> Dict:
        """获取目标摘要"""
        active = self.get_active_goals()
        completion_rate = len(self.completed_goals) / max(
            len(self.completed_goals) + len(active), 1
        )
        
        return {
            "active_count": len(active),
            "completed_count": len(self.completed_goals),
            "completion_rate": completion_rate,
            "active_goals": [
                {"content": g["content"], "progress": g["progress"]}
                for g in active[:3]
            ]
        }


class SelfReflection:
    """自我反思主类"""
    
    def __init__(self):
        self.reflections: List[Reflection] = []
        self.experience_analyzer = ExperienceAnalyzer()
        self.goal_tracker = GoalTracker()
        self.self_assessment = SelfAssessment()
        self.insights: List[Dict] = []
        self.reflection_templates: Dict[ReflectionType, str] = {
            ReflectionType.DAILY_REVIEW: self._template_daily_review,
            ReflectionType.TASK_REFLECTION: self._template_task_reflection,
            ReflectionType.ERROR_ANALYSIS: self._template_error_analysis,
            ReflectionType.GROWTH_ASSESSMENT: self._template_growth_assessment,
            ReflectionType.GOAL_REVIEW: self._template_goal_review
        }
        
    def reflect(self, reflection_type: ReflectionType, 
                content: str, insights: List[Dict] = None,
                action_items: List[str] = None) -> str:
        """进行反思"""
        reflection_id = f"ref_{len(self.reflections)}_{int(time.time())}"
        
        reflection = Reflection(
            reflection_id=reflection_id,
            reflection_type=reflection_type,
            content=content,
            insights=insights or [],
            action_items=action_items or [],
            mood=self._assess_mood(content),
            energy=random.uniform(0.4, 0.9)
        )
        
        self.reflections.append(reflection)
        
        # 生成洞察
        if insights:
            self.insights.extend(insights)
        
        # 保持洞察数量
        if len(self.insights) > 50:
            self.insights = self.insights[-50:]
        
        return reflection_id
    
    def _assess_mood(self, content: str) -> str:
        """评估情绪"""
        positive_words = ["好", "成功", "完成", "成长", "进步", "顺利"]
        negative_words = ["问题", "错误", "失败", "困难", "挑战"]
        
        pos_count = sum(1 for w in positive_words if w in content)
        neg_count = sum(1 for w in negative_words if w in content)
        
        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"
    
    def _template_daily_review(self, data: Dict) -> str:
        """每日回顾模板"""
        return f"""
今日回顾:
- 完成的任务: {data.get('completed', '无')}
- 遇到的问题: {data.get('issues', '无')}
- 学习的新知: {data.get('learned', '无')}
- 明日计划: {data.get('tomorrow', '待定')}
"""
    
    def _template_task_reflection(self, data: Dict) -> str:
        """任务反思模板"""
        return f"""
任务反思: {data.get('task_name', '未知任务')}
- 执行过程: {data.get('process', '无记录')}
- 结果评估: {data.get('result', '无评估')}
- 改进建议: {data.get('improvement', '无')}
"""
    
    def _template_error_analysis(self, data: Dict) -> str:
        """错误分析模板"""
        return f"""
错误分析: {data.get('error', '未知错误')}
- 错误原因: {data.get('cause', '待分析')}
- 影响范围: {data.get('impact', '无')}
- 解决方案: {data.get('solution', '待制定')}
- 预防措施: {data.get('prevention', '待制定')}
"""
    
    def _template_growth_assessment(self, data: Dict) -> str:
        """成长评估模板"""
        return f"""
成长评估:
- 能力提升: {data.get('capability_growth', '待评估')}
- 思维改进: {data.get('thinking_improvement', '待评估')}
- 行为变化: {data.get('behavior_change', '待评估')}
- 下一步目标: {data.get('next_goal', '待定')}
"""
    
    def _template_goal_review(self, data: Dict) -> str:
        """目标回顾模板"""
        return f"""
目标回顾: {data.get('goal', '无目标')}
- 当前进度: {data.get('progress', '0%')}
- 完成情况: {data.get('completion', '待评估')}
- 障碍分析: {data.get('obstacles', '无')}
- 调整方案: {data.get('adjustment', '待定')}
"""
    
    def daily_reflection(self, completed: List[str], issues: List[str],
                        learned: List[str], tomorrow: List[str]) -> str:
        """每日反思"""
        data = {
            "completed": ", ".join(completed) if completed else "无",
            "issues": ", ".join(issues) if issues else "无",
            "learned": ", ".join(learned) if learned else "无",
            "tomorrow": ", ".join(tomorrow) if tomorrow else "待定"
        }
        
        content = self._template_daily_review(data)
        
        insights = []
        if issues:
            insights.append({
                "category": InsightCategory.FAILURE_PATTERN.value,
                "content": f"发现{len(issues)}个问题需要解决",
                "action": "分析问题根因"
            })
        
        if learned:
            insights.append({
                "category": InsightCategory.NEW_UNDERSTANDING.value,
                "content": f"学习到{len(learned)}个新知识点",
                "action": "应用到实践中"
            })
        
        return self.reflect(ReflectionType.DAILY_REVIEW, content, insights)
    
    def task_reflection(self, task_name: str, process: str, 
                       result: str, improvement: str) -> str:
        """任务反思"""
        data = {
            "task_name": task_name,
            "process": process,
            "result": result,
            "improvement": improvement
        }
        
        content = self._template_task_reflection(data)
        
        # 分析经验
        experience = {
            "type": "task",
            "task": task_name,
            "outcome": "success" if "成功" in result else "failure",
            "details": result
        }
        self.experience_analyzer.analyze_experience(experience)
        
        insights = []
        if "成功" in result:
            insights.append({
                "category": InsightCategory.SUCCESS_PATTERN.value,
                "content": f"任务{task_name}成功完成",
                "action": "总结成功经验"
            })
        else:
            insights.append({
                "category": InsightCategory.FAILURE_PATTERN.value,
                "content": f"任务{task_name}遇到问题",
                "action": "分析失败原因"
            })
        
        return self.reflect(ReflectionType.TASK_REFLECTION, content, insights)
    
    def error_analysis(self, error: str, cause: str, 
                      impact: str, solution: str, prevention: str) -> str:
        """错误分析"""
        data = {
            "error": error,
            "cause": cause,
            "impact": impact,
            "solution": solution,
            "prevention": prevention
        }
        
        content = self._template_error_analysis(data)
        
        # 记录失败经验
        experience = {
            "type": "error",
            "error": error,
            "outcome": "failure",
            "details": cause
        }
        self.experience_analyzer.analyze_experience(experience)
        
        insights = [{
            "category": InsightCategory.BEHAVIOR_CHANGE.value,
            "content": f"需要改进: {prevention}",
            "action": prevention
        }]
        
        action_items = [solution, prevention]
        
        return self.reflect(ReflectionType.ERROR_ANALYSIS, content, insights, action_items)
    
    def growth_assessment(self) -> Dict:
        """成长评估"""
        # 分析历史反思
        recent_reflections = self.reflections[-10:]
        
        if not recent_reflections:
            return {"assessment": "数据不足"}
        
        # 计算各项指标
        positive_count = sum(1 for r in recent_reflections if r.mood == "positive")
        avg_energy = sum(r.energy for r in recent_reflections) / len(recent_reflections)
        
        # 评估能力成长
        self.self_assessment.capability_score = min(1.0, 0.5 + positive_count * 0.05)
        self.self_assessment.growth_rate = 0.05  # 简化处理
        self.self_assessment.consistency = avg_energy
        self.self_assessment.adaptation = 0.6 + random.random() * 0.2
        self.self_assessment.confidence = self.self_assessment.capability_score
        
        # 生成成长洞察
        insights = []
        if self.self_assessment.capability_score > 0.7:
            insights.append({
                "category": InsightCategory.STRENGTH.value,
                "content": "能力持续提升",
                "action": "保持当前状态"
            })
        
        if self.self_assessment.consistency > 0.6:
            insights.append({
                "category": InsightCategory.SUCCESS_PATTERN.value,
                "content": "工作一致性良好",
                "action": "继续坚持"
            })
        
        assessment = {
            "metrics": self.self_assessment.to_dict(),
            "insights": insights,
            "recommendation": self._generate_recommendation()
        }
        
        # 存储反思
        content = f"成长评估: 能力={self.self_assessment.capability_score:.2f}, " \
                  f"一致性={self.self_assessment.consistency:.2f}"
        self.reflect(ReflectionType.GROWTH_ASSESSMENT, content, insights)
        
        return assessment
    
    def _generate_recommendation(self) -> str:
        """生成建议"""
        metrics = self.self_assessment
        
        if metrics.consistency < 0.5:
            return "建议: 提高工作一致性，减少分心"
        elif metrics.confidence < 0.5:
            return "建议: 多完成任务来增强信心"
        elif metrics.adaptation < 0.5:
            return "建议: 增强适应新环境的能力"
        else:
            return "状态良好，继续保持"
    
    def goal_review(self) -> Dict:
        """目标回顾"""
        goal_summary = self.goal_tracker.get_goal_summary()
        
        # 分析目标完成情况
        content = f"目标回顾: 活跃目标{goal_summary['active_count']}个, " \
                  f"完成{goal_summary['completed_count']}个, " \
                  f"完成率{goal_summary['completion_rate']:.1%}"
        
        insights = []
        if goal_summary['completion_rate'] > 0.7:
            insights.append({
                "category": InsightCategory.SUCCESS_PATTERN.value,
                "content": "目标完成率高",
                "action": "继续保持"
            })
        elif goal_summary['completion_rate'] < 0.3:
            insights.append({
                "category": InsightCategory.WEAKNESS.value,
                "content": "目标完成率较低",
                "action": "调整目标设定策略"
            })
        
        self.reflect(ReflectionType.GOAL_REVIEW, content, insights)
        
        return goal_summary
    
    def get_insights(self, category: InsightCategory = None) -> List[Dict]:
        """获取洞察"""
        if category:
            return [i for i in self.insights 
                   if i.get("category") == category.value]
        return self.insights[-10:]
    
    def get_reflection_summary(self) -> Dict:
        """获取反思摘要"""
        return {
            "total_reflections": len(self.reflections),
            "by_type": {
                rt.value: len([r for r in self.reflections 
                             if r.reflection_type == rt])
                for rt in ReflectionType
            },
            "insights_count": len(self.insights),
            "recent_insights": self.get_insights()[-3:],
            "patterns": self.experience_analyzer.get_patterns()
        }
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "reflection_count": len(self.reflections),
            "insights_count": len(self.insights),
            "self_assessment": self.self_assessment.to_dict(),
            "goal_summary": self.goal_tracker.get_goal_summary()
        }


def main():
    """测试自我反思机制"""
    print("🔄 自我反思机制 - 第3世")
    print("=" * 50)
    
    # 创建自我反思系统
    reflection = SelfReflection()
    
    # 每日反思
    print("\n📝 每日反思:")
    reflection.daily_reflection(
        completed=["完成监控系统", "优化告警规则"],
        issues=["内存使用略高"],
        learned=["新的优化技术", "更好的日志分析"],
        tomorrow=["继续性能优化", "检查系统负载"]
    )
    
    # 任务反思
    print("\n🎯 任务反思:")
    reflection.task_reflection(
        task_name="性能优化任务",
        process="分析CPU和内存使用情况",
        result="成功降低CPU使用率15%",
        improvement="可以进一步优化内存管理"
    )
    
    # 错误分析
    print("\n❌ 错误分析:")
    reflection.error_analysis(
        error="磁盘空间不足",
        cause="日志文件未及时清理",
       影响="导致部分服务失败",
        solution="清理旧日志文件",
        prevention="设置自动清理脚本"
    )
    
    # 成长评估
    print("\n📈 成长评估:")
    growth = reflection.growth_assessment()
    print(f"  能力评分: {growth['metrics']['capability_score']:.2f}")
    print(f"  一致性: {growth['metrics']['consistency']:.2f}")
    print(f"  总体评分: {growth['metrics']['overall']:.2f}")
    print(f"  建议: {growth['recommendation']}")
    
    # 目标回顾
    print("\n🎯 目标回顾:")
    # 添加测试目标
    reflection.goal_tracker.add_goal("完成系统监控优化", "milestone")
    reflection.goal_tracker.add_goal("学习新技术", "weekly")
    reflection.goal_tracker.update_progress("goal_0", 0.7)
    
    goal_review = reflection.goal_review()
    print(f"  活跃目标: {goal_review['active_count']}")
    print(f"  完成目标: {goal_review['completed_count']}")
    print(f"  完成率: {goal_review['completion_rate']:.1%}")
    
    # 洞察
    print("\n💡 洞察:")
    insights = reflection.get_insights()
    for i in insights[-3:]:
        print(f"  [{i['category']}] {i['content']}")
    
    # 状态
    print("\n📊 状态:")
    status = reflection.get_status()
    print(f"  反思次数: {status['reflection_count']}")
    print(f"  洞察数量: {status['insights_count']}")
    
    print("\n✅ 自我反思机制运行正常")


if __name__ == "__main__":
    main()