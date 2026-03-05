"""
反馈闭环模块
Feedback Loop - 从执行结果中学习和优化
"""
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class Feedback:
    """反馈数据"""
    decision_id: str
    action_id: str
    expected: Any          # 预期结果
    actual: Any            # 实际结果
    success: bool          # 是否成功
    delta: float = 0.0     # 差异度
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    
    def compute_delta(self):
        """计算差异度"""
        if self.expected is None or self.actual is None:
            self.delta = 0.0
            return
            
        try:
            if isinstance(self.expected, (int, float)) and isinstance(self.actual, (int, float)):
                self.delta = abs(float(self.expected) - float(self.actual))
            elif self.expected != self.actual:
                self.delta = 1.0
            else:
                self.delta = 0.0
        except:
            self.delta = 1.0 if self.expected != self.actual else 0.0
    
    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "action_id": self.action_id,
            "expected": str(self.expected),
            "actual": str(self.actual),
            "success": self.success,
            "delta": self.delta,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class LearningEntry:
    """学习条目"""
    pattern: str           # 模式标识
    context: Dict          # 上下文
    action: str            # 执行的动作
    result: bool           # 结果
    reward: float          # 奖励值
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "pattern": self.pattern,
            "context": self.context,
            "action": self.action,
            "result": self.result,
            "reward": self.reward,
            "timestamp": self.timestamp.isoformat()
        }


class FeedbackLoop:
    """
    反馈闭环系统
    收集执行结果，学习并优化决策
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.feedback_history: List[Feedback] = []
        self.learning_memory: List[LearningEntry] = []
        self.max_history = self.config.get("max_history", 5000)
        
        # 模式-动作-奖励 映射
        self.pattern_actions: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        
        # 统计
        self.stats = {
            "total_feedback": 0,
            "successful": 0,
            "failed": 0,
            "patterns_learned": 0
        }
        
        # 回调函数
        self.on_improvement: Callable[[Dict], None] = None
        
        logger.info("反馈闭环系统初始化完成")
        
    def collect(self, decision_id: str, action_id: str, expected: Any, actual: Any, metadata: Dict = None) -> Feedback:
        """收集反馈"""
        feedback = Feedback(
            decision_id=decision_id,
            action_id=action_id,
            expected=expected,
            actual=actual,
            success=expected == actual,
            metadata=metadata or {}
        )
        feedback.compute_delta()
        
        # 记录
        self.feedback_history.append(feedback)
        self.stats["total_feedback"] += 1
        
        if feedback.success:
            self.stats["successful"] += 1
        else:
            self.stats["failed"] += 1
            
        # 清理历史
        if len(self.feedback_history) > self.max_history:
            self.feedback_history = self.feedback_history[-self.max_history:]
            
        logger.info(f"反馈收集: {decision_id} - {action_id} - 成功: {feedback.success}")
        
        return feedback
    
    def learn(self, context: Dict, action: str, result: bool) -> LearningEntry:
        """学习 - 从结果中提取模式"""
        # 生成模式标识
        pattern = self._generate_pattern(context)
        
        # 计算奖励
        reward = 1.0 if result else -0.5
        
        entry = LearningEntry(
            pattern=pattern,
            context=context,
            action=action,
            result=result,
            reward=reward
        )
        
        # 更新模式-动作映射
        self.pattern_actions[pattern][action] += reward
        
        # 记录学习
        self.learning_memory.append(entry)
        self.stats["patterns_learned"] = len(self.pattern_actions)
        
        # 清理
        if len(self.learning_memory) > self.max_history:
            self.learning_memory = self.learning_memory[-self.max_history:]
            
        # 检查是否触发改进
        self._check_improvement(pattern)
        
        return entry
    
    def _generate_pattern(self, context: Dict) -> str:
        """生成模式标识"""
        # 简化: 使用关键指标生成模式
        key_metrics = []
        for key in ["cpu_percent", "memory_percent", "disk_percent", "error_count", "response_time"]:
            if key in context:
                value = context[key]
                if isinstance(value, (int, float)):
                    # 分桶
                    bucket = int(value / 20) * 20
                    key_metrics.append(f"{key}_{bucket}")
                    
        return "|".join(key_metrics) if key_metrics else "default"
    
    def _check_improvement(self, pattern: str):
        """检查是否需要改进"""
        if not self.on_improvement:
            return
            
        action_rewards = self.pattern_actions.get(pattern, {})
        if not action_rewards:
            return
            
        # 找到最佳动作
        best_action = max(action_rewards.items(), key=lambda x: x[1])
        
        # 如果最佳动作的奖励很低，可能需要改进
        if best_action[1] < 0:
            self.on_improvement({
                "pattern": pattern,
                "best_action": best_action[0],
                "reward": best_action[1],
                "suggestion": "考虑调整规则或参数"
            })
    
    def get_best_action(self, context: Dict) -> Optional[str]:
        """根据学习历史获取最佳动作"""
        pattern = self._generate_pattern(context)
        action_rewards = self.pattern_actions.get(pattern, {})
        
        if not action_rewards:
            return None
            
        best_action = max(action_rewards.items(), key=lambda x: x[1])
        return best_action[0] if best_action[1] > 0 else None
    
    def get_recommendations(self, context: Dict) -> List[Dict]:
        """获取优化建议"""
        recommendations = []
        
        pattern = self._generate_pattern(context)
        
        # 基于历史失败模式
        recent_failures = [
            f for f in self.feedback_history[-100:]
            if not f.success and f.decision_id == context.get("decision_id")
        ]
        
        if len(recent_failures) > 5:
            recommendations.append({
                "type": "pattern",
                "message": f"检测到重复失败模式: {len(recent_failures)}次失败",
                "confidence": 0.8
            })
            
        # 基于低奖励动作
        action_rewards = self.pattern_actions.get(pattern, {})
        for action, reward in action_rewards.items():
            if reward < -1.0:
                recommendations.append({
                    "type": "action",
                    "action": action,
                    "message": f"动作 '{action}' 在当前模式下表现不佳",
                    "reward": reward,
                    "confidence": min(1.0, abs(reward) / 5.0)
                })
                
        return recommendations
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            "feedback_count": len(self.feedback_history),
            "learning_entries": len(self.learning_memory),
            "unique_patterns": len(self.pattern_actions),
            "success_rate": self.stats["successful"] / self.stats["total_feedback"] if self.stats["total_feedback"] > 0 else 0
        }
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """获取反馈历史"""
        return [f.to_dict() for f in self.feedback_history[-limit:]]
    
    def export_learnings(self) -> Dict:
        """导出学习结果"""
        return {
            "patterns": dict(self.pattern_actions),
            "stats": self.get_stats(),
            "export_time": datetime.now().isoformat()
        }
    
    def import_learnings(self, data: Dict):
        """导入学习结果"""
        if "patterns" in data:
            for pattern, actions in data["patterns"].items():
                self.pattern_actions[pattern] = defaultdict(float, actions)
        logger.info("学习数据导入完成")