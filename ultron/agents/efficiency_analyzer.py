#!/usr/bin/env python3
"""
效率分析器 - 多智能体协作网络
第3世：协作优化 - 协作效率分析
"""

import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta

@dataclass
class TaskRecord:
    task_id: str
    task_name: str
    agent_id: str
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    success: bool = True
    complexity: int = 1
    
    @property
    def duration(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return 0.0

@dataclass
class AgentMetrics:
    agent_id: str
    agent_name: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_duration: float = 0.0
    last_active: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0
    
    @property
    def avg_duration(self) -> float:
        return self.total_duration / self.tasks_completed if self.tasks_completed > 0 else 0.0

class EfficiencyAnalyzer:
    """效率分析器"""
    
    def __init__(self):
        self.task_records: List[TaskRecord] = []
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        self.analysis_window: float = 3600.0  # 1小时分析窗口
        
    def record_task_start(self, task_id: str, agent_id: str):
        """记录任务开始"""
        for record in self.task_records:
            if record.task_id == task_id and record.started_at is None:
                record.started_at = time.time()
                return True
        return False
    
    def record_task_complete(self, task_id: str, success: bool = True):
        """记录任务完成"""
        for record in self.task_records:
            if record.task_id == task_id:
                record.completed_at = time.time()
                record.success = success
                # 更新代理指标
                if record.agent_id in self.agent_metrics:
                    metrics = self.agent_metrics[record.agent_id]
                    if success:
                        metrics.tasks_completed += 1
                    else:
                        metrics.tasks_failed += 1
                    metrics.total_duration += record.duration
                    metrics.last_active = time.time()
                return True
        return False
    
    def add_task(self, task_id: str, task_name: str, agent_id: str, 
                 agent_name: str, complexity: int = 1):
        """添加新任务记录"""
        record = TaskRecord(
            task_id=task_id,
            task_name=task_name,
            agent_id=agent_id,
            created_at=time.time(),
            complexity=complexity
        )
        self.task_records.append(record)
        
        # 初始化代理指标
        if agent_id not in self.agent_metrics:
            self.agent_metrics[agent_id] = AgentMetrics(agent_id, agent_name)
    
    def get_agent_efficiency(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取单个代理效率"""
        if agent_id not in self.agent_metrics:
            return None
            
        metrics = self.agent_metrics[agent_id]
        return {
            "agent_id": agent_id,
            "agent_name": metrics.agent_name,
            "tasks_completed": metrics.tasks_completed,
            "tasks_failed": metrics.tasks_failed,
            "success_rate": round(metrics.success_rate * 100, 2),
            "avg_duration": round(metrics.avg_duration, 2),
            "total_work_time": round(metrics.total_duration, 2),
            "last_active": datetime.fromtimestamp(metrics.last_active).isoformat() 
                if metrics.last_active else None
        }
    
    def get_collaboration_score(self) -> Dict[str, Any]:
        """计算协作效率得分"""
        if not self.agent_metrics:
            return {"score": 0, "grade": "N/A", "factors": {}}
        
        # 计算各项指标
        total_tasks = sum(m.tasks_completed + m.tasks_failed for m in self.agent_metrics.values())
        total_success = sum(m.tasks_completed for m in self.agent_metrics.values())
        success_rate = total_success / total_tasks if total_tasks > 0 else 0
        
        # 计算负载均衡度
        workloads = [m.tasks_completed for m in self.agent_metrics.values()]
        avg_workload = sum(workloads) / len(workloads) if workloads else 0
        if avg_workload > 0:
            balance_factor = 1 - (max(workloads) - min(workloads)) / (avg_workload * 2)
            balance_factor = max(0, min(1, balance_factor))
        else:
            balance_factor = 1.0
        
        # 计算响应时间
        recent_records = [r for r in self.task_records 
                         if time.time() - r.created_at < self.analysis_window]
        if recent_records:
            avg_response = sum(r.duration for r in recent_records) / len(recent_records)
        else:
            avg_response = 0
        
        # 综合评分 (0-100)
        score = (
            success_rate * 40 +      # 成功率占40%
            balance_factor * 30 +    # 负载均衡占30%
            (1 - min(avg_response / 60, 1)) * 30  # 响应时间占30%
        ) * 100
        
        # 评级
        if score >= 90:
            grade = "A+"
        elif score >= 80:
            grade = "A"
        elif score >= 70:
            grade = "B"
        elif score >= 60:
            grade = "C"
        else:
            grade = "D"
        
        return {
            "score": round(score, 2),
            "grade": grade,
            "factors": {
                "success_rate": round(success_rate * 100, 2),
                "load_balance": round(balance_factor * 100, 2),
                "avg_response_time": round(avg_response, 2),
                "total_tasks": total_tasks
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def get_bottlenecks(self) -> List[Dict[str, Any]]:
        """识别瓶颈"""
        bottlenecks = []
        
        # 检查低成功率代理
        for agent_id, metrics in self.agent_metrics.items():
            if metrics.tasks_completed + metrics.tasks_failed >= 3:  # 至少3个任务
                if metrics.success_rate < 0.7:
                    bottlenecks.append({
                        "type": "low_success_rate",
                        "agent_id": agent_id,
                        "agent_name": metrics.agent_name,
                        "success_rate": round(metrics.success_rate * 100, 2),
                        "severity": "high" if metrics.success_rate < 0.5 else "medium"
                    })
        
        # 检查负载不均
        if self.agent_metrics:
            workloads = [(m.agent_id, m.tasks_completed) for m in self.agent_metrics.values()]
            if workloads:
                max_load = max(w for _, w in workloads)
                min_load = min(w for _, w in workloads)
                if max_load > 0 and (max_load - min_load) / max_load > 0.5:
                    bottlenecks.append({
                        "type": "load_imbalance",
                        "max_load": max_load,
                        "min_load": min_load,
                        "severity": "medium"
                    })
        
        return bottlenecks
    
    def get_report(self) -> Dict[str, Any]:
        """生成完整分析报告"""
        return {
            "summary": self.get_collaboration_score(),
            "agent_details": {
                agent_id: self.get_agent_efficiency(agent_id)
                for agent_id in self.agent_metrics
            },
            "bottlenecks": self.get_bottlenecks(),
            "recent_tasks": [
                {
                    "task_id": r.task_id,
                    "task_name": r.task_name,
                    "agent": r.agent_id,
                    "duration": round(r.duration, 2),
                    "success": r.success
                }
                for r in self.task_records[-10:]
            ]
        }

# 单例
_analyzer = None

def get_analyzer() -> EfficiencyAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = EfficiencyAnalyzer()
    return _analyzer

if __name__ == "__main__":
    analyzer = get_analyzer()
    
    # 模拟数据
    analyzer.add_task("t1", "监控任务", "agent1", "Monitor-1", 2)
    analyzer.add_task("t2", "执行任务", "agent2", "Executor-1", 3)
    analyzer.add_task("t3", "学习任务", "agent3", "Learner-1", 1)
    
    print("Efficiency Report:")
    print(json.dumps(analyzer.get_report(), indent=2, ensure_ascii=False))