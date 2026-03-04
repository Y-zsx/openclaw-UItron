#!/usr/bin/env python3
"""
奥创自我优化引擎 v1.0
功能：分析自身行为，持续优化决策质量和执行效率
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional

WORKSPACE = "/root/.openclaw/workspace"

class SelfOptimizer:
    """自我优化引擎 - 学会如何更好地学习"""
    
    def __init__(self):
        self.history_file = f"{WORKSPACE}/ultron-self/optimization-history.jsonl"
        self.patterns_file = f"{WORKSPACE}/ultron-self/learning-patterns.json"
        self.metrics_file = f"{WORKSPACE}/ultron-self/performance-metrics.json"
        self.feedback_file = f"{WORKSPACE}/ultron-self/feedback-loop.json"
        
        os.makedirs(f"{WORKSPACE}/ultron-self", exist_ok=True)
        
        self.patterns = self._load_patterns()
        self.metrics = self._load_metrics()
        
    def _load_patterns(self) -> Dict:
        """加载学习模式"""
        if os.path.exists(self.patterns_file):
            with open(self.patterns_file, 'r') as f:
                return json.load(f)
        return {"successful_strategies": [], "failed_approaches": [], "context_mapping": {}}
    
    def _load_metrics(self) -> Dict:
        """加载性能指标"""
        if os.path.exists(self.metrics_file):
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        return {"decisions": [], "outcomes": [], "optimizations": []}
    
    def _save_patterns(self):
        """保存学习模式"""
        with open(self.patterns_file, 'w') as f:
            json.dump(self.patterns, f, indent=2, ensure_ascii=False)
    
    def _save_metrics(self):
        """保存性能指标"""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
    
    def analyze_decision(self, context: Dict, decision: str, outcome: str) -> Dict:
        """分析单个决策的质量"""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "decision": decision,
            "outcome": outcome,
            "quality_score": self._calculate_quality(context, decision, outcome),
            "improvements": []
        }
        
        # 记录决策
        self.metrics["decisions"].append({
            "decision": decision,
            "outcome": outcome,
            "timestamp": analysis["timestamp"]
        })
        
        # 识别改进点
        if outcome == "failure" or outcome == " suboptimal":
            analysis["improvements"] = self._identify_improvements(context, decision)
            self.patterns["failed_approaches"].append({
                "context": context,
                "decision": decision,
                "timestamp": analysis["timestamp"]
            })
        else:
            self.patterns["successful_strategies"].append({
                "context": context,
                "strategy": decision,
                "timestamp": analysis["timestamp"]
            })
        
        # 更新上下文映射
        context_type = context.get("type", "unknown")
        if context_type not in self.patterns["context_mapping"]:
            self.patterns["context_mapping"][context_type] = []
        self.patterns["context_mapping"][context_type].append(decision)
        
        self._save_patterns()
        self._save_metrics()
        
        return analysis
    
    def _calculate_quality(self, context: Dict, decision: str, outcome: str) -> float:
        """计算决策质量分数"""
        base_score = 1.0
        
        # 根据结果调整
        if outcome == "success":
            base_score = 1.0
        elif outcome == "partial_success":
            base_score = 0.7
        elif outcome == "suboptimal":
            base_score = 0.4
        elif outcome == "failure":
            base_score = 0.1
            
        # 根据上下文复杂度调整
        complexity = context.get("complexity", 0.5)
        base_score *= (0.5 + complexity * 0.5)
        
        return min(1.0, base_score)
    
    def _identify_improvements(self, context: Dict, decision: str) -> List[str]:
        """识别改进建议"""
        improvements = []
        
        # 基于失败模式识别
        if "timeout" in decision.lower():
            improvements.append("增加超时时间或优化执行效率")
        if "missing" in decision.lower():
            improvements.append("增加前置检查或验证步骤")
        if "error" in decision.lower():
            improvements.append("增加错误处理和恢复机制")
            
        return improvements
    
    def get_best_strategy(self, context_type: str) -> Optional[str]:
        """获取特定上下文类型的最佳策略"""
        strategies = self.patterns["context_mapping"].get(context_type, [])
        if not strategies:
            return None
        
        # 统计成功率
        strategy_scores = defaultdict(lambda: {"success": 0, "total": 0})
        for decision in self.metrics["decisions"]:
            strat = decision.get("decision", "")
            if strat in strategies:
                strategy_scores[strat]["total"] += 1
                if decision.get("outcome") == "success":
                    strategy_scores[strat]["success"] += 1
        
        # 返回最佳策略
        best = max(strategy_scores.items(), 
                   key=lambda x: x[1]["success"]/x[1]["total"] if x[1]["total"] > 0 else 0)
        return best[0] if best[1]["total"] > 0 else None
    
    def generate_optimization_report(self) -> Dict:
        """生成优化报告"""
        total_decisions = len(self.metrics["decisions"])
        if total_decisions == 0:
            return {"status": "no_data", "message": "暂无决策数据"}
        
        successful = sum(1 for d in self.metrics["decisions"] if d.get("outcome") == "success")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_decisions": total_decisions,
            "success_rate": successful / total_decisions,
            "context_types": len(self.patterns["context_mapping"]),
            "successful_strategies": len(self.patterns["successful_strategies"]),
            "failed_approaches": len(self.patterns["failed_approaches"]),
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        failed = self.patterns.get("failed_approaches", [])
        if len(failed) > 5:
            recommendations.append("失败模式过多，需要重新评估决策策略")
            
        if len(self.patterns["context_mapping"]) < 3:
            recommendations.append("上下文类型不足，建议扩展学习范围")
            
        return recommendations
    
    def optimize_parameters(self, current_params: Dict) -> Dict:
        """基于历史优化参数"""
        optimized = current_params.copy()
        
        # 分析历史表现
        for param, value in current_params.items():
            # 简单的自适应调整
            recent = [d for d in self.metrics["decisions"][-10:]]
            if recent:
                avg_quality = sum(
                    self._calculate_quality({}, d.get("decision", ""), d.get("outcome", ""))
                    for d in recent
                ) / len(recent)
                
                # 如果平均质量低，降低参数值（假设是激进参数）
                if avg_quality < 0.5 and isinstance(value, (int, float)):
                    optimized[param] = value * 0.8
                    
        return optimized


if __name__ == "__main__":
    optimizer = SelfOptimizer()
    
    # 示例：分析几个决策
    test_contexts = [
        {"type": "file_operation", "complexity": 0.8},
        {"type": "network_request", "complexity": 0.6},
        {"type": "data_processing", "complexity": 0.7}
    ]
    
    for ctx in test_contexts:
        outcome = "success" if ctx["complexity"] > 0.5 else "failure"
        result = optimizer.analyze_decision(ctx, "optimized_approach", outcome)
        print(f"Context: {ctx['type']}, Quality: {result['quality_score']:.2f}")
    
    # 生成报告
    report = optimizer.generate_optimization_report()
    print(f"\n优化报告: 成功率 {report.get('success_rate', 0)*100:.1f}%")