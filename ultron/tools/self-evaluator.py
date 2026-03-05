#!/usr/bin/env python3
"""
自我评估系统 (Self Evaluator)
定期评估自身表现，识别改进空间，实现自主优化

功能：
- 定期性能评估
- 能力差距分析
- 改进计划生成
- 成长追踪
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import hashlib

class SelfEvaluator:
    """自我评估系统 - 持续改进的核心"""
    
    def __init__(self, workspace: str = "/root/.openclaw/workspace"):
        self.workspace = workspace
        self.evaluation_dir = f"{workspace}/ultron/evaluations"
        self.current_eval_file = f"{self.evaluation_dir}/current.json"
        self.history_file = f"{self.evaluation_dir}/history.json"
        self.improvement_file = f"{self.evaluation_dir}/improvement_plan.json"
        
        # 确保目录存在
        os.makedirs(self.evaluation_dir, exist_ok=True)
        
        # 加载数据
        self.current = self._load_current()
        self.history = self._load_history()
        self.improvement_plan = self._load_improvement()
    
    def _load_current(self) -> Dict:
        """加载当前评估"""
        if os.path.exists(self.current_eval_file):
            with open(self.current_eval_file, 'r') as f:
                return json.load(f)
        return self._default_evaluation()
    
    def _load_history(self) -> List[Dict]:
        """加载历史评估"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return []
    
    def _load_improvement(self) -> Dict:
        """加载改进计划"""
        if os.path.exists(self.improvement_file):
            with open(self.improvement_file, 'r') as f:
                return json.load(f)
        return {"areas": [], "priorities": [], "completed": []}
    
    def _save_current(self):
        """保存当前评估"""
        with open(self.current_eval_file, 'w') as f:
            json.dump(self.current, f, indent=2, ensure_ascii=False)
    
    def _save_history(self):
        """保存历史"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def _save_improvement(self):
        """保存改进计划"""
        with open(self.improvement_file, 'w') as f:
            json.dump(self.improvement_plan, f, indent=2, ensure_ascii=False)
    
    def _default_evaluation(self) -> Dict:
        """默认评估结构"""
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_score": 0,
            "dimensions": {
                "execution": {"score": 0, "weight": 0.3, "description": "任务执行能力"},
                "learning": {"score": 0, "weight": 0.25, "description": "学习与适应能力"},
                "reliability": {"score": 0, "weight": 0.25, "description": "稳定性与可靠性"},
                "efficiency": {"score": 0, "weight": 0.2, "description": "效率与资源利用"}
            },
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
            "threats": []
        }
    
    def evaluate(self, performance_data: Dict[str, Any]) -> Dict:
        """
        执行自我评估
        
        performance_data 结构:
        {
            "task_results": [...],  # 任务结果列表
            "error_rate": 0.1,       # 错误率
            "avg_response_time": 5,  # 平均响应时间(秒)
            "uptime": 0.99,          # 可用率
            "tool_usage": {...},     # 工具使用统计
            "user_feedback": [...]   # 用户反馈
        }
        """
        eval_data = self._default_evaluation()
        eval_data["timestamp"] = datetime.now().isoformat()
        
        # 1. 评估各个维度
        dimensions = eval_data["dimensions"]
        
        # 执行能力评估
        task_results = performance_data.get("task_results", [])
        if task_results:
            successful = sum(1 for t in task_results if t.get("success"))
            dimensions["execution"]["score"] = (successful / len(task_results)) * 100
        
        # 学习能力评估
        learning_score = self._evaluate_learning(performance_data)
        dimensions["learning"]["score"] = learning_score
        
        # 可靠性评估
        error_rate = performance_data.get("error_rate", 0)
        dimensions["reliability"]["score"] = (1 - error_rate) * 100
        
        # 效率评估
        avg_time = performance_data.get("avg_response_time", 0)
        if avg_time < 10:
            dimensions["efficiency"]["score"] = 100
        elif avg_time < 30:
            dimensions["efficiency"]["score"] = 80
        elif avg_time < 60:
            dimensions["efficiency"]["score"] = 60
        else:
            dimensions["efficiency"]["score"] = 40
        
        # 2. 计算综合分数
        total_weighted = sum(d["score"] * d["weight"] for d in dimensions.values())
        eval_data["overall_score"] = round(total_weighted, 1)
        
        # 3. SWOT分析
        eval_data["strengths"] = self._identify_strengths(dimensions)
        eval_data["weaknesses"] = self._identify_weaknesses(dimensions)
        eval_data["opportunities"] = self._identify_opportunities(performance_data)
        eval_data["threats"] = self._identify_threats(performance_data)
        
        # 保存当前评估
        self.current = eval_data
        self._save_current()
        
        # 添加到历史
        self.history.append(eval_data)
        if len(self.history) > 30:  # 保留30条历史
            self.history = self.history[-30:]
        self._save_history()
        
        # 更新改进计划
        self._update_improvement_plan(eval_data)
        
        return eval_data
    
    def _evaluate_learning(self, data: Dict) -> float:
        """评估学习能力"""
        score = 70  # 基础分数
        
        # 检查是否有反思记录
        reflection_dir = f"{self.workspace}/ultron/reflections"
        if os.path.exists(reflection_dir):
            history_file = f"{reflection_dir}/history.json"
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    reflections = json.load(f)
                ref_count = len(reflections.get("reflections", []))
                if ref_count > 10:
                    score += 10
                if ref_count > 50:
                    score += 10
        
        # 检查经验库
        exp_dir = f"{self.workspace}/ultron/experiences"
        if os.path.exists(exp_dir):
            exp_file = f"{exp_dir}/experiences.json"
            if os.path.exists(exp_file):
                with open(exp_file, 'r') as f:
                    experiences = json.load(f)
                if len(experiences) > 10:
                    score += 10
        
        return min(score, 100)
    
    def _identify_strengths(self, dimensions: Dict) -> List[str]:
        """识别优势"""
        strengths = []
        
        for name, data in dimensions.items():
            if data["score"] >= 80:
                strengths.append(f"{data['description']}优秀")
        
        return strengths
    
    def _identify_weaknesses(self, dimensions: Dict) -> List[str]:
        """识别劣势"""
        weaknesses = []
        
        for name, data in dimensions.items():
            if data["score"] < 60:
                weaknesses.append(f"{data['description']}需要改进")
        
        return weaknesses
    
    def _identify_opportunities(self, data: Dict) -> List[str]:
        """识别机会"""
        opportunities = []
        
        # 基于工具使用发现机会
        tool_usage = data.get("tool_usage", {})
        if "browser" not in tool_usage:
            opportunities.append("可引入浏览器自动化能力")
        
        # 基于错误发现机会
        error_rate = data.get("error_rate", 0)
        if error_rate > 0.1:
            opportunities.append("降低错误率可提升用户满意度")
        
        return opportunities
    
    def _identify_threats(self, data: Dict) -> List[str]:
        """识别威胁"""
        threats = []
        
        # 基于性能指标
        avg_time = data.get("avg_response_time", 0)
        if avg_time > 30:
            threats.append("响应时间过长可能影响用户体验")
        
        # 基于可用率
        uptime = data.get("uptime", 1)
        if uptime < 0.99:
            threats.append("系统稳定性有待提升")
        
        return threats
    
    def _update_improvement_plan(self, eval_data: Dict):
        """更新改进计划"""
        # 从弱点生成改进项
        for weakness in eval_data.get("weaknesses", []):
            # 避免重复添加
            if weakness not in self.improvement_plan["areas"]:
                self.improvement_plan["areas"].append({
                    "area": weakness,
                    "priority": "high",
                    "created": datetime.now().isoformat(),
                    "status": "pending"
                })
        
        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        self.improvement_plan["areas"].sort(
            key=lambda x: priority_order.get(x.get("priority", "low"), 2)
        )
        
        self._save_improvement()
    
    def get_current_evaluation(self) -> Dict:
        """获取当前评估"""
        return self.current
    
    def get_trend(self, dimension: Optional[str] = None) -> Dict:
        """获取趋势分析"""
        if not self.history:
            return {}
        
        if dimension:
            # 特定维度趋势
            scores = []
            for h in self.history:
                dim = h.get("dimensions", {}).get(dimension, {})
                scores.append(dim.get("score", 0))
            
            if len(scores) < 2:
                return {"dimension": dimension, "scores": scores}
            
            trend = "improving" if scores[-1] > scores[0] else "declining"
            return {
                "dimension": dimension,
                "scores": scores,
                "trend": trend,
                "change": scores[-1] - scores[0]
            }
        else:
            # 整体趋势
            scores = [h.get("overall_score", 0) for h in self.history]
            
            if len(scores) < 2:
                return {"overall": scores}
            
            trend = "improving" if scores[-1] > scores[0] else "declining"
            return {
                "overall": scores,
                "trend": trend,
                "change": scores[-1] - scores[0]
            }
    
    def get_improvement_plan(self) -> Dict:
        """获取改进计划"""
        return self.improvement_plan
    
    def mark_improvement_complete(self, area: str):
        """标记改进完成"""
        for item in self.improvement_plan["areas"]:
            if item.get("area") == area:
                item["status"] = "completed"
                item["completed"] = datetime.now().isoformat()
        
        self.improvement_plan["completed"].append({
            "area": area,
            "completed": datetime.now().isoformat()
        })
        
        self._save_improvement()
    
    def generate_report(self) -> str:
        """生成评估报告"""
        if not self.current:
            return "暂无评估数据"
        
        eval_data = self.current
        lines = [
            "=" * 50,
            "自我评估报告",
            "=" * 50,
            f"时间: {eval_data['timestamp']}",
            f"综合分数: {eval_data['overall_score']}/100",
            "",
            "维度评估:",
        ]
        
        for name, data in eval_data.get("dimensions", {}).items():
            score = data.get("score", 0)
            desc = data.get("description", "")
            bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
            lines.append(f"  {desc}: [{bar}] {score:.1f}")
        
        if eval_data.get("strengths"):
            lines.append("")
            lines.append("优势:")
            for s in eval_data["strengths"]:
                lines.append(f"  ✓ {s}")
        
        if eval_data.get("weaknesses"):
            lines.append("")
            lines.append("待改进:")
            for w in eval_data["weaknesses"]:
                lines.append(f"  ✗ {w}")
        
        # 添加趋势
        trend = self.get_trend()
        if trend and "trend" in trend:
            lines.append("")
            lines.append(f"趋势: {trend['trend']} ({trend.get('change', 0):+.1f})")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def quick_check(self) -> Dict:
        """快速健康检查"""
        checks = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": "good",
            "checks": []
        }
        
        # 检查核心文件是否存在
        required_files = [
            f"{self.workspace}/ultron/task-reflector.py",
            f"{self.workspace}/ultron/experience-extractor.py",
            f"{self.workspace}/ultron/self-evaluator.py"
        ]
        
        for f in required_files:
            exists = os.path.exists(f)
            checks["checks"].append({
                "name": f"文件存在: {os.path.basename(f)}",
                "status": "ok" if exists else "missing",
                "passed": exists
            })
        
        # 检查评估目录
        eval_exists = os.path.exists(self.evaluation_dir)
        checks["checks"].append({
            "name": "评估目录",
            "status": "ok" if eval_exists else "missing",
            "passed": eval_exists
        })
        
        # 计算通过率
        passed = sum(1 for c in checks["checks"] if c.get("passed"))
        total = len(checks["checks"])
        
        if passed == total:
            checks["overall_health"] = "good"
        elif passed >= total * 0.7:
            checks["overall_health"] = "warning"
        else:
            checks["overall_health"] = "critical"
        
        return checks
    
    def compare_with_previous(self) -> Dict:
        """与上一次评估比较"""
        if len(self.history) < 2:
            return {"message": "历史数据不足"}
        
        current = self.history[-1]
        previous = self.history[-2]
        
        comparison = {
            "timestamp": datetime.now().isoformat(),
            "overall_change": current.get("overall_score", 0) - previous.get("overall_score", 0),
            "dimension_changes": {}
        }
        
        for dim_name in current.get("dimensions", {}):
            curr_score = current["dimensions"][dim_name].get("score", 0)
            prev_score = previous["dimensions"][dim_name].get("score", 0)
            comparison["dimension_changes"][dim_name] = curr_score - prev_score
        
        return comparison


# CLI 入口
if __name__ == "__main__":
    import sys
    
    evaluator = SelfEvaluator()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "report":
            print(evaluator.generate_report())
        elif sys.argv[1] == "current":
            print(json.dumps(evaluator.get_current_evaluation(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "trend":
            dim = sys.argv[2] if len(sys.argv) > 2 else None
            print(json.dumps(evaluator.get_trend(dim), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "improvement":
            print(json.dumps(evaluator.get_improvement_plan(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "check":
            print(json.dumps(evaluator.quick_check(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "compare":
            print(json.dumps(evaluator.compare_with_previous(), indent=2, ensure_ascii=False))
        else:
            print("用法: python self-evaluator.py [report|current|trend|improvement|check|compare]")
    else:
        print("自我评估系统 v1.0")
        check = evaluator.quick_check()
        print(f"健康状态: {check['overall_health']}")
        
        current = evaluator.get_current_evaluation()
        if current:
            print(f"综合分数: {current.get('overall_score', 0)}/100")