#!/usr/bin/env python3
"""
Agent Metrics Collector - Agent指标收集与监控系统
收集每个Agent的运行指标，支持历史查询和告警
"""
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading


class AgentMetrics:
    """单个Agent的指标数据"""
    
    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.tasks_total = 0
        self.tasks_success = 0
        self.tasks_failed = 0
        self.total_response_time = 0.0  # 毫秒
        self.start_time = datetime.now()
        self.last_task_time = None
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.status = "idle"  # idle, busy, error, offline
        self.error_history = deque(maxlen=10)
        self.task_history = deque(maxlen=100)  # 最近100个任务
    
    @property
    def success_rate(self) -> float:
        if self.tasks_total == 0:
            return 100.0
        return round(self.tasks_success / self.tasks_total * 100, 2)
    
    @property
    def avg_response_time(self) -> float:
        if self.tasks_success == 0:
            return 0.0
        return round(self.total_response_time / self.tasks_success, 2)
    
    @property
    def uptime_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()
    
    def record_task(self, success: bool, response_time: float, error: str = None):
        """记录任务执行结果"""
        self.tasks_total += 1
        if success:
            self.tasks_success += 1
        else:
            self.tasks_failed += 1
        
        self.total_response_time += response_time
        self.last_task_time = datetime.now()
        
        # 记录到任务历史
        self.task_history.append({
            "time": self.last_task_time.isoformat(),
            "success": success,
            "response_time": response_time,
            "error": error
        })
        
        if error:
            self.error_history.append({
                "time": datetime.now().isoformat(),
                "error": error
            })
    
    def set_status(self, status: str):
        """更新Agent状态"""
        self.status = status
    
    def set_resources(self, cpu: float, memory: float):
        """更新资源使用情况"""
        self.cpu_usage = cpu
        self.memory_usage = memory
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "tasks_total": self.tasks_total,
            "tasks_success": self.tasks_success,
            "tasks_failed": self.tasks_failed,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "uptime_seconds": self.uptime_seconds,
            "status": self.status,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "last_task_time": self.last_task_time.isoformat() if self.last_task_time else None,
            "error_count": len(self.error_history),
            "recent_errors": list(self.error_history)
        }


class MetricsCollector:
    """指标收集器 - 收集所有Agent的指标"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.metrics: Dict[str, AgentMetrics] = {}
        self.history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1440))  # 保留24小时数据(每分钟)
        self.lock = threading.Lock()
        self.state_file = Path(__file__).parent / "metrics_state.json"
        self._load_state()
    
    def _load_state(self):
        """加载保存的状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # 恢复Agent指标
                    for agent_id, m in data.get('metrics', {}).items():
                        metrics = AgentMetrics(m['agent_id'], m['agent_name'])
                        metrics.tasks_total = m.get('tasks_total', 0)
                        metrics.tasks_success = m.get('tasks_success', 0)
                        metrics.tasks_failed = m.get('tasks_failed', 0)
                        metrics.total_response_time = m.get('total_response_time', 0)
                        metrics.status = m.get('status', 'idle')
                        metrics.cpu_usage = m.get('cpu_usage', 0)
                        metrics.memory_usage = m.get('memory_usage', 0)
                        if m.get('start_time'):
                            metrics.start_time = datetime.fromisoformat(m['start_time'])
                        self.metrics[agent_id] = metrics
                    print(f"[Metrics] 已恢复 {len(self.metrics)} 个Agent的指标")
            except Exception as e:
                print(f"[Metrics] 状态加载失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        try:
            data = {
                "metrics": {
                    agent_id: m.to_dict() for agent_id, m in self.metrics.items()
                },
                "saved_at": datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Metrics] 状态保存失败: {e}")
    
    def register_agent(self, agent_id: str, agent_name: str) -> AgentMetrics:
        """注册Agent并创建指标记录"""
        with self.lock:
            if agent_id not in self.metrics:
                self.metrics[agent_id] = AgentMetrics(agent_id, agent_name)
                print(f"[Metrics] 注册Agent: {agent_name} ({agent_id})")
            return self.metrics[agent_id]
    
    def unregister_agent(self, agent_id: str):
        """注销Agent"""
        with self.lock:
            if agent_id in self.metrics:
                del self.metrics[agent_id]
                print(f"[Metrics] 注销Agent: {agent_id}")
    
    def record_task(self, agent_id: str, success: bool, response_time: float, error: str = None):
        """记录任务执行"""
        with self.lock:
            if agent_id not in self.metrics:
                self.register_agent(agent_id, agent_id)
            self.metrics[agent_id].record_task(success, response_time, error)
    
    def update_status(self, agent_id: str, status: str):
        """更新Agent状态"""
        with self.lock:
            if agent_id in self.metrics:
                self.metrics[agent_id].set_status(status)
    
    def update_resources(self, agent_id: str, cpu: float, memory: float):
        """更新资源使用"""
        with self.lock:
            if agent_id in self.metrics:
                self.metrics[agent_id].set_resources(cpu, memory)
    
    def get_metrics(self, agent_id: str) -> Optional[Dict]:
        """获取指定Agent的指标"""
        with self.lock:
            if agent_id in self.metrics:
                return self.metrics[agent_id].to_dict()
            return None
    
    def get_all_metrics(self) -> List[Dict]:
        """获取所有Agent的指标"""
        with self.lock:
            return [m.to_dict() for m in self.metrics.values()]
    
    def get_summary(self) -> Dict:
        """获取汇总统计"""
        with self.lock:
            total_tasks = sum(m.tasks_total for m in self.metrics.values())
            total_success = sum(m.tasks_success for m in self.metrics.values())
            total_failed = sum(m.tasks_failed for m in self.metrics.values())
            
            agents_by_status = defaultdict(int)
            for m in self.metrics.values():
                agents_by_status[m.status] += 1
            
            return {
                "total_agents": len(self.metrics),
                "total_tasks": total_tasks,
                "total_success": total_success,
                "total_failed": total_failed,
                "overall_success_rate": round(total_success / total_tasks * 100, 2) if total_tasks > 0 else 100.0,
                "agents_by_status": dict(agents_by_status),
                "timestamp": datetime.now().isoformat()
            }
    
    def collect_snapshot(self):
        """收集当前快照并存入历史"""
        with self.lock:
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "summary": self.get_summary(),
                "agents": [m.to_dict() for m in self.metrics.values()]
            }
            
            # 存入历史
            for agent_id, m in self.metrics.items():
                if agent_id not in self.history:
                    self.history[agent_id] = deque(maxlen=1440)
                self.history[agent_id].append({
                    "time": datetime.now().isoformat(),
                    "tasks_total": m.tasks_total,
                    "tasks_success": m.tasks_success,
                    "success_rate": m.success_rate,
                    "avg_response_time": m.avg_response_time,
                    "cpu_usage": m.cpu_usage,
                    "memory_usage": m.memory_usage,
                    "status": m.status
                })
            
            # 定期保存状态
            self._save_state()
            
            return snapshot
    
    def get_history(self, agent_id: str, minutes: int = 60) -> List[Dict]:
        """获取Agent的历史指标"""
        with self.lock:
            if agent_id not in self.history:
                return []
            return list(self.history[agent_id])
    
    def get_trends(self, agent_id: str) -> Dict:
        """分析Agent趋势"""
        with self.lock:
            if agent_id not in self.history or len(self.history[agent_id]) < 2:
                return {"trend": "insufficient_data"}
            
            history = list(self.history[agent_id])
            
            # 计算最近和之前的平均值
            recent = history[-10:] if len(history) >= 10 else history
            older = history[:-10] if len(history) >= 10 else []
            
            if not older:
                return {"trend": "insufficient_data"}
            
            def avg(items, key):
                return sum(item.get(key, 0) for item in items) / len(items) if items else 0
            
            trends = {
                "success_rate_change": avg(recent, "success_rate") - avg(older, "success_rate"),
                "response_time_change": avg(recent, "avg_response_time") - avg(older, "avg_response_time"),
                "cpu_change": avg(recent, "cpu_usage") - avg(older, "cpu_usage"),
            }
            
            # 判断趋势方向
            for key in ["success_rate_change", "response_time_change", "cpu_change"]:
                value = trends[key]
                if key == "success_rate_change":
                    trends[f"{key}_direction"] = "up" if value > 1 else ("down" if value < -1 else "stable")
                else:
                    trends[f"{key}_direction"] = "up" if value > 5 else ("down" if value < -5 else "stable")
            
            return trends


class MetricsAlert:
    """指标告警器"""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.thresholds = {
            "success_rate_min": 80.0,  # 最低成功率
            "response_time_max": 5000,  # 最大响应时间(ms)
            "cpu_max": 90.0,  # 最大CPU使用率
            "memory_max": 90.0,  # 最大内存使用率
            "error_rate_max": 20.0,  # 最大错误率
            "offline_timeout": 300  # 离线超时时间(秒)
        }
        self.alerts = []
    
    def check_agent(self, agent_id: str) -> List[Dict]:
        """检查单个Agent是否需要告警"""
        metrics = self.collector.get_metrics(agent_id)
        if not metrics:
            return []
        
        alerts = []
        
        # 检查成功率
        if metrics["success_rate"] < self.thresholds["success_rate_min"]:
            alerts.append({
                "type": "success_rate_low",
                "level": "warning",
                "message": f"Agent {metrics['agent_name']} 成功率过低: {metrics['success_rate']}%",
                "value": metrics["success_rate"],
                "threshold": self.thresholds["success_rate_min"]
            })
        
        # 检查响应时间
        if metrics["avg_response_time"] > self.thresholds["response_time_max"]:
            alerts.append({
                "type": "response_time_high",
                "level": "warning",
                "message": f"Agent {metrics['agent_name']} 响应时间过高: {metrics['avg_response_time']}ms",
                "value": metrics["avg_response_time"],
                "threshold": self.thresholds["response_time_max"]
            })
        
        # 检查CPU
        if metrics["cpu_usage"] > self.thresholds["cpu_max"]:
            alerts.append({
                "type": "cpu_high",
                "level": "critical",
                "message": f"Agent {metrics['agent_name']} CPU使用率过高: {metrics['cpu_usage']}%",
                "value": metrics["cpu_usage"],
                "threshold": self.thresholds["cpu_max"]
            })
        
        # 检查内存
        if metrics["memory_usage"] > self.thresholds["memory_max"]:
            alerts.append({
                "type": "memory_high",
                "level": "critical",
                "message": f"Agent {metrics['agent_name']} 内存使用率过高: {metrics['memory_usage']}%",
                "value": metrics["memory_usage"],
                "threshold": self.thresholds["memory_max"]
            })
        
        # 检查错误率
        error_rate = 100 - metrics["success_rate"]
        if error_rate > self.thresholds["error_rate_max"]:
            alerts.append({
                "type": "error_rate_high",
                "level": "critical",
                "message": f"Agent {metrics['agent_name']} 错误率过高: {error_rate}%",
                "value": error_rate,
                "threshold": self.thresholds["error_rate_max"]
            })
        
        # 检查离线
        if metrics["status"] == "offline":
            alerts.append({
                "type": "agent_offline",
                "level": "critical",
                "message": f"Agent {metrics['agent_name']} 已离线",
                "value": metrics["status"],
                "threshold": "online"
            })
        
        # 检查超时无任务
        if metrics["last_task_time"]:
            last_time = datetime.fromisoformat(metrics["last_task_time"])
            idle_time = (datetime.now() - last_time).total_seconds()
            if idle_time > self.thresholds["offline_timeout"] and metrics["status"] == "idle":
                alerts.append({
                    "type": "agent_idle_timeout",
                    "level": "warning",
                    "message": f"Agent {metrics['agent_name']} 长时间无任务: {int(idle_time)}s",
                    "value": idle_time,
                    "threshold": self.thresholds["offline_timeout"]
                })
        
        return alerts
    
    def check_all(self) -> List[Dict]:
        """检查所有Agent"""
        all_alerts = []
        for metrics in self.collector.get_all_metrics():
            agent_alerts = self.check_agent(metrics["agent_id"])
            all_alerts.extend(agent_alerts)
        return all_alerts


# 演示测试
if __name__ == "__main__":
    collector = MetricsCollector()
    
    # 注册测试Agent
    collector.register_agent("agent_001", "WebScraper")
    collector.register_agent("agent_002", "DataProcessor")
    collector.register_agent("agent_003", "MLEngine")
    
    # 模拟任务记录
    collector.record_task("agent_001", True, 120.5)
    collector.record_task("agent_001", True, 98.2)
    collector.record_task("agent_001", False, 2000.0, "Timeout")
    collector.record_task("agent_002", True, 500.0)
    collector.record_task("agent_003", True, 1500.0)
    
    collector.update_status("agent_001", "busy")
    collector.update_resources("agent_001", 45.5, 62.3)
    
    # 收集快照
    snapshot = collector.collect_snapshot()
    print(f"\n[Metrics] 快照收集完成")
    
    # 输出汇总
    summary = collector.get_summary()
    print(f"\n=== 指标汇总 ===")
    print(f"总Agent数: {summary['total_agents']}")
    print(f"总任务数: {summary['total_tasks']}")
    print(f"成功率: {summary['overall_success_rate']}%")
    print(f"状态分布: {summary['agents_by_status']}")
    
    # 输出各Agent指标
    print(f"\n=== Agent指标详情 ===")
    for m in collector.get_all_metrics():
        print(f"\n[{m['agent_name']}]")
        print(f"  状态: {m['status']}")
        print(f"  任务: {m['tasks_success']}/{m['tasks_total']} (成功率: {m['success_rate']}%)")
        print(f"  平均响应: {m['avg_response_time']}ms")
        print(f"  CPU: {m['cpu_usage']}%, 内存: {m['memory_usage']}%")
    
    # 告警检查
    alertor = MetricsAlert(collector)
    alerts = alertor.check_all()
    print(f"\n=== 告警检查 ===")
    if alerts:
        for alert in alerts:
            print(f"[{alert['level'].upper()}] {alert['message']}")
    else:
        print("无告警")
    
    # 保存状态
    collector._save_state()
    print(f"\n[Metrics] 状态已保存")