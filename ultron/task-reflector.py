#!/usr/bin/env python3
"""
任务反思引擎 (Task Reflector)
从每个任务中提取经验教训，实现持续学习与改进

功能：
- 任务结果分析
- 成功/失败因素提取
- 改进建议生成
- 反思日志记录
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

class TaskReflector:
    """任务反思引擎 - 从实践中学习"""
    
    def __init__(self, workspace: str = "/root/.openclaw/workspace"):
        self.workspace = workspace
        self.reflection_dir = f"{workspace}/ultron/reflections"
        self.history_file = f"{self.reflection_dir}/history.json"
        self.insights_file = f"{self.reflection_dir}/insights.json"
        
        # 确保目录存在
        os.makedirs(self.reflection_dir, exist_ok=True)
        
        # 初始化历史记录
        self.history = self._load_history()
        self.insights = self._load_insights()
    
    def _load_history(self) -> Dict:
        """加载历史反思记录"""
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return {"reflections": [], "stats": {"total": 0, "success": 0, "failure": 0}}
    
    def _load_insights(self) -> Dict:
        """加载洞察记录"""
        if os.path.exists(self.insights_file):
            with open(self.insights_file, 'r') as f:
                return json.load(f)
        return {"patterns": [], "lessons": [], "recommendations": []}
    
    def _save_history(self):
        """保存历史记录"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def _save_insights(self):
        """保存洞察记录"""
        with open(self.insights_file, 'w') as f:
            json.dump(self.insights, f, indent=2, ensure_ascii=False)
    
    def reflect_on_task(self, task_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        对任务结果进行反思
        
        task_result 结构:
        {
            "task_id": "xxx",
            "task_type": "execution|analysis|creation",
            "success": true/false,
            "duration": 120,  # 秒
            "output": "结果描述",
            "errors": ["错误1", "错误2"],
            "tools_used": ["tool1", "tool2"],
            "context": {"key": "value"}
        }
        """
        task_id = task_result.get("task_id", f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        # 1. 分析任务类型和结果
        analysis = self._analyze_result(task_result)
        
        # 2. 提取成功/失败因素
        factors = self._extract_factors(task_result, analysis)
        
        # 3. 生成改进建议
        recommendations = self._generate_recommendations(task_result, factors)
        
        # 4. 识别模式
        patterns = self._identify_patterns(task_result)
        
        # 5. 构建反思记录
        reflection = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "task_type": task_result.get("task_type", "unknown"),
            "success": task_result.get("success", False),
            "duration": task_result.get("duration", 0),
            "analysis": analysis,
            "factors": factors,
            "recommendations": recommendations,
            "patterns": patterns
        }
        
        # 保存反思
        self.history["reflections"].append(reflection)
        self.history["stats"]["total"] += 1
        if task_result.get("success"):
            self.history["stats"]["success"] += 1
        else:
            self.history["stats"]["failure"] += 1
        
        # 更新洞察
        self._update_insights(reflection, factors, recommendations, patterns)
        
        self._save_history()
        self._save_insights()
        
        return reflection
    
    def _analyze_result(self, result: Dict) -> Dict:
        """分析任务结果"""
        success = result.get("success", False)
        duration = result.get("duration", 0)
        errors = result.get("errors", [])
        
        analysis = {
            "outcome": "success" if success else "failure",
            "performance": self._evaluate_performance(duration),
            "error_count": len(errors),
            "error_severity": self._assess_error_severity(errors)
        }
        
        # 分析工具使用效率
        tools = result.get("tools_used", [])
        analysis["tool_efficiency"] = len(tools) > 0
        
        return analysis
    
    def _evaluate_performance(self, duration: float) -> str:
        """评估性能等级"""
        if duration < 30:
            return "excellent"
        elif duration < 120:
            return "good"
        elif duration < 300:
            return "average"
        else:
            return "slow"
    
    def _assess_error_severity(self, errors: List[str]) -> str:
        """评估错误严重程度"""
        if not errors:
            return "none"
        
        critical = ["error", "fatal", "exception", "crash"]
        warnings = ["warning", "warn", "deprecated"]
        
        has_critical = any(e.lower() in critical for e in errors)
        has_warnings = any(e.lower() in warnings for e in errors)
        
        if has_critical:
            return "critical"
        elif has_warnings:
            return "moderate"
        else:
            return "minor"
    
    def _extract_factors(self, result: Dict, analysis: Dict) -> Dict:
        """提取成功/失败因素"""
        factors = {
            "success_factors": [],
            "failure_factors": [],
            "neutral_factors": []
        }
        
        success = result.get("success", False)
        
        # 基于结果类型提取因素
        if success:
            factors["success_factors"].extend([
                "任务目标明确",
                "工具选择适当",
                "执行过程顺利"
            ])
            
            if analysis.get("performance") in ["excellent", "good"]:
                factors["success_factors"].append("性能表现优秀")
        else:
            factors["failure_factors"].extend([
                "执行过程中出现错误"
            ])
            
            if analysis.get("error_severity") == "critical":
                factors["failure_factors"].append("关键错误导致失败")
        
        # 从错误中提取因素
        errors = result.get("errors", [])
        for error in errors:
            if "timeout" in error.lower():
                factors["failure_factors"].append("操作超时")
            if "permission" in error.lower():
                factors["failure_factors"].append("权限不足")
            if "not found" in error.lower():
                factors["failure_factors"].append("资源不存在")
        
        # 中性因素
        factors["neutral_factors"] = [
            f"使用工具数: {len(result.get('tools_used', []))}",
            f"任务类型: {result.get('task_type', 'unknown')}"
        ]
        
        return factors
    
    def _generate_recommendations(self, result: Dict, factors: Dict) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        success = result.get("success", False)
        
        if not success:
            # 失败时的建议
            if factors["failure_factors"]:
                recommendations.append(f"重点改进: {factors['failure_factors'][0]}")
            
            errors = result.get("errors", [])
            if errors:
                recommendations.append(f"分析错误: {errors[0][:100]}")
            
            recommendations.append("考虑增加错误处理机制")
        else:
            # 成功时的建议
            if result.get("duration", 0) > 120:
                recommendations.append("优化执行效率，减少等待时间")
            
            recommendations.append("记录成功模式供后续参考")
        
        # 通用建议
        if len(result.get("tools_used", [])) > 5:
            recommendations.append("考虑简化工具调用链")
        
        return recommendations
    
    def _identify_patterns(self, result: Dict) -> List[str]:
        """识别任务模式"""
        patterns = []
        
        task_type = result.get("task_type", "")
        duration = result.get("duration", 0)
        
        # 时间模式
        if duration > 300:
            patterns.append("长时间运行任务")
        
        # 工具模式
        tools = result.get("tools_used", [])
        if "browser" in tools:
            patterns.append("涉及浏览器操作")
        if "exec" in tools:
            patterns.append("涉及命令行执行")
        
        # 错误模式
        errors = result.get("errors", [])
        if len(errors) > 3:
            patterns.append("多错误并发")
        
        return patterns
    
    def _update_insights(self, reflection: Dict, factors: Dict, 
                        recommendations: List[str], patterns: List[str]):
        """更新洞察库"""
        # 更新模式
        for pattern in patterns:
            existing = [p for p in self.insights["patterns"] if p["pattern"] == pattern]
            if existing:
                existing[0]["count"] = existing[0].get("count", 0) + 1
            else:
                self.insights["patterns"].append({
                    "pattern": pattern,
                    "count": 1,
                    "first_seen": datetime.now().isoformat()
                })
        
        # 更新教训
        for rec in recommendations:
            if rec not in self.insights["lessons"]:
                self.insights["lessons"].append(rec)
        
        # 更新建议
        for factor in factors.get("failure_factors", []):
            if factor not in self.insights["recommendations"]:
                self.insights["recommendations"].append(f"避免: {factor}")
        
        for factor in factors.get("success_factors", []):
            if factor not in self.insights["recommendations"]:
                self.insights["recommendations"].append(f"保持: {factor}")
    
    def get_recent_reflections(self, count: int = 10) -> List[Dict]:
        """获取最近N条反思"""
        return self.history["reflections"][-count:]
    
    def get_patterns(self) -> List[Dict]:
        """获取识别到的模式"""
        return sorted(self.insights["patterns"], key=lambda x: x.get("count", 0), reverse=True)
    
    def get_lessons(self) -> List[str]:
        """获取学到的教训"""
        return self.insights["lessons"]
    
    def get_recommendations(self) -> List[str]:
        """获取改进建议"""
        return self.insights["recommendations"]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.history["stats"]
    
    def analyze_session(self, session_log: List[Dict]) -> Dict:
        """分析整个会话"""
        total_tasks = len(session_log)
        successful = sum(1 for t in session_log if t.get("success"))
        failed = total_tasks - successful
        
        total_duration = sum(t.get("duration", 0) for t in session_log)
        avg_duration = total_duration / total_tasks if total_tasks > 0 else 0
        
        # 收集所有工具
        all_tools = set()
        all_errors = []
        for task in session_log:
            all_tools.update(task.get("tools_used", []))
            all_errors.extend(task.get("errors", []))
        
        return {
            "session_summary": {
                "total_tasks": total_tasks,
                "successful": successful,
                "failed": failed,
                "success_rate": successful / total_tasks if total_tasks > 0 else 0,
                "avg_duration": avg_duration,
                "total_duration": total_duration
            },
            "tools_used": list(all_tools),
            "common_errors": self._count_errors(all_errors),
            "insights": self._generate_session_insights(session_log)
        }
    
    def _count_errors(self, errors: List[str]) -> Dict[str, int]:
        """统计错误频率"""
        counts = {}
        for error in errors:
            # 简化错误描述
            key = error[:50] if len(error) > 50 else error
            counts[key] = counts.get(key, 0) + 1
        return counts
    
    def _generate_session_insights(self, session_log: List[Dict]) -> List[str]:
        """生成会话洞察"""
        insights = []
        
        # 分析任务分布
        task_types = {}
        for task in session_log:
            t = task.get("task_type", "unknown")
            task_types[t] = task_types.get(t, 0) + 1
        
        if task_types:
            most_common = max(task_types.items(), key=lambda x: x[1])
            insights.append(f"主要任务类型: {most_common[0]} ({most_common[1]}次)")
        
        # 分析失败模式
        failures = [t for t in session_log if not t.get("success")]
        if failures:
            insights.append(f"失败任务数: {len(failures)}")
        
        return insights


# CLI 入口
if __name__ == "__main__":
    import sys
    
    reflector = TaskReflector()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            print(json.dumps(reflector.get_stats(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "patterns":
            print(json.dumps(reflector.get_patterns(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "lessons":
            print(json.dumps(reflector.get_lessons(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "recent":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            print(json.dumps(reflector.get_recent_reflections(count), indent=2, ensure_ascii=False))
        else:
            print("用法: python task-reflector.py [stats|patterns|lessons|recent]")
    else:
        print("任务反思引擎 v1.0")
        print(f"总反思数: {reflector.get_stats()['total']}")
        print(f"成功率: {reflector.get_stats()['success']/max(reflector.get_stats()['total'],1)*100:.1f}%")