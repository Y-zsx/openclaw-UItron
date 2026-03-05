#!/usr/bin/env python3
"""
分析Agent - 决策支持核心
负责分析任务、评估可行性、提供优化建议
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))


class AnalyzerAgent:
    """分析Agent - 智能决策支持"""
    
    def __init__(self):
        self.name = "analyzer"
        self.version = "1.0"
        self.analysis_history = []
        
    def analyze_task(self, task: Dict) -> Dict:
        """
        分析任务并提供评估报告
        """
        task_id = task.get("id", "unknown")
        task_type = task.get("type", "unknown")
        task_data = task.get("data", {})
        
        analysis = {
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "complexity": self._assess_complexity(task),
            "feasibility": self._assess_feasibility(task),
            "risks": self._identify_risks(task),
            "recommendations": self._generate_recommendations(task),
            "estimated_duration": self._estimate_duration(task),
            "dependencies": self._find_dependencies(task),
            "priority": self._calculate_priority(task)
        }
        
        self.analysis_history.append(analysis)
        return analysis
    
    def _assess_complexity(self, task: Dict) -> str:
        """评估任务复杂度"""
        complexity_score = 0
        
        # 检查任务类型
        task_type = task.get("type", "")
        if task_type in ["execute", "send"]:
            complexity_score += 1
        elif task_type in ["analyze", "orchestrate"]:
            complexity_score += 3
        elif task_type == "learn":
            complexity_score += 2
            
        # 检查数据量
        data = task.get("data", {})
        if isinstance(data, dict):
            complexity_score += min(len(data) // 3, 2)
            
        if complexity_score <= 2:
            return "simple"
        elif complexity_score <= 4:
            return "moderate"
        else:
            return "complex"
    
    def _assess_feasibility(self, task: Dict) -> float:
        """评估任务可行性 (0-1)"""
        feasibility = 1.0
        
        # 检查必要字段
        if not task.get("type"):
            feasibility -= 0.3
        if not task.get("data"):
            feasibility -= 0.2
            
        # 检查任务类型是否支持
        supported_types = ["execute", "send", "analyze", "orchestrate", "learn", "monitor"]
        if task.get("type") not in supported_types:
            feasibility -= 0.4
            
        return max(0.0, feasibility)
    
    def _identify_risks(self, task: Dict) -> List[str]:
        """识别任务风险"""
        risks = []
        
        task_type = task.get("type", "")
        data = task.get("data", {})
        
        # 执行类任务风险
        if task_type == "execute":
            command = data.get("command", "")
            if "rm -rf" in command or "dd if=" in command:
                risks.append("HIGH: 危险命令检测")
            if not command:
                risks.append("MEDIUM: 缺少执行命令")
                
        # 消息类任务风险
        if task_type == "send":
            if not data.get("message"):
                risks.append("MEDIUM: 消息内容为空")
                
        # 依赖风险
        if task.get("depends_on"):
            risks.append("LOW: 存在任务依赖")
            
        return risks
    
    def _generate_recommendations(self, task: Dict) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        task_type = task.get("type", "")
        
        if task_type == "execute":
            recommendations.append("建议使用异步执行避免阻塞")
            recommendations.append("考虑添加超时控制")
            
        elif task_type == "orchestrate":
            recommendations.append("建议添加重试机制")
            recommendations.append("考虑任务拆分以提高并行度")
            
        elif task_type == "learn":
            recommendations.append("建议设置学习频率限制")
            recommendations.append("考虑增量学习而非全量学习")
            
        return recommendations
    
    def _estimate_duration(self, task: Dict) -> int:
        """估算任务执行时间(秒)"""
        base_times = {
            "execute": 30,
            "send": 5,
            "analyze": 15,
            "orchestrate": 60,
            "learn": 120,
            "monitor": 10
        }
        
        base = base_times.get(task.get("type", "execute"), 30)
        
        # 根据复杂度调整
        if self._assess_complexity(task) == "complex":
            base *= 2
        elif self._assess_complexity(task) == "moderate":
            base *= 1.5
            
        return int(base)
    
    def _find_dependencies(self, task: Dict) -> List[str]:
        """查找任务依赖"""
        return task.get("depends_on", [])
    
    def _calculate_priority(self, task: Dict) -> int:
        """计算任务优先级(1-10)"""
        priority = 5
        
        # 根据任务类型
        type_priorities = {
            "execute": 7,
            "send": 6,
            "analyze": 5,
            "orchestrate": 8,
            "learn": 3,
            "monitor": 4
        }
        priority = type_priorities.get(task.get("type", "analyze"), 5)
        
        # 根据紧急程度
        if task.get("urgent"):
            priority = min(10, priority + 3)
            
        return priority
    
    def compare_options(self, options: List[Dict]) -> Dict:
        """
        比较多个选项并推荐最佳方案
        """
        if not options:
            return {"recommendation": None, "reason": "无可用选项"}
            
        scored = []
        for i, opt in enumerate(options):
            score = 0
            # 评分逻辑
            score += opt.get("efficiency", 0.5) * 40
            score += opt.get("reliability", 0.5) * 30
            score += (1 - opt.get("cost", 0.5)) * 30
            scored.append({"index": i, "option": opt, "score": score})
            
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "recommendation": scored[0]["option"],
            "reason": f"综合得分最高: {scored[0]['score']:.1f}",
            "alternatives": [s["option"] for s in scored[1:3]]
        }
    
    def get_statistics(self) -> Dict:
        """获取分析统计"""
        return {
            "total_analyses": len(self.analysis_history),
            "recent": self.analysis_history[-5:] if self.analysis_history else []
        }


def handle_request(data: Dict) -> Dict:
    """处理分析请求"""
    agent = AnalyzerAgent()
    action = data.get("action", "analyze_task")
    
    if action == "analyze_task":
        task = data.get("task", {})
        result = agent.analyze_task(task)
        return {"status": "success", "analysis": result}
    
    elif action == "compare_options":
        options = data.get("options", [])
        result = agent.compare_options(options)
        return {"status": "success", "comparison": result}
    
    elif action == "statistics":
        result = agent.get_statistics()
        return {"status": "success", "statistics": result}
    
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


if __name__ == "__main__":
    # 测试
    test_task = {
        "id": "test-001",
        "type": "execute",
        "data": {"command": "echo hello"},
        "urgent": False
    }
    
    result = handle_request({"action": "analyze_task", "task": test_task})
    print(json.dumps(result, indent=2, ensure_ascii=False))