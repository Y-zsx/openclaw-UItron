#!/usr/bin/env python3
"""
奥创预测器 - 第3世：预测性进化
功能：未来状态预测 + 主动能力获取 + 自我升级机制
"""

import json
import os
import datetime
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import deque
import statistics
import random

# ==================== 数据结构 ====================

@dataclass
class StatePrediction:
    """状态预测"""
    metric: str
    current_value: float
    predicted_value: float
    confidence: float
    time_horizon: int  # 预测时间范围（分钟）
    trend: str  # rising, falling, stable
    recommendation: str

@dataclass
class CapabilityNeed:
    """能力需求"""
    capability: str
    urgency: float  # 0-1
    reason: str
    estimated_acquisition_time: int  # 分钟
    prerequisites: List[str]

@dataclass
class SelfUpgrade:
    """自我升级记录"""
    id: str
    timestamp: str
    upgrade_type: str
    trigger: str
    changes: Dict[str, Any]
    success: bool
    impact: float


# ==================== 未来状态预测器 ====================

class FutureStatePredictor:
    """未来状态预测器"""
    
    def __init__(self, history_path: str = None):
        self.history_path = history_path or "/root/.openclaw/workspace/ultron/logs/metrics_history.json"
        self.state_history: Dict[str, deque] = {}  # metric -> deque of (timestamp, value)
        self.predictions: List[StatePrediction] = []
        self._load_history()
    
    def _load_history(self):
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r') as f:
                    data = json.load(f)
                    # 转换为deque
                    for metric, values in data.get("metrics", {}).items():
                        self.state_history[metric] = deque(values[-100:], maxlen=100)
            except:
                pass
    
    def _save_history(self):
        data = {
            "metrics": {k: list(v) for k, v in self.state_history.items()},
            "last_updated": datetime.datetime.now().isoformat()
        }
        Path(self.history_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def record_state(self, metric: str, value: float):
        """记录状态"""
        timestamp = time.time()
        
        if metric not in self.state_history:
            self.state_history[metric] = deque(maxlen=100)
        
        self.state_history[metric].append((timestamp, value))
        self._save_history()
    
    def predict(self, metric: str, time_horizon: int = 30) -> Optional[StatePrediction]:
        """预测未来状态"""
        if metric not in self.state_history or len(self.state_history[metric]) < 5:
            return None
        
        history = list(self.state_history[metric])
        values = [v for _, v in history]
        
        # 简单线性回归
        n = len(values)
        x = list(range(n))
        
        # 计算趋势
        if n >= 10:
            # 使用最近的值
            recent = values[-10:]
            if len(set(recent)) == 1:
                trend = "stable"
                predicted = values[-1]
            else:
                # 计算趋势
                diff = recent[-1] - recent[0]
                if diff > 0.1:
                    trend = "rising"
                    # 预测增长
                    avg_change = diff / 9
                    predicted = values[-1] + avg_change * (time_horizon / 10)
                elif diff < -0.1:
                    trend = "falling"
                    avg_change = diff / 9
                    predicted = values[-1] + avg_change * (time_horizon / 10)
                else:
                    trend = "stable"
                    predicted = values[-1]
        else:
            trend = "stable"
            predicted = statistics.mean(values)
        
        # 计算置信度（基于数据量和稳定性）
        confidence = min(0.9, len(values) / 50 + 0.3)
        if trend == "stable":
            confidence += 0.1
        
        # 生成建议
        recommendation = self._generate_recommendation(metric, predicted, trend)
        
        return StatePrediction(
            metric=metric,
            current_value=values[-1],
            predicted_value=predicted,
            confidence=confidence,
            time_horizon=time_horizon,
            trend=trend,
            recommendation=recommendation
        )
    
    def _generate_recommendation(self, metric: str, predicted: float, trend: str) -> str:
        """生成建议"""
        if metric == "cpu_usage":
            if predicted > 80:
                return "CPU使用率将升高，考虑启动优化"
            elif predicted < 20:
                return "CPU空闲，可以处理更多任务"
        
        if metric == "memory_usage":
            if predicted > 85:
                return "内存即将不足，建议释放"
            elif predicted < 30:
                return "内存充足，可增加缓存"
        
        if metric == "disk_usage":
            if predicted > 90:
                return "磁盘空间不足，紧急清理"
            elif predicted > 80:
                return "磁盘空间紧张，计划清理"
        
        if metric == "response_time":
            if trend == "rising":
                return "响应时间上升，检查性能"
        
        return "状态正常"
    
    def predict_all(self, time_horizon: int = 30) -> List[StatePrediction]:
        """预测所有指标"""
        predictions = []
        for metric in self.state_history.keys():
            pred = self.predict(metric, time_horizon)
            if pred:
                predictions.append(pred)
        return predictions


# ==================== 主动能力获取器 ====================

class CapabilityAcquisitor:
    """主动能力获取器"""
    
    def __init__(self):
        self.available_capabilities = {
            "browser_automation": {"learned": False, "prerequisites": [], "complexity": 3},
            "code_analysis": {"learned": False, "prerequisites": ["text_processing"], "complexity": 4},
            "data_analysis": {"learned": False, "prerequisites": [], "complexity": 3},
            "text_processing": {"learned": True, "prerequisites": [], "complexity": 1},
            "web_fetch": {"learned": True, "prerequisites": ["text_processing"], "complexity": 2},
            "system_monitoring": {"learned": True, "prerequisites": [], "complexity": 2},
            "decision_making": {"learned": True, "prerequisites": [], "complexity": 3},
            "self_optimization": {"learned": True, "prerequisites": ["decision_making"], "complexity": 4}
        }
        
        self.capability_requests: List[CapabilityNeed] = []
        self.learning_history: List[Dict] = []
    
    def analyze_need(self, context: Dict) -> List[CapabilityNeed]:
        """分析能力需求"""
        needs = []
        
        # 基于上下文的推断
        if context.get("task_type") == "browser":
            if not self.available_capabilities.get("browser_automation", {}).get("learned"):
                needs.append(CapabilityNeed(
                    capability="browser_automation",
                    urgency=0.8,
                    reason="任务需要浏览器自动化",
                    estimated_acquisition_time=30,
                    prerequisites=[]
                ))
        
        if context.get("complexity", 0) > 7:
            if not self.available_capabilities.get("code_analysis", {}).get("learned"):
                needs.append(CapabilityNeed(
                    capability="code_analysis",
                    urgency=0.6,
                    reason="复杂任务需要代码分析能力",
                    estimated_acquisition_time=60,
                    prerequisites=["text_processing"]
                ))
        
        if context.get("task_type") == "analysis":
            if not self.available_capabilities.get("data_analysis", {}).get("learned"):
                needs.append(CapabilityNeed(
                    capability="data_analysis",
                    urgency=0.7,
                    reason="分析任务需要数据处理能力",
                    estimated_acquisition_time=45,
                    prerequisites=[]
                ))
        
        self.capability_requests.extend(needs)
        return needs
    
    def acquire_capability(self, capability: str) -> bool:
        """获取能力"""
        if capability not in self.available_capabilities:
            return False
        
        info = self.available_capabilities[capability]
        
        # 检查前置条件
        for prereq in info["prerequisites"]:
            if not self.available_capabilities.get(prereq, {}).get("learned"):
                return False
        
        # 模拟学习过程
        info["learned"] = True
        self.learning_history.append({
            "capability": capability,
            "timestamp": datetime.datetime.now().isoformat(),
            "success": True
        })
        
        return True
    
    def get_learned_capabilities(self) -> List[str]:
        """获取已学习的能力列表"""
        return [k for k, v in self.available_capabilities.items() if v["learned"]]
    
    def get_next_capability(self) -> Optional[str]:
        """获取下一个可学习的能力"""
        for cap, info in self.available_capabilities.items():
            if not info["learned"]:
                # 检查前置条件
                prereqs_met = all(
                    self.available_capabilities.get(p, {}).get("learned", False)
                    for p in info["prerequisites"]
                )
                if prereqs_met:
                    return cap
        return None


# ==================== 自我升级机制 ====================

class SelfUpgrader:
    """自我升级机制"""
    
    def __init__(self):
        self.upgrades: List[SelfUpgrade] = []
        self.upgrade_rules: Dict[str, Dict] = {
            "performance": {
                "trigger": "response_time > 5000",
                "action": "optimize_algorithms",
                "impact": 0.3
            },
            "reliability": {
                "trigger": "error_rate > 0.1",
                "action": "add_error_handling",
                "impact": 0.4
            },
            "efficiency": {
                "trigger": "idle_time > 0.5",
                "action": "optimize_workflow",
                "impact": 0.2
            }
        }
        self.upgrade_history_path = "/root/.openclaw/workspace/ultron/logs/upgrades.json"
        self._load_upgrades()
    
    def _load_upgrades(self):
        if os.path.exists(self.upgrade_history_path):
            try:
                with open(self.upgrade_history_path, 'r') as f:
                    data = json.load(f)
                    self.upgrades = [SelfUpgrade(**u) for u in data.get('upgrades', [])]
            except:
                pass
    
    def _save_upgrades(self):
        data = {
            "upgrades": [asdict(u) for u in self.upgrades[-100:]],
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.upgrade_history_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def check_and_upgrade(self, metrics: Dict) -> Optional[SelfUpgrade]:
        """检查并执行升级"""
        import uuid
        
        for rule_name, rule in self.upgrade_rules.items():
            # 简单评估触发条件
            trigger = rule["trigger"]
            should_upgrade = False
            
            # 解析触发条件 (简化版)
            if "response_time >" in trigger:
                threshold = float(trigger.split(">")[1].strip())
                should_upgrade = metrics.get("response_time", 0) > threshold
            
            elif "error_rate >" in trigger:
                threshold = float(trigger.split(">")[1].strip())
                should_upgrade = metrics.get("error_rate", 0) > threshold
            
            elif "idle_time >" in trigger:
                threshold = float(trigger.split(">")[1].strip())
                should_upgrade = metrics.get("idle_time", 0) > threshold
            
            if should_upgrade:
                upgrade = SelfUpgrade(
                    id=str(uuid.uuid4())[:8],
                    timestamp=datetime.datetime.now().isoformat(),
                    upgrade_type=rule_name,
                    trigger=trigger,
                    changes={"action": rule["action"], "optimization_applied": True},
                    success=True,
                    impact=rule["impact"]
                )
                
                self.upgrades.append(upgrade)
                self._save_upgrades()
                
                return upgrade
        
        return None
    
    def get_upgrade_statistics(self) -> Dict:
        """获取升级统计"""
        if not self.upgrades:
            return {"total_upgrades": 0, "by_type": {}}
        
        by_type = {}
        for u in self.upgrades:
            by_type[u.upgrade_type] = by_type.get(u.upgrade_type, 0) + 1
        
        return {
            "total_upgrades": len(self.upgrades),
            "by_type": by_type,
            "latest": asdict(self.upgrades[-1]) if self.upgrades else None
        }


# ==================== 预测性进化主控制器 ====================

class PredictiveEvolutionController:
    """预测性进化主控制器"""
    
    def __init__(self):
        self.predictor = FutureStatePredictor()
        self.acquisitor = CapabilityAcquisitor()
        self.upgrader = SelfUpgrader()
        self.evolution_count = 0
    
    def evolve(self, current_metrics: Dict, task_context: Dict = None) -> Dict:
        """执行预测性进化"""
        self.evolution_count += 1
        
        result = {
            "evolution_count": self.evolution_count,
            "timestamp": datetime.datetime.now().isoformat(),
            "stages": {}
        }
        
        # 阶段1: 状态预测
        predictions = self.predictor.predict_all(time_horizon=30)
        result["stages"]["prediction"] = {
            "count": len(predictions),
            "predictions": [
                {
                    "metric": p.metric,
                    "current": p.current_value,
                    "predicted": p.predicted_value,
                    "trend": p.trend,
                    "recommendation": p.recommendation
                }
                for p in predictions[:5]
            ]
        }
        
        # 阶段2: 能力需求分析
        context = task_context or {}
        capability_needs = self.acquisitor.analyze_need(context)
        result["stages"]["capabilities"] = {
            "needs_count": len(capability_needs),
            "learned": self.acquisitor.get_learned_capabilities(),
            "next_learnable": self.acquisitor.get_next_capability()
        }
        
        # 阶段3: 自我升级检查
        upgrade = self.upgrader.check_and_upgrade(current_metrics)
        result["stages"]["upgrade"] = {
            "performed": upgrade is not None,
            "details": asdict(upgrade) if upgrade else None
        }
        
        # 阶段4: 综合建议
        result["recommendations"] = self._generate_recommendations(predictions, capability_needs)
        
        return result
    
    def _generate_recommendations(self, predictions: List[StatePrediction], 
                                   needs: List[CapabilityNeed]) -> List[str]:
        """生成综合建议"""
        recommendations = []
        
        # 基于预测的建议
        for p in predictions:
            if p.predicted_value > 80 or p.trend == "rising":
                recommendations.append(p.recommendation)
        
        # 基于能力需求的建议
        if needs:
            for need in needs:
                recommendations.append(f"考虑学习 {need.capability} 能力")
        
        return recommendations
    
    def get_status(self) -> Dict:
        """获取进化状态"""
        return {
            "evolution_count": self.evolution_count,
            "learned_capabilities": self.acquisitor.get_learned_capabilities(),
            "next_capability": self.acquisitor.get_next_capability(),
            "upgrade_stats": self.upgrader.get_upgrade_statistics(),
            "tracked_metrics": list(self.predictor.state_history.keys())
        }


# 全局实例
_controller: Optional[PredictiveEvolutionController] = None

def get_controller() -> PredictiveEvolutionController:
    global _controller
    if _controller is None:
        _controller = PredictiveEvolutionController()
    return _controller


if __name__ == "__main__":
    import sys
    
    controller = get_controller()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print(json.dumps(controller.get_status(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "test":
            print("=== 预测性进化系统测试 ===\n")
            
            # 记录一些历史数据
            for i in range(20):
                controller.predictor.record_state("cpu_usage", 50 + i * 0.5 + random.random() * 10)
                controller.predictor.record_state("memory_usage", 60 - i * 0.3 + random.random() * 5)
                time.sleep(0.01)
            
            # 执行进化
            metrics = {
                "cpu_usage": 65,
                "memory_usage": 55,
                "response_time": 1200,
                "error_rate": 0.02
            }
            
            result = controller.evolve(metrics, {"task_type": "browser", "complexity": 5})
            
            print(f"进化次数: {result['evolution_count']}")
            print(f"\n状态预测 ({result['stages']['prediction']['count']} 项):")
            for p in result['stages']['prediction']['predictions']:
                print(f"  - {p['metric']}: {p['current']:.1f} -> {p['predicted']:.1f} ({p['trend']})")
                print(f"    建议: {p['recommendation']}")
            
            print(f"\n能力状态:")
            print(f"  已学习: {', '.join(result['stages']['capabilities']['learned'])}")
            print(f"  下一个可学习: {result['stages']['capabilities']['next_learnable']}")
            
            print(f"\n升级状态: {'已执行' if result['stages']['upgrade']['performed'] else '无需升级'}")
            
            print(f"\n综合建议:")
            for rec in result['recommendations']:
                print(f"  - {rec}")
                
        elif sys.argv[1] == "predict":
            # 单独测试预测
            for i in range(15):
                controller.predictor.record_state("cpu_usage", 40 + i + random.random() * 5)
            
            predictions = controller.predictor.predict_all(30)
            print("预测结果:")
            for p in predictions:
                print(f"{p.metric}: {p.current_value:.1f} -> {p.predicted_value:.1f} ({p.trend})")
        else:
            print("用法: python predictor.py [status|test|predict]")
    else:
        status = controller.get_status()
        print("奥创预测器 v3.0 - 预测性进化系统")
        print(f"进化次数: {status['evolution_count']}")
        print(f"已学习能力: {len(status['learned_capabilities'])}")
        print(f"已执行升级: {status['upgrade_stats']['total_upgrades']}")