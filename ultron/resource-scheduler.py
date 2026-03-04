#!/usr/bin/env python3
"""
奥创资源调度器 - 夙愿八：智能决策优化系统 第2世
功能：自适应资源分配 + 负载均衡 + 优先级调度
创建时间: 2026-03-04
"""

import os
import time
import json
import subprocess
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import deque


class ResourceScheduler:
    """智能资源调度系统"""
    
    def __init__(self):
        self.data_dir = "/root/.openclaw/workspace/ultron/data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 资源阈值
        self.thresholds = {
            "cpu_high": 75.0,
            "cpu_low": 20.0,
            "memory_high": 80.0,
            "memory_low": 30.0,
            "load_balance_threshold": 0.3,  # 负载差异阈值
        }
        
        # 优先级配置
        self.priority_levels = {
            "critical": 0,
            "high": 1,
            "normal": 2,
            "low": 3,
            "background": 4
        }
        
        # 任务队列
        self.task_queue = deque()
        self.running_tasks = {}
        self.task_history = []
        
        # 资源历史（用于趋势分析）
        self.resource_history = deque(maxlen=60)  # 保留60个采样点
    
    def get_current_resources(self) -> Dict:
        """获取当前资源状态"""
        try:
            # CPU
            result = subprocess.run(
                ["cat", "/proc/stat"],
                capture_output=True, text=True, timeout=5
            )
            cpu_line = result.stdout.strip().split("\n")[0]
            parts = cpu_line.split()
            total = sum(float(x) for x in parts[1:8] if x.replace('.','').isdigit())
            idle = float(parts[4])
            cpu_usage = 100 - (idle / total * 100) if total > 0 else 0
            
            # 内存
            result = subprocess.run(
                ["free", "-b"],
                capture_output=True, text=True, timeout=5
            )
            mem_line = result.stdout.strip().split("\n")[1].split()
            mem_total = int(mem_line[1])
            mem_used = int(mem_line[2])
            mem_available = int(mem_line[6]) if len(mem_line) > 6 else int(mem_line[3])
            mem_usage = (mem_used / mem_total) * 100
            
            # 负载
            load1, load5, load15 = os.getloadavg()
            
            # 进程数
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, timeout=5
            )
            process_count = len(result.stdout.strip().split("\n")) - 1
            
            return {
                "cpu_usage": cpu_usage,
                "memory_usage": mem_usage,
                "memory_total": mem_total,
                "memory_available": mem_available,
                "load_1m": load1,
                "load_5m": load5,
                "process_count": process_count,
                "cpu_count": os.cpu_count(),
                "timestamp": time.time()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def analyze_resource_trend(self) -> Dict:
        """分析资源趋势"""
        if len(self.resource_history) < 5:
            return {"trend": "insufficient_data"}
        
        # 简单线性趋势分析
        recent = list(self.resource_history)[-10:]
        
        cpu_values = [r["cpu_usage"] for r in recent if "cpu_usage" in r]
        mem_values = [r["memory_usage"] for r in recent if "memory_usage" in r]
        
        def calc_trend(values):
            if len(values) < 2:
                return "stable"
            diff = values[-1] - values[0]
            if diff > 10:
                return "increasing"
            elif diff < -10:
                return "decreasing"
            return "stable"
        
        return {
            "cpu_trend": calc_trend(cpu_values),
            "memory_trend": calc_trend(mem_values),
            "samples": len(recent)
        }
    
    def adaptive_allocation(self) -> Dict:
        """自适应资源分配"""
        resources = self.get_current_resources()
        self.resource_history.append(resources)
        
        if "error" in resources:
            return {"error": resources["error"]}
        
        cpu_usage = resources["cpu_usage"]
        mem_usage = resources["memory_usage"]
        load = resources["load_1m"]
        cpu_count = resources["cpu_count"]
        
        # 计算可用资源
        available_cpu = 100 - cpu_usage
        available_memory = resources["memory_available"]
        
        # 基于当前状态和趋势动态调整
        trend = self.analyze_resource_trend()
        
        # 分配策略
        allocation = {
            "timestamp": datetime.now().isoformat(),
            "current_state": {
                "cpu_usage": f"{cpu_usage:.1f}%",
                "memory_usage": f"{mem_usage:.1f}%",
                "load": f"{load:.2f}"
            },
            "available": {
                "cpu_percent": available_cpu,
                "memory_bytes": available_memory
            },
            "trend": trend,
            "recommended_actions": []
        }
        
        # CPU分配决策
        if cpu_usage > self.thresholds["cpu_high"]:
            allocation["recommended_actions"].append({
                "type": "cpu_throttle",
                "priority": "high",
                "action": "降低非关键任务优先级",
                "reason": f"CPU使用率 {cpu_usage:.1f}% 超过阈值 {self.thresholds['cpu_high']}%"
            })
        elif cpu_usage < self.thresholds["cpu_low"]:
            allocation["recommended_actions"].append({
                "type": "cpu_scale_up",
                "priority": "medium",
                "action": "可以增加计算任务",
                "reason": f"CPU空闲 {available_cpu:.1f}%，资源充足"
            })
        
        # 内存分配决策
        if mem_usage > self.thresholds["memory_high"]:
            allocation["recommended_actions"].append({
                "type": "memory_release",
                "priority": "high",
                "action": "清理缓存或释放内存",
                "reason": f"内存使用率 {mem_usage:.1f}% 超过阈值"
            })
        
        # 趋势预测
        if trend.get("cpu_trend") == "increasing":
            allocation["recommended_actions"].append({
                "type": "predictive_scale",
                "priority": "warning",
                "action": "CPU使用率上升中，准备资源扩展",
                "reason": "检测到CPU使用率持续上升"
            })
        
        return allocation
    
    def load_balance(self) -> Dict:
        """负载均衡分析"""
        resources = self.get_current_resources()
        
        load = resources.get("load_1m", 0)
        cpu_count = resources.get("cpu_count", 4)
        cpu_usage = resources.get("cpu_usage", 0)
        
        # 计算负载均衡分数
        # 理想情况：负载接近但不超过CPU核心数
        ideal_load = cpu_count
        load_ratio = load / ideal_load if ideal_load > 0 else 0
        
        # 分析各维度负载
        balance_analysis = {
            "timestamp": datetime.now().isoformat(),
            "load_metrics": {
                "current_load": load,
                "cpu_cores": cpu_count,
                "ideal_load": ideal_load,
                "load_ratio": load_ratio,
                "cpu_usage": cpu_usage
            },
            "balance_score": 100,
            "status": "balanced",
            "recommendations": []
        }
        
        # 计算均衡分数
        if load_ratio <= 0.5:
            balance_analysis["balance_score"] = 100
            balance_analysis["status"] = "idle"
            balance_analysis["recommendations"].append({
                "action": "资源充足，可以接受更多任务",
                "priority": "low"
            })
        elif load_ratio <= 0.8:
            balance_analysis["balance_score"] = 100 - (load_ratio - 0.5) * 100
            balance_analysis["status"] = "optimal"
            balance_analysis["recommendations"].append({
                "action": "负载最优，继续保持",
                "priority": "low"
            })
        elif load_ratio <= 1.0:
            balance_analysis["balance_score"] = 80 - (load_ratio - 0.8) * 200
            balance_analysis["status"] = "busy"
            balance_analysis["recommendations"].append({
                "action": "负载较高，注意监控",
                "priority": "medium"
            })
        else:
            max_score = max(0, 60 - (load_ratio - 1.0) * 100)
            balance_analysis["balance_score"] = max_score
            balance_analysis["status"] = "overloaded"
            balance_analysis["recommendations"].append({
                "action": "负载超过能力，考虑扩容或限流",
                "priority": "high"
            })
        
        # CPU与负载关系分析
        if cpu_usage < 50 and load > cpu_count:
            balance_analysis["recommendations"].append({
                "action": "检测到IO等待或阻塞进程",
                "priority": "medium",
                "reason": "负载高但CPU使用低"
            })
        
        return balance_analysis
    
    def priority_schedule(self, tasks: List[Dict]) -> List[Dict]:
        """优先级调度"""
        # 为每个任务计算优先级分数
        scored_tasks = []
        
        for task in tasks:
            priority = task.get("priority", "normal")
            priority_score = self.priority_levels.get(priority, 2)
            
            # 考虑资源紧张程度的调整
            resources = self.get_current_resources()
            resource_factor = 1.0
            
            if resources.get("cpu_usage", 0) > 80:
                # 资源紧张时，提高高优先级任务权重
                if priority in ["critical", "high"]:
                    resource_factor = 0.5  # 更快调度
                elif priority == "low":
                    resource_factor = 2.0  # 延缓调度
            
            # 计算最终调度分数（越低越先调度）
            final_score = priority_score * resource_factor
            
            scored_tasks.append({
                **task,
                "schedule_score": final_score,
                "scheduled": False
            })
        
        # 按分数排序
        scored_tasks.sort(key=lambda x: x["schedule_score"])
        
        return scored_tasks
    
    def execute_scheduled_task(self, task: Dict) -> Dict:
        """执行调度的任务"""
        task_id = task.get("id", f"task_{int(time.time())}")
        
        self.running_tasks[task_id] = {
            **task,
            "start_time": time.time(),
            "status": "running"
        }
        
        # 模拟任务执行（实际会根据任务类型执行）
        result = {
            "task_id": task_id,
            "status": "started",
            "start_time": datetime.now().isoformat()
        }
        
        return result
    
    def get_schedule_status(self) -> Dict:
        """获取调度状态"""
        return {
            "timestamp": datetime.now().isoformat(),
            "queue_length": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "resource_allocation": self.adaptive_allocation(),
            "load_balance": self.load_balance()
        }
    
    def run_full_analysis(self) -> Dict:
        """运行完整调度分析"""
        print("📊 资源调度分析")
        print("="*50)
        
        # 自适应分配
        allocation = self.adaptive_allocation()
        print(f"\n💻 CPU: {allocation['current_state']['cpu_usage']}")
        print(f"🧠 内存: {allocation['current_state']['memory_usage']}")
        print(f"⚖️  负载: {allocation['current_state']['load']}")
        
        if allocation.get("trend", {}).get("trend") != "insufficient_data":
            print(f"📈 趋势: CPU={allocation['trend'].get('cpu_trend')}, "
                  f"内存={allocation['trend'].get('memory_trend')}")
        
        # 负载均衡
        balance = self.load_balance()
        print(f"\n⚖️  负载均衡状态: {balance['status'].upper()}")
        print(f"📊 均衡分数: {balance['balance_score']}/100")
        
        # 建议
        print("\n💡 调度建议:")
        for action in allocation.get("recommended_actions", []):
            print(f"  [{action['priority'].upper()}] {action['action']}")
        
        for rec in balance.get("recommendations", []):
            print(f"  [{rec.get('priority', 'low').upper()}] {rec.get('action')}")
        
        print("="*50)
        
        # 保存报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "allocation": allocation,
            "load_balance": balance,
            "summary": {
                "status": balance["status"],
                "balance_score": balance["balance_score"]
            }
        }
        
        report_file = f"{self.data_dir}/scheduler_report_{int(time.time())}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        return report


def main():
    scheduler = ResourceScheduler()
    report = scheduler.run_full_analysis()
    return report


if __name__ == "__main__":
    main()