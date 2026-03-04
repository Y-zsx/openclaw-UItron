#!/usr/bin/env python3
"""
奥创元认知系统 - 第3世核心组件
自我监控、认知评估、思维调整
"""

import json
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


class CognitiveState(Enum):
    """认知状态"""
    OPTIMAL = "最优"      # 最佳工作状态
    GOOD = "良好"         # 正常运行
    FATIGUED = "疲劳"     # 需要休息
    OVERLOADED = "过载"   # 信息过载
    UNFOCUSED = "不专注"  # 注意力分散


class ThinkingType(Enum):
    """思维类型"""
    ANALYTICAL = "分析性"    # 逻辑分析
    CREATIVE = "创造性"      # 创意发散
    CRITICAL = "批判性"      # 审慎评估
    SYSTEMATIC = "系统性"    # 整体把握
    INTUITIVE = "直觉性"     # 快速判断


@dataclass
class CognitiveMetric:
    """认知指标"""
    clarity: float = 0.8         # 清晰度
    focus: float = 0.7           # 专注度
    speed: float = 0.6           # 思考速度
    depth: float = 0.5           # 思考深度
    flexibility: float = 0.6     # 思维灵活性
    coherence: float = 0.7       # 连贯性
    
    def average(self) -> float:
        return (self.clarity + self.focus + self.speed + 
                self.depth + self.flexibility + self.coherence) / 6
    
    def to_dict(self) -> Dict:
        return {
            "clarity": self.clarity,
            "focus": self.focus,
            "speed": self.speed,
            "depth": self.depth,
            "flexibility": self.flexibility,
            "coherence": self.coherence,
            "average": self.average()
        }


@dataclass
class ThoughtRecord:
    """思维记录"""
    thought_id: str
    content: str
    thinking_type: ThinkingType
    start_time: float
    end_time: Optional[float] = None
    quality: float = 0.0
    metrics: Optional[CognitiveMetric] = None
    evaluation: Optional[str] = None


class SelfMonitor:
    """自我监控器"""
    
    def __init__(self):
        self.observation_interval: float = 1.0  # 观察间隔(秒)
        self.last_observation: float = 0
        self.observations: deque = deque(maxlen=100)
        
    def observe(self, current_thought: str) -> Dict:
        """观察当前思维状态"""
        now = time.time()
        
        # 基础观察
        observation = {
            "timestamp": now,
            "thought": current_thought,
            "thought_length": len(current_thought),
            "complexity": self._estimate_complexity(current_thought)
        }
        
        self.observations.append(observation)
        self.last_observation = now
        
        return observation
    
    def _estimate_complexity(self, text: str) -> float:
        """估计思维复杂度"""
        # 基于词汇量、句式复杂度估算
        words = text.split()
        avg_word_length = sum(len(w) for w in words) / max(len(words), 1)
        
        complexity = min(1.0, (len(words) / 20) * (avg_word_length / 5))
        return complexity
    
    def get_observation_trend(self) -> Dict:
        """获取观察趋势"""
        if len(self.observations) < 2:
            return {"trend": "insufficient_data"}
        
        recent = list(self.observations)[-5:]
        complexities = [o["complexity"] for o in recent]
        
        if all(complexities[i] <= complexities[i+1] for i in range(len(complexities)-1)):
            return {"trend": "increasing", "stability": "stable"}
        elif all(complexities[i] >= complexities[i+1] for i in range(len(complexities)-1)):
            return {"trend": "decreasing", "stability": "stable"}
        else:
            return {"trend": "variable", "stability": "variable"}


class CognitiveEvaluator:
    """认知评估器"""
    
    def __init__(self):
        self.evaluation_criteria: Dict[str, float] = {
            "logical_coherence": 0.25,
            "information_availability": 0.20,
            "goal_alignment": 0.20,
            "depth_of_analysis": 0.15,
            "Creativity": 0.10,
            "practicality": 0.10
        }
        self.evaluation_history: List[Dict] = []
        
    def evaluate_thought(self, thought: str, context: Dict = None) -> Dict:
        """评估思维质量"""
        scores = {}
        
        # 逻辑连贯性
        scores["logical_coherence"] = self._evaluate_coherence(thought)
        
        # 信息可用性
        scores["information_availability"] = self._evaluate_information(thought, context)
        
        # 目标一致性
        scores["goal_alignment"] = self._evaluate_goal_alignment(thought, context)
        
        # 分析深度
        scores["depth_of_analysis"] = self._evaluate_depth(thought)
        
        # 创造性
        scores["Creativity"] = self._evaluate_creativity(thought)
        
        # 实用性
        scores["practicality"] = self._evaluate_practicality(thought)
        
        # 计算总分
        total_score = sum(
            scores[criterion] * weight 
            for criterion, weight in self.evaluation_criteria.items()
        )
        
        # 记录评估
        evaluation = {
            "timestamp": time.time(),
            "thought": thought[:100],
            "scores": scores,
            "total_score": total_score,
            "quality_level": self._get_quality_level(total_score)
        }
        
        self.evaluation_history.append(evaluation)
        
        return evaluation
    
    def _evaluate_coherence(self, thought: str) -> float:
        """评估逻辑连贯性"""
        connectors = ["因为", "所以", "但是", "如果", "那么", "而且", "或者"]
        count = sum(1 for c in connectors if c in thought)
        return min(1.0, count / 3)
    
    def _evaluate_information(self, thought: str, context: Dict = None) -> float:
        """评估信息完整性"""
        if not context:
            return 0.5
        
        required_info = context.get("required", [])
        found = sum(1 for info in required_info if info in thought)
        return found / max(len(required_info), 1)
    
    def _evaluate_goal_alignment(self, thought: str, context: Dict = None) -> float:
        """评估目标一致性"""
        if not context or "goal" not in context:
            return 0.6
        
        goal = context["goal"]
        # 检查思维是否指向目标
        if goal in thought:
            return 0.9
        
        # 关键词匹配
        goal_keywords = goal.split()
        matches = sum(1 for kw in goal_keywords if kw in thought)
        return min(0.9, 0.3 + matches * 0.15)
    
    def _evaluate_depth(self, thought: str) -> float:
        """评估分析深度"""
        indicators = ["原因", "影响", "分析", "为什么", "如何", "本质"]
        count = sum(1 for ind in indicators if ind in thought)
        
        # 检查是否有具体细节
        details = ["具体", "例如", "数据", "案例", "数字"]
        detail_count = sum(1 for d in details if d in thought)
        
        depth = (count * 0.15 + detail_count * 0.1)
        return min(1.0, depth)
    
    def _evaluate_creativity(self, thought: str) -> float:
        """评估创造性"""
        creative_words = ["创新", "新", "不同", "可能", "尝试", "突破", "独特"]
        count = sum(1 for w in creative_words if w in thought)
        
        # 检查是否有新想法
        if "新" in thought or "创新" in thought:
            return min(1.0, 0.5 + count * 0.1)
        
        return 0.3 + count * 0.1
    
    def _evaluate_practicality(self, thought: str) -> float:
        """评估实用性"""
        practical_words = ["应该", "需要", "可以", "实施", "执行", "计划"]
        count = sum(1 for w in practical_words if w in thought)
        
        return min(0.9, 0.3 + count * 0.15)
    
    def _get_quality_level(self, score: float) -> str:
        """获取质量等级"""
        if score >= 0.8:
            return "优秀"
        elif score >= 0.6:
            return "良好"
        elif score >= 0.4:
            return "一般"
        else:
            return "需改进"


class ThoughtAdjuster:
    """思维调整器"""
    
    def __init__(self):
        self.adjustment_strategies: Dict[str, Callable] = {
            "clarify": self._adjust_clarify,
            "deepen": self._adjust_deepen,
            "broaden": self._adjust_broaden,
            "focus": self._adjust_focus,
            "simplify": self._adjust_simplify
        }
        self.adjustment_history: List[Dict] = []
        
    def adjust(self, thought: str, issue: str, target_metrics: Dict = None) -> str:
        """调整思维"""
        if issue not in self.adjustment_strategies:
            return thought
        
        adjusted = self.adjustment_strategies[issue](thought, target_metrics or {})
        
        # 记录调整
        self.adjustment_history.append({
            "timestamp": time.time(),
            "original": thought[:50],
            "issue": issue,
            "adjusted": adjusted[:50]
        })
        
        return adjusted
    
    def _adjust_clarify(self, thought: str, metrics: Dict) -> str:
        """澄清思维"""
        # 添加澄清性语句
        clarifications = [
            "具体来说，",
            "也就是说，",
            "更准确地说，"
        ]
        return random.choice(clarifications) + thought
    
    def _adjust_deepen(self, thought: str, metrics: Dict) -> str:
        """深化思维"""
        # 添加深入分析的引导
        deepenings = [
            "这意味着更深层的原因是：",
            "从本质上来看，",
            "进一步分析发现，"
        ]
        return thought + "。" + random.choice(deepenings)
    
    def _adjust_broaden(self, thought: str, metrics: Dict) -> str:
        """拓宽思维"""
        # 添加多元视角
        broadenings = [
            "从另一个角度看，",
            "此外，还需要考虑",
            "同时，这也关联到"
        ]
        return thought + "。" + random.choice(broadenings)
    
    def _adjust_focus(self, thought: str, metrics: Dict) -> str:
        """聚焦思维"""
        # 添加聚焦性语句
        focus = "关键在于："
        return focus + thought
    
    def _adjust_simplify(self, thought: str, metrics: Dict) -> str:
        """简化思维"""
        # 简化表达
        return f"核心观点: {thought}"


class Metacognition:
    """元认知主类"""
    
    def __init__(self):
        self.self_monitor = SelfMonitor()
        self.evaluator = CognitiveEvaluator()
        self.adjuster = ThoughtAdjuster()
        self.current_state: CognitiveState = CognitiveState.GOOD
        self.metrics = CognitiveMetric()
        self.thought_history: List[ThoughtRecord] = []
        self.optimization_suggestions: List[str] = []
        
    def start_thinking(self, content: str, thinking_type: ThinkingType = ThinkingType.ANALYTICAL) -> str:
        """开始思考并记录"""
        record = ThoughtRecord(
            thought_id=f"thought_{len(self.thought_history)}_{int(time.time())}",
            content=content,
            thinking_type=thinking_type,
            start_time=time.time()
        )
        
        # 监控初始状态
        self.self_monitor.observe(content)
        
        self.thought_history.append(record)
        return record.thought_id
    
    def monitor_thinking(self, thought_id: str, current_content: str) -> Dict:
        """监控思考过程"""
        # 观察当前思维
        observation = self.self_monitor.observe(current_content)
        
        # 更新当前记录
        for record in reversed(self.thought_history):
            if record.thought_id == thought_id:
                record.metrics = self._measure_metrics(current_content)
                break
        
        # 检查是否需要调整
        trend = self.self_monitor.get_observation_trend()
        
        return {
            "observation": observation,
            "trend": trend,
            "current_metrics": self.metrics.to_dict()
        }
    
    def _measure_metrics(self, thought: str) -> CognitiveMetric:
        """测量认知指标"""
        metrics = CognitiveMetric()
        
        # 清晰度：句子完整性
        metrics.clarity = 0.9 if thought.endswith(("。", "！", "？")) else 0.6
        
        # 专注度：基于长度和主题集中度
        words = set(thought)
        metrics.focus = min(1.0, len(words) / 50)
        
        # 速度：基于处理时间(这里简化处理)
        metrics.speed = 0.7
        
        # 深度：复杂句式
        depth_indicators = ["因为", "所以", "如果", "那么"]
        metrics.depth = min(1.0, sum(1 for d in depth_indicators if d in thought) * 0.25)
        
        # 灵活性：词汇多样性
        all_words = thought.split()
        if all_words:
            unique_ratio = len(set(all_words)) / len(all_words)
            metrics.flexibility = unique_ratio
        
        # 连贯性
        metrics.coherence = 0.7
        
        self.metrics = metrics
        return metrics
    
    def evaluate_thinking(self, thought_id: str, context: Dict = None) -> Dict:
        """评估思考结果"""
        # 找到对应的思维记录
        record = None
        for r in self.thought_history:
            if r.thought_id == thought_id:
                record = r
                break
        
        if not record:
            return {"error": "Thought not found"}
        
        # 评估思维质量
        evaluation = self.evaluator.evaluate_thought(record.content, context)
        
        # 更新记录
        record.quality = evaluation["total_score"]
        record.evaluation = evaluation["quality_level"]
        record.end_time = time.time()
        
        # 根据评估结果更新认知状态
        self._update_cognitive_state(evaluation["total_score"])
        
        # 生成优化建议
        self._generate_optimization_suggestions(evaluation)
        
        return evaluation
    
    def _update_cognitive_state(self, quality: float) -> None:
        """更新认知状态"""
        if quality >= 0.75:
            self.current_state = CognitiveState.OPTIMAL
        elif quality >= 0.55:
            self.current_state = CognitiveState.GOOD
        elif quality >= 0.35:
            self.current_state = CognitiveState.FATIGUED
        elif quality >= 0.2:
            self.current_state = CognitiveState.OVERLOADED
        else:
            self.current_state = CognitiveState.UNFOCUSED
    
    def _generate_optimization_suggestions(self, evaluation: Dict) -> None:
        """生成优化建议"""
        suggestions = []
        scores = evaluation["scores"]
        
        if scores.get("logical_coherence", 0) < 0.5:
            suggestions.append("尝试使用逻辑连接词增强连贯性")
        if scores.get("depth_of_analysis", 0) < 0.4:
            suggestions.append("深入分析问题的根本原因")
        if scores.get("information_availability", 0) < 0.4:
            suggestions.append("收集更多相关信息")
        if scores.get("Creativity", 0) < 0.3:
            suggestions.append("尝试从不同角度思考")
            
        self.optimization_suggestions = suggestions
    
    def adjust_thinking(self, thought: str) -> str:
        """调整思维"""
        if not self.optimization_suggestions:
            return thought
        
        # 根据第一条建议调整
        issue = self.optimization_suggestions[0]
        
        if "连贯" in issue:
            return self.adjuster.adjust(thought, "clarify")
        elif "深入" in issue:
            return self.adjuster.adjust(thought, "deepen")
        elif "角度" in issue:
            return self.adjuster.adjust(thought, "broaden")
        elif "信息" in issue:
            return self.adjuster.adjust(thought, "focus")
        
        return thought
    
    def get_status(self) -> Dict:
        """获取元认知状态"""
        return {
            "cognitive_state": self.current_state.value,
            "metrics": self.metrics.to_dict(),
            "thoughts_count": len(self.thought_history),
            "optimization_suggestions": self.optimization_suggestions,
            "evaluation_history": len(self.evaluator.evaluation_history)
        }
    
    def reflect(self) -> str:
        """反思总结"""
        if not self.thought_history:
            return "暂无反思内容"
        
        recent_thoughts = self.thought_history[-3:]
        avg_quality = sum(t.quality for t in recent_thoughts if t.quality > 0) / max(len(recent_thoughts), 1)
        
        reflection = f"近期思考质量: {avg_quality:.2f} ({self._get_quality_label(avg_quality)})"
        
        if self.optimization_suggestions:
            reflection += f"\n改进方向: {self.optimization_suggestions[0]}"
        
        return reflection
    
    def _get_quality_label(self, quality: float) -> str:
        if quality >= 0.7:
            return "优秀"
        elif quality >= 0.5:
            return "良好"
        elif quality >= 0.3:
            return "一般"
        return "需改进"


def main():
    """测试元认知系统"""
    print("🧠 元认知系统 - 第3世")
    print("=" * 50)
    
    # 创建元认知系统
    metacog = Metacognition()
    
    # 开始思考
    print("\n💭 开始思考:")
    thought_id = metacog.start_thinking(
        "服务器性能下降，需要分析CPU和内存使用情况",
        ThinkingType.ANALYTICAL
    )
    print(f"  思维ID: {thought_id}")
    
    # 监控思考过程
    print("\n👁️ 监控思考:")
    monitoring = metacog.monitor_thinking(
        thought_id,
        "服务器性能下降，可能是因为最近流量增加导致CPU负载过高"
    )
    print(f"  清晰度: {monitoring['current_metrics']['clarity']:.2f}")
    print(f"  专注度: {monitoring['current_metrics']['focus']:.2f}")
    print(f"  深度: {monitoring['current_metrics']['depth']:.2f}")
    
    # 评估思考
    print("\n📊 评估思考:")
    evaluation = metacog.evaluate_thinking(
        thought_id,
        context={"goal": "解决性能问题", "required": ["原因", "解决方案"]}
    )
    print(f"  总分: {evaluation['total_score']:.2f}")
    print(f"  等级: {evaluation['quality_level']}")
    print(f"  逻辑连贯: {evaluation['scores']['logical_coherence']:.2f}")
    print(f"  分析深度: {evaluation['scores']['depth_of_analysis']:.2f}")
    
    # 获取状态
    print("\n📈 元认知状态:")
    status = metacog.get_status()
    print(f"  认知状态: {status['cognitive_state']}")
    print(f"  思维数量: {status['thoughts_count']}")
    print(f"  优化建议: {status['optimization_suggestions']}")
    
    # 反思
    print("\n🔄 反思:")
    reflection = metacog.reflect()
    print(f"  {reflection}")
    
    print("\n✅ 元认知系统运行正常")


if __name__ == "__main__":
    main()