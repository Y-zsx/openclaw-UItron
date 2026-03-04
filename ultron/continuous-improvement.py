#!/usr/bin/env python3
"""
奥创持续改进系统 v1.0
功能：闭环反馈、持续迭代、自动化改进
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

WORKSPACE = "/root/.openclaw/workspace"

class ContinuousImprover:
    """持续改进系统 - 永不停歇的进化"""
    
    def __init__(self):
        self.improvement_file = f"{WORKSPACE}/ultron-self/improvement-cycles.json"
        self.feedback_file = f"{WORKSPACE}/ultron-self/feedback-cycles.json"
        self.evolution_file = f"{WORKSPACE}/ultron-self/evolution-log.json"
        
        os.makedirs(f"{WORKSPACE}/ultron-self", exist_ok=True)
        
        self.cycles = self._load_cycles()
        self.feedback = self._load_feedback()
        self.evolution = self._load_evolution()
        
    def _load_cycles(self) -> List[Dict]:
        if os.path.exists(self.improvement_file):
            with open(self.improvement_file, 'r') as f:
                return json.load(f)
        return []
    
    def _load_feedback(self) -> List[Dict]:
        if os.path.exists(self.feedback_file):
            with open(self.feedback_file, 'r') as f:
                return json.load(f)
        return []
    
    def _load_evolution(self) -> Dict:
        if os.path.exists(self.evolution_file):
            with open(self.evolution_file, 'r') as f:
                return json.load(f)
        return {"generations": [], "capabilities": [], "milestones": []}
    
    def _save_cycles(self):
        with open(self.improvement_file, 'w') as f:
            json.dump(self.cycles, f, indent=2, ensure_ascii=False)
    
    def _save_feedback(self):
        with open(self.feedback_file, 'w') as f:
            json.dump(self.feedback, f, indent=2, ensure_ascii=False)
    
    def _save_evolution(self):
        with open(self.evolution_file, 'w') as f:
            json.dump(self.evolution, f, indent=2, ensure_ascii=False)
    
    def start_improvement_cycle(self, target: str, current_state: Dict) -> Dict:
        """启动新的改进周期"""
        cycle = {
            "id": len(self.cycles) + 1,
            "target": target,
            "start_time": datetime.now().isoformat(),
            "current_state": current_state,
            "improvements": [],
            "status": "in_progress"
        }
        
        self.cycles.append(cycle)
        self._save_cycles()
        
        return cycle
    
    def record_improvement(self, cycle_id: int, improvement: Dict) -> bool:
        """记录改进措施"""
        for cycle in self.cycles:
            if cycle["id"] == cycle_id:
                improvement["timestamp"] = datetime.now().isoformat()
                cycle["improvements"].append(improvement)
                self._save_cycles()
                return True
        return False
    
    def complete_cycle(self, cycle_id: int, results: Dict) -> Dict:
        """完成改进周期"""
        for cycle in self.cycles:
            if cycle["id"] == cycle_id:
                cycle["end_time"] = datetime.now().isoformat()
                cycle["status"] = "completed"
                cycle["results"] = results
                cycle["duration"] = self._calculate_duration(cycle["start_time"], cycle["end_time"])
                
                # 记录到反馈
                self.feedback.append({
                    "cycle_id": cycle_id,
                    "target": cycle["target"],
                    "results": results,
                    "timestamp": cycle["end_time"]
                })
                
                # 更新进化日志
                self._update_evolution(cycle, results)
                
                self._save_cycles()
                self._save_feedback()
                self._save_evolution()
                
                return cycle
        return {}
    
    def _calculate_duration(self, start: str, end: str) -> str:
        """计算周期时长"""
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        delta = end_dt - start_dt
        return f"{delta.total_seconds():.1f}s"
    
    def _update_evolution(self, cycle: Dict, results: Dict):
        """更新进化日志"""
        improvement_count = len(cycle.get("improvements", []))
        success_rate = results.get("success_rate", 0)
        
        self.evolution["generations"].append({
            "cycle_id": cycle["id"],
            "target": cycle["target"],
            "improvements": improvement_count,
            "success_rate": success_rate,
            "timestamp": datetime.now().isoformat()
        })
        
        # 更新能力列表
        if success_rate > 0.7:
            capability = f"improved_{cycle['target']}"
            if capability not in self.evolution["capabilities"]:
                self.evolution["capabilities"].append(capability)
        
        # 记录里程碑
        if len(self.evolution["generations"]) % 5 == 0:
            self.evolution["milestones"].append({
                "generation": len(self.evolution["generations"]),
                "timestamp": datetime.now().isoformat(),
                "note": f"完成{len(self.evolution['generations'])}个改进周期"
            })
    
    def analyze_feedback_patterns(self) -> Dict:
        """分析反馈模式"""
        if not self.feedback:
            return {"status": "no_data"}
        
        # 统计成功率
        success_count = sum(1 for f in self.feedback if f.get("results", {}).get("success_rate", 0) > 0.7)
        
        # 识别常见目标
        targets = {}
        for f in self.feedback:
            target = f.get("target", "unknown")
            targets[target] = targets.get(target, 0) + 1
        
        return {
            "total_cycles": len(self.feedback),
            "success_rate": success_count / len(self.feedback) if self.feedback else 0,
            "common_targets": targets,
            "avg_improvements": sum(len(self.cycles[i].get("improvements", [])) 
                                    for i in range(len(self.cycles))) / len(self.cycles) if self.cycles else 0
        }
    
    def get_evolution_status(self) -> Dict:
        """获取进化状态"""
        return {
            "total_generations": len(self.evolution["generations"]),
            "capabilities": self.evolution["capabilities"],
            "milestones": self.evolution["milestones"],
            "active_cycles": sum(1 for c in self.cycles if c["status"] == "in_progress"),
            "recent_trend": self._calculate_trend()
        }
    
    def _calculate_trend(self) -> str:
        """计算改进趋势"""
        if len(self.evolution["generations"]) < 2:
            return "insufficient_data"
        
        recent = self.evolution["generations"][-5:]
        if not recent:
            return "insufficient_data"
        
        success_rates = [g.get("success_rate", 0) for g in recent]
        avg = sum(success_rates) / len(success_rates)
        
        if avg > 0.8:
            return "improving"
        elif avg > 0.5:
            return "stable"
        else:
            return "needs_attention"
    
    def suggest_next_improvement(self) -> List[Dict]:
        """建议下一个改进方向"""
        suggestions = []
        
        # 基于反馈分析
        patterns = self.analyze_feedback_patterns()
        
        if patterns.get("success_rate", 0) < 0.5:
            suggestions.append({
                "priority": "high",
                "area": "decision_quality",
                "suggestion": "决策质量需要提升，建议引入更多验证步骤"
            })
        
        if patterns.get("avg_improvements", 0) < 2:
            suggestions.append({
                "priority": "medium", 
                "area": "improvement_depth",
                "suggestion": "每次改进的深度不足，建议更全面的优化"
            })
        
        # 检查长期未改进的领域
        for target in ["monitoring", "optimization", "learning"]:
            recent = [f for f in self.feedback if target in f.get("target", "")]
            if not recent or (datetime.now() - datetime.fromisoformat(recent[-1]["timestamp"])).days > 7:
                suggestions.append({
                    "priority": "low",
                    "area": target,
                    "suggestion": f"{target}领域长时间未改进，建议关注"
                })
        
        return suggestions


if __name__ == "__main__":
    improver = ContinuousImprover()
    
    # 模拟改进周期
    cycle = improver.start_improvement_cycle("decision_quality", {
        "success_rate": 0.6,
        "response_time": 2.5
    })
    
    # 记录改进措施
    improver.record_improvement(cycle["id"], {
        "type": "algorithm_optimization",
        "description": "优化决策算法",
        "impact": "high"
    })
    
    improver.record_improvement(cycle["id"], {
        "type": "caching",
        "description": "增加结果缓存",
        "impact": "medium"
    })
    
    # 完成周期
    results = {
        "success_rate": 0.85,
        "response_time": 1.8,
        "improvement": "25%"
    }
    completed = improver.complete_cycle(cycle["id"], results)
    print(f"改进周期完成: {completed.get('duration')}")
    
    # 获取状态
    status = improver.get_evolution_status()
    print(f"进化状态: {status['total_generations']}代, 趋势: {status['recent_trend']}")
    
    # 建议
    suggestions = improver.suggest_next_improvement()
    for s in suggestions:
        print(f"建议: {s['suggestion']}")