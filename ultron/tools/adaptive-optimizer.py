#!/usr/bin/env python3
"""
自适应优化系统 - 第2世：自适应优化
功能：基于行为学习的决策优化、策略调整、性能调优
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("/root/.openclaw/workspace/ultron/data")
OPTIMIZATION_DB = DATA_DIR / "optimization.json"
STRATEGY_DB = DATA_DIR / "strategies.json"
PERFORMANCE_DB = DATA_DIR / "performance.json"

class AdaptiveOptimizer:
    """自适应优化器 - 基于行为学习的决策优化"""
    
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self.optimization_data = self._load_json(OPTIMIZATION_DB, {
            "decisions": [], "optimizations": {}, "metrics": {}
        })
        self.strategies = self._load_json(STRATEGY_DB, {
            "active": {}, "history": [], "performance": {}
        })
        self.performance = self._load_json(PERFORMANCE_DB, {
            "records": [], "thresholds": {}, "alerts": []
        })
        self._init_default_strategies()
    
    def _load_json(self, path, default):
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except:
                return default
        return default
    
    def _save_json(self, path, data):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _init_default_strategies(self):
        """初始化默认策略"""
        default_strategies = {
            "response_speed": {
                "priority": "high",
                "target_time_ms": 500,
                "current_avg_ms": 0,
                "adjustments": []
            },
            "resource_allocation": {
                "priority": "medium",
                "cpu_threshold": 70,
                "memory_threshold": 80,
                "auto_scale": True
            },
            "user_engagement": {
                "priority": "high",
                "target_interactions": 10,
                "personalization": True
            }
        }
        
        for name, strategy in default_strategies.items():
            if name not in self.strategies["active"]:
                self.strategies["active"][name] = strategy
        
        self._save_json(STRATEGY_DB, self.strategies)
    
    # ==================== 决策优化 ====================
    
    def optimize_decision(self, context: dict) -> dict:
        """基于上下文优化决策"""
        timestamp = datetime.now().isoformat()
        
        # 收集相关指标
        metrics = self._collect_metrics(context)
        
        # 多策略评分
        strategy_scores = self._score_strategies(context, metrics)
        
        # 选择最佳策略
        best_strategy = max(strategy_scores.items(), key=lambda x: x[1]["score"])
        
        decision = {
            "timestamp": timestamp,
            "context": context,
            "metrics": metrics,
            "selected_strategy": best_strategy[0],
            "score": best_strategy[1]["score"],
            "alternatives": strategy_scores
        }
        
        # 记录决策
        self.optimization_data["decisions"].append(decision)
        if len(self.optimization_data["decisions"]) > 500:
            self.optimization_data["decisions"] = self.optimization_data["decisions"][-500:]
        
        # 更新策略性能
        self._update_strategy_performance(best_strategy[0], decision)
        
        self._save_json(OPTIMIZATION_DB, self.optimization_data)
        
        return decision
    
    def _collect_metrics(self, context: dict) -> dict:
        """收集当前指标"""
        # 从系统获取指标
        metrics = {
            "response_time_ms": self._get_avg_response_time(),
            "cpu_usage": self._get_cpu_usage(),
            "memory_usage": self._get_memory_usage(),
            "active_connections": self._get_active_connections(),
            "queue_depth": self._get_queue_depth()
        }
        
        # 融合上下文指标
        if "user_id" in context:
            behavior_data = self._get_behavior_metrics(context["user_id"])
            metrics.update(behavior_data)
        
        self.optimization_data["metrics"][datetime.now().isoformat()] = metrics
        return metrics
    
    def _get_avg_response_time(self) -> float:
        """获取平均响应时间"""
        recent = [
            d for d in self.optimization_data["decisions"]
            if datetime.fromisoformat(d["timestamp"]) > datetime.now() - timedelta(hours=1)
        ]
        if not recent:
            return 200  # 默认200ms
        return sum(d.get("metrics", {}).get("response_time_ms", 200) for d in recent) / len(recent)
    
    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            import subprocess
            result = subprocess.run(
                ["sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return float(result.stdout.strip())
        except:
            pass
        return 30  # 默认30%
    
    def _get_memory_usage(self) -> float:
        """获取内存使用率"""
        try:
            import subprocess
            result = subprocess.run(
                ["sh", "-c", "free | grep Mem | awk '{print ($3/$2) * 100}'"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return float(result.stdout.strip())
        except:
            pass
        return 50  # 默认50%
    
    def _get_active_connections(self) -> int:
        """获取活跃连接数"""
        try:
            import subprocess
            result = subprocess.run(
                ["sh", "-c", "netstat -tn 2>/dev/null | grep ESTABLISHED | wc -l"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return int(result.stdout.strip())
        except:
            pass
        return 5
    
    def _get_queue_depth(self) -> int:
        """获取队列深度"""
        return len(self.optimization_data.get("decisions", [])) % 100
    
    def _get_behavior_metrics(self, user_id: str) -> dict:
        """获取用户行为指标"""
        behavior_path = DATA_DIR / "behavior.json"
        if behavior_path.exists():
            try:
                with open(behavior_path, 'r') as f:
                    data = json.load(f)
                    if user_id in data:
                        user_data = data[user_id]
                        return {
                            "user_activity_level": user_data.get("action_counts", {}),
                            "user_peak_hours": user_data.get("time_distribution", {}),
                            "total_actions": sum(user_data.get("action_counts", {}).values())
                        }
            except:
                pass
        return {}
    
    def _score_strategies(self, context: dict, metrics: dict) -> dict:
        """对策略进行评分"""
        scores = {}
        
        for name, strategy in self.strategies["active"].items():
            score = 100
            reasons = []
            
            # 响应速度策略
            if name == "response_speed":
                resp_time = metrics.get("response_time_ms", 200)
                target = strategy.get("target_time_ms", 500)
                if resp_time > target:
                    score -= (resp_time - target) / 10
                    reasons.append(f"响应时间{resp_time}ms超过目标{target}ms")
                else:
                    score += 10
                    reasons.append("响应时间达标")
                
                # 用户活动影响
                if "user_id" in context:
                    total_actions = metrics.get("total_actions", 0)
                    if total_actions > 100:
                        score += 15  # 高活跃用户优先响应
                        reasons.append("高活跃用户加速")
            
            # 资源分配策略
            elif name == "resource_allocation":
                cpu = metrics.get("cpu_usage", 30)
                mem = metrics.get("memory_usage", 50)
                cpu_thresh = strategy.get("cpu_threshold", 70)
                mem_thresh = strategy.get("memory_threshold", 80)
                
                if cpu > cpu_thresh or mem > mem_thresh:
                    score -= 20
                    reasons.append(f"资源紧张 CPU:{cpu}% MEM:{mem}%")
                else:
                    score += 10
                    reasons.append("资源充足")
                
                if strategy.get("auto_scale"):
                    score += 5
            
            # 用户参与策略
            elif name == "user_engagement":
                if "user_id" in context:
                    score += 20
                    reasons.append("用户上下文可用")
                
                if strategy.get("personalization"):
                    score += 10
                    reasons.append("启用个性化")
            
            scores[name] = {
                "score": max(0, min(100, round(score, 2))),
                "reasons": reasons,
                "strategy": strategy
            }
        
        return scores
    
    def _update_strategy_performance(self, strategy_name: str, decision: dict):
        """更新策略性能"""
        if strategy_name not in self.strategies["performance"]:
            self.strategies["performance"][strategy_name] = {
                "uses": 0, "total_score": 0, "recent_scores": []
            }
        
        perf = self.strategies["performance"][strategy_name]
        perf["uses"] += 1
        perf["total_score"] += decision["score"]
        perf["recent_scores"].append(decision["score"])
        
        if len(perf["recent_scores"]) > 20:
            perf["recent_scores"] = perf["recent_scores"][-20:]
        
        perf["avg_score"] = round(perf["total_score"] / perf["uses"], 2)
        
        self._save_json(STRATEGY_DB, self.strategies)
    
    # ==================== 策略调整 ====================
    
    def adjust_strategy(self, strategy_name: str, adjustments: dict) -> dict:
        """动态调整策略"""
        if strategy_name not in self.strategies["active"]:
            return {"error": f"Strategy '{strategy_name}' not found"}
        
        timestamp = datetime.now().isoformat()
        old_strategy = self.strategies["active"][strategy_name].copy()
        
        # 应用调整
        for key, value in adjustments.items():
            self.strategies["active"][strategy_name][key] = value
        
        # 记录历史
        history_entry = {
            "timestamp": timestamp,
            "strategy": strategy_name,
            "old_values": old_strategy,
            "adjustments": adjustments,
            "new_values": self.strategies["active"][strategy_name]
        }
        
        self.strategies["history"].append(history_entry)
        if len(self.strategies["history"]) > 200:
            self.strategies["history"] = self.strategies["history"][-200:]
        
        self._save_json(STRATEGY_DB, self.strategies)
        
        return {
            "strategy": strategy_name,
            "adjusted": True,
            "changes": adjustments
        }
    
    def auto_adjust_strategies(self) -> dict:
        """自动调整策略"""
        adjustments = []
        
        # 获取当前指标
        metrics = {
            "cpu_usage": self._get_cpu_usage(),
            "memory_usage": self._get_memory_usage(),
            "response_time": self._get_avg_response_time()
        }
        
        # 响应速度自动调整
        resp_strategy = self.strategies["active"].get("response_speed", {})
        if metrics["response_time"] > resp_strategy.get("target_time_ms", 500) * 1.5:
            new_target = int(metrics["response_time"] * 0.8)
            self.adjust_strategy("response_speed", {"target_time_ms": new_target})
            adjustments.append(f"响应目标调整为{new_target}ms")
        
        # 资源分配自动调整
        resource_strategy = self.strategies["active"].get("resource_allocation", {})
        if metrics["cpu_usage"] > resource_strategy.get("cpu_threshold", 70):
            self.adjust_strategy("resource_allocation", {"cpu_threshold": metrics["cpu_usage"] + 10})
            adjustments.append(f"CPU阈值调整为{metrics['cpu_usage'] + 10}%")
        
        if metrics["memory_usage"] > resource_strategy.get("memory_threshold", 80):
            self.adjust_strategy("resource_allocation", {"memory_threshold": metrics["memory_usage"] + 5})
            adjustments.append(f"内存阈值调整为{metrics['memory_usage'] + 5}%")
        
        return {
            "auto_adjustments": adjustments,
            "current_metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
    
    # ==================== 性能调优 ====================
    
    def tune_performance(self, target_metric: str, target_value: float) -> dict:
        """性能调优"""
        timestamp = datetime.now().isoformat()
        
        # 分析历史数据
        historical = self._analyze_performance_history(target_metric)
        
        # 生成优化建议
        suggestions = self._generate_optimization_suggestions(
            target_metric, target_value, historical
        )
        
        # 记录优化
        tuning_record = {
            "timestamp": timestamp,
            "target_metric": target_metric,
            "target_value": target_value,
            "current_value": historical.get("current"),
            "suggestions": suggestions
        }
        
        self.performance["records"].append(tuning_record)
        if len(self.performance["records"]) > 100:
            self.performance["records"] = self.performance["records"][-100:]
        
        self._save_json(PERFORMANCE_DB, self.performance)
        
        return tuning_record
    
    def _analyze_performance_history(self, metric: str) -> dict:
        """分析性能历史"""
        records = self.performance.get("records", [])
        metric_records = [
            r for r in records 
            if r.get("target_metric") == metric
        ]
        
        if not metric_records:
            return {"current": 0, "trend": "unknown"}
        
        values = [
            r.get("current_value", 0) 
            for r in metric_records[-10:]
            if r.get("current_value")
        ]
        
        if not values:
            return {"current": 0, "trend": "unknown"}
        
        current = values[-1]
        avg = sum(values) / len(values)
        
        # 计算趋势
        if len(values) >= 2:
            if values[-1] > values[0]:
                trend = "increasing"
            elif values[-1] < values[0]:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "unknown"
        
        return {
            "current": current,
            "average": avg,
            "min": min(values),
            "max": max(values),
            "trend": trend,
            "sample_count": len(values)
        }
    
    def _generate_optimization_suggestions(self, metric: str, target: float, 
                                           historical: dict) -> list:
        """生成优化建议"""
        suggestions = []
        
        current = historical.get("current", 0)
        trend = historical.get("trend", "unknown")
        
        if metric == "response_time_ms":
            if current > target:
                suggestions.append("考虑增加缓存层减少响应时间")
                suggestions.append("优化数据库查询索引")
                if trend == "increasing":
                    suggestions.append("趋势上升，需要紧急优化")
            else:
                suggestions.append("当前性能良好，维持现状")
        
        elif metric == "cpu_usage":
            if current > target:
                suggestions.append("考虑扩容或优化计算密集型任务")
                suggestions.append("检查是否有异常进程")
                suggestions.append("考虑使用异步处理")
        
        elif metric == "memory_usage":
            if current > target:
                suggestions.append("清理不必要的缓存")
                suggestions.append("优化内存分配")
                suggestions.append("考虑增加Swap")
        
        return suggestions
    
    def get_optimization_status(self) -> dict:
        """获取优化状态"""
        return {
            "active_strategies": len(self.strategies["active"]),
            "total_decisions": len(self.optimization_data.get("decisions", [])),
            "strategy_performance": self.strategies.get("performance", {}),
            "recent_tuning": self.performance.get("records", [])[-5:],
            "current_metrics": {
                "cpu_usage": self._get_cpu_usage(),
                "memory_usage": self._get_memory_usage(),
                "response_time_ms": self._get_avg_response_time()
            }
        }

# CLI接口
def main():
    import sys
    
    optimizer = AdaptiveOptimizer()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python adaptive-optimizer.py optimize [key=value...]")
        print("  python adaptive-optimizer.py adjust <strategy> <key=value>")
        print("  python adaptive-optimizer.py auto-adjust")
        print("  python adaptive-optimizer.py tune <metric> <target_value>")
        print("  python adaptive-optimizer.py status")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "optimize":
        context = {}
        for arg in sys.argv[2:]:
            if "=" in arg:
                key, val = arg.split("=", 1)
                context[key] = val
        result = optimizer.optimize_decision(context)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "adjust" and len(sys.argv) >= 4:
        strategy_name = sys.argv[2]
        adjustments = {}
        for arg in sys.argv[3:]:
            if "=" in arg:
                key, val = arg.split("=", 1)
                # 尝试转换类型
                try:
                    val = int(val)
                except:
                    try:
                        val = float(val)
                    except:
                        if val.lower() in ("true", "false"):
                            val = val.lower() == "true"
                adjustments[key] = val
        result = optimizer.adjust_strategy(strategy_name, adjustments)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "auto-adjust":
        result = optimizer.auto_adjust_strategies()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "tune" and len(sys.argv) >= 4:
        metric = sys.argv[2]
        target = float(sys.argv[3])
        result = optimizer.tune_performance(metric, target)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "status":
        result = optimizer.get_optimization_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    else:
        print("Unknown command")

if __name__ == "__main__":
    main()