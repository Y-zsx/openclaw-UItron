"""
反馈闭环模块 V2 - 增强版
Feedback Loop - 从执行结果中学习和优化
增强功能:
- 自适应学习率
- 模式聚类
- 预测性反馈
- 自动规则优化
"""
import logging
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json
import math

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


class AdaptiveLearningRate:
    """
    自适应学习率控制器
    根据决策结果动态调整学习率
    """
    
    def __init__(self, base_rate: float = 0.1, min_rate: float = 0.01, max_rate: float = 0.5):
        self.base_rate = base_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.success_streak = 0
        self.failure_streak = 0
        self.current_rate = base_rate
        self.history: List[float] = []
        
    def compute(self, success: bool, context: Dict = None) -> float:
        """计算当前学习率"""
        if success:
            self.success_streak += 1
            self.failure_streak = 0
            
            # 连续成功时降低学习率（保守策略）
            if self.success_streak >= 5:
                self.current_rate = max(self.min_rate, self.current_rate * 0.9)
        else:
            self.failure_streak += 1
            self.success_streak = 0
            
            # 连续失败时提高学习率（激进策略）
            if self.failure_streak >= 3:
                self.current_rate = min(self.max_rate, self.current_rate * 1.5)
                
        # 考虑上下文影响
        if context:
            urgency = context.get("urgency", 0.5)
            self.current_rate = min(self.max_rate, self.current_rate * (1 + urgency))
            
        self.history.append(self.current_rate)
        return self.current_rate
    
    def get_stats(self) -> Dict:
        return {
            "current_rate": self.current_rate,
            "success_streak": self.success_streak,
            "failure_streak": self.failure_streak,
            "history_samples": len(self.history)
        }


class PatternCluster:
    """
    模式聚类器
    将相似的上下文模式聚合在一起
    """
    
    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        self.clusters: Dict[str, List[Dict]] = defaultdict(list)
        self.cluster_centers: Dict[str, Dict] = {}
        
    def _extract_features(self, context: Dict) -> List[float]:
        """提取特征向量"""
        features = []
        numeric_keys = ["cpu_percent", "memory_percent", "disk_percent", 
                       "error_count", "response_time", "load_avg"]
        for key in numeric_keys:
            features.append(float(context.get(key, 0)))
        return features
    
    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """计算余弦相似度"""
        if not v1 or not v2:
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        mag1 = math.sqrt(sum(a * a for a in v1))
        mag2 = math.sqrt(sum(b * b for b in v2))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)
    
    def add_context(self, context: Dict, action: str, result: bool):
        """添加上下文到聚类"""
        features = self._extract_features(context)
        cluster_key = self._find_cluster(features)
        
        if cluster_key is None:
            # 创建新聚类
            cluster_key = f"cluster_{len(self.clusters)}"
            self.cluster_centers[cluster_key] = features
            
        self.clusters[cluster_key].append({
            "context": context,
            "action": action,
            "result": result,
            "features": features
        })
        
        # 更新聚类中心
        self._update_center(cluster_key)
        
    def _find_cluster(self, features: List[float]) -> Optional[str]:
        """找到最相似的聚类"""
        best_cluster = None
        best_similarity = 0
        
        for cluster_id, center in self.cluster_centers.items():
            sim = self._cosine_similarity(features, center)
            if sim > best_similarity and sim >= self.similarity_threshold:
                best_similarity = sim
                best_cluster = cluster_id
                
        return best_cluster
    
    def _update_center(self, cluster_key: str):
        """更新聚类中心"""
        members = self.clusters[cluster_key]
        if not members:
            return
            
        num_features = len(members[0]["features"]) if members else 0
        if num_features == 0:
            return
            
        center = []
        for i in range(num_features):
            center.append(sum(m["features"][i] for m in members) / len(members))
            
        self.cluster_centers[cluster_key] = center
        
    def get_cluster_insights(self) -> List[Dict]:
        """获取聚类洞察"""
        insights = []
        for cluster_id, members in self.clusters.items():
            if not members:
                continue
                
            success_count = sum(1 for m in members if m["result"])
            total = len(members)
            
            # 找出最佳动作
            action_results = defaultdict(lambda: {"success": 0, "total": 0})
            for m in members:
                action_results[m["action"]]["total"] += 1
                if m["result"]:
                    action_results[m["action"]]["success"] += 1
                    
            best_action = max(action_results.items(), 
                            key=lambda x: x[1]["success"] / x[1]["total"] if x[1]["total"] > 0 else 0)
            
            insights.append({
                "cluster_id": cluster_id,
                "size": total,
                "success_rate": success_count / total,
                "best_action": best_action[0] if best_action[1]["total"] > 0 else None,
                "best_action_success_rate": best_action[1]["success"] / best_action[1]["total"] if best_action[1]["total"] > 0 else 0
            })
            
        return insights


class PredictiveFeedback:
    """
    预测性反馈系统
    基于历史模式预测潜在问题
    """
    
    def __init__(self, prediction_window: int = 10):
        self.prediction_window = prediction_window
        self.recent_contexts: List[Dict] = []
        self.failure_sequences: List[List[Dict]] = []
        self.current_sequence: List[Dict] = []
        
    def add_outcome(self, context: Dict, result: bool):
        """添加结果用于预测"""
        entry = {"context": context, "result": result, "timestamp": datetime.now()}
        
        self.recent_contexts.append(entry)
        self.current_sequence.append(entry)
        
        if not result:
            # 记录失败序列
            if len(self.current_sequence) > 1:
                self.failure_sequences.append(self.current_sequence[:-1].copy())
                self.current_sequence = []
        else:
            # 成功后清空当前序列
            self.current_sequence = []
            
        # 保持历史大小
        if len(self.recent_contexts) > self.prediction_window * 10:
            self.recent_contexts = self.recent_contexts[-self.prediction_window:]
            
    def predict_failures(self, current_context: Dict) -> List[Dict]:
        """预测可能的失败"""
        predictions = []
        
        # 检查相似失败序列
        for sequence in self.failure_sequences[-5:]:
            if not sequence:
                continue
            # 检查当前上下文是否匹配失败序列的前置条件
            match_score = self._context_similarity(current_context, sequence[0]["context"])
            if match_score > 0.6:
                predictions.append({
                    "type": "sequence_pattern",
                    "confidence": match_score,
                    "message": "检测到可能导致失败的上下文模式",
                    "suggested_action": "放缓或重新评估"
                })
                
        # 检查近期失败率趋势
        recent = self.recent_contexts[-self.prediction_window:]
        if recent:
            failure_rate = sum(1 for r in recent if not r["result"]) / len(recent)
            if failure_rate > 0.5:
                predictions.append({
                    "type": "high_failure_rate",
                    "confidence": failure_rate,
                    "message": f"近期失败率较高: {failure_rate:.1%}",
                    "suggested_action": "系统可能处于不稳定状态"
                })
                
        return predictions
    
    def _context_similarity(self, c1: Dict, c2: Dict) -> float:
        """计算上下文相似度"""
        keys = set(c1.keys()) & set(c2.keys())
        if not keys:
            return 0.0
            
        matches = 0
        for key in keys:
            if c1.get(key) == c2.get(key):
                matches += 1
                
        return matches / len(keys)


class AutoRuleOptimizer:
    """
    自动规则优化器
    基于学习结果自动调整规则参数
    """
    
    def __init__(self, feedback_loop: FeedbackLoop):
        self.feedback_loop = feedback_loop
        self.optimization_history: List[Dict] = []
        self.rules_adjustments: Dict[str, Dict] = {}
        
    def analyze_and_optimize(self, rules: List[Dict]) -> List[Dict]:
        """分析并优化规则"""
        recommendations = []
        
        # 获取所有模式的学习结果
        for pattern, action_rewards in self.feedback_loop.pattern_actions.items():
            if not action_rewards:
                continue
                
            # 找出表现差的动作
            for action, reward in action_rewards.items():
                if reward < -1.0:
                    # 查找对应的规则
                    for rule in rules:
                        if rule.get("action") == action:
                            # 计算调整建议
                            adjustment = self._calculate_adjustment(rule, reward)
                            recommendations.append({
                                "rule_id": rule.get("id"),
                                "action": action,
                                "current_value": rule.get("threshold"),
                                "suggested_adjustment": adjustment,
                                "reason": f"模式 '{pattern}' 下奖励过低 ({reward})"
                            })
                            
                            # 记录调整
                            self.rules_adjustments[rule.get("id", action)] = {
                                "adjustment": adjustment,
                                "timestamp": datetime.now().isoformat()
                            }
                            
        self.optimization_history.append({
            "timestamp": datetime.now().isoformat(),
            "recommendations": recommendations
        })
        
        return recommendations
    
    def _calculate_adjustment(self, rule: Dict, reward: float) -> Dict:
        """计算调整幅度"""
        current = rule.get("threshold", 50)
        
        # 根据奖励值计算调整方向和幅度
        if reward < -2.0:
            # 严重不足，大幅调整
            adjustment_ratio = 0.7 if "upper" in str(rule.get("type", "")).lower() else 1.3
        elif reward < -1.0:
            adjustment_ratio = 0.85 if "upper" in str(rule.get("type", "")).lower() else 1.15
        else:
            adjustment_ratio = 0.95 if "upper" in str(rule.get("type", "")).lower() else 1.05
            
        new_value = int(current * adjustment_ratio)
        
        return {
            "old_value": current,
            "new_value": new_value,
            "ratio": adjustment_ratio,
            "direction": "decrease" if adjustment_ratio < 1 else "increase"
        }
    
    def get_optimization_stats(self) -> Dict:
        """获取优化统计"""
        return {
            "total_optimizations": len(self.optimization_history),
            "active_adjustments": len(self.rules_adjustments),
            "last_optimization": self.optimization_history[-1] if self.optimization_history else None
        }


class EnhancedFeedbackLoop(FeedbackLoop):
    """
    增强版反馈闭环系统
    整合所有增强功能
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        # 增强功能
        self.learning_rate = AdaptiveLearningRate()
        self.pattern_cluster = PatternCluster()
        self.predictor = PredictiveFeedback()
        self.optimizer = AutoRuleOptimizer(self)
        
        self.config = config or {}
        
    def collect_enhanced(self, decision_id: str, action_id: str, 
                         expected: Any, actual: Any, 
                         context: Dict = None,
                         action: str = None,
                         metadata: Dict = None) -> Feedback:
        """增强版收集反馈"""
        # 基础反馈收集
        feedback = self.collect(decision_id, action_id, expected, actual, metadata)
        
        if context:
            # 自适应学习率
            rate = self.learning_rate.compute(feedback.success, context)
            
            # 模式聚类
            self.pattern_cluster.add_context(context, action or action_id, feedback.success)
            
            # 预测性反馈
            self.predictor.add_outcome(context, feedback.success)
            
            # 学习
            self.learn(context, action or action_id, feedback.success)
            
        return feedback
    
    def get_enhanced_stats(self) -> Dict:
        """获取增强统计"""
        base_stats = self.get_stats()
        
        return {
            **base_stats,
            "learning_rate": self.learning_rate.get_stats(),
            "pattern_clusters": len(self.pattern_cluster.clusters),
            "cluster_insights": self.pattern_cluster.get_cluster_insights(),
            "predictor_predictions": len(self.predictor.failure_sequences),
            "optimization": self.optimizer.get_optimization_stats()
        }
    
    def get_predictions(self, context: Dict) -> List[Dict]:
        """获取预测"""
        return self.predictor.predict_failures(context)
    
    def optimize_rules(self, rules: List[Dict]) -> List[Dict]:
        """优化规则"""
        return self.optimizer.analyze_and_optimize(rules)