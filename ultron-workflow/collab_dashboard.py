#!/usr/bin/env python3
"""
Agent协作网络可视化仪表盘
=========================
提供实时Agent状态、任务分布、性能指标的可视化展示
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading

# 数据存储路径
DASHBOARD_DATA_DIR = os.path.expanduser("~/.ultron/dashboard")
os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)

class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class AgentInfo:
    """Agent信息"""
    agent_id: str
    name: str
    status: str
    capabilities: List[str]
    current_task: Optional[str] = None
    load: float = 0.0
    success_rate: float = 1.0
    avg_response_time: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_heartbeat: Optional[str] = None

@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    name: str
    priority: int
    status: str  # pending, running, completed, failed
    assigned_agent: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: float = 0.0
    retries: int = 0

@dataclass
class NetworkMetrics:
    """网络指标"""
    total_agents: int = 0
    active_agents: int = 0
    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_load: float = 0.0
    avg_success_rate: float = 0.0
    throughput: float = 0.0  # tasks/min
    timestamp: Optional[str] = None

class DashboardDataStore:
    """仪表盘数据存储"""
    
    def __init__(self):
        self.agents_file = os.path.join(DASHBOARD_DATA_DIR, "agents.json")
        self.tasks_file = os.path.join(DASHBOARD_DATA_DIR, "tasks.json")
        self.metrics_file = os.path.join(DASHBOARD_DATA_DIR, "metrics.json")
        self.history_file = os.path.join(DASHBOARD_DATA_DIR, "history.json")
        self._lock = threading.Lock()
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储"""
        if not os.path.exists(self.agents_file):
            self._save_json(self.agents_file, {})
        if not os.path.exists(self.tasks_file):
            self._save_json(self.tasks_file, {"pending": [], "running": [], "completed": [], "failed": []})
        if not os.path.exists(self.metrics_file):
            self._save_json(self.metrics_file, {"current": {}, "history": []})
        if not os.path.exists(self.history_file):
            self._save_json(self.history_file, [])
    
    def _load_json(self, filepath: str) -> Any:
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return None
    
    def _save_json(self, filepath: str, data: Any):
        with self._lock:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    
    def save_agent(self, agent: AgentInfo):
        """保存Agent信息"""
        agents = self._load_json(self.agents_file) or {}
        agents[agent.agent_id] = asdict(agent)
        self._save_json(self.agents_file, agents)
    
    def get_agents(self) -> Dict[str, AgentInfo]:
        """获取所有Agent"""
        data = self._load_json(self.agents_file) or {}
        return {k: AgentInfo(**v) for k, v in data.items()}
    
    def save_task(self, task: TaskInfo):
        """保存任务"""
        tasks = self._load_json(self.tasks_file)
        task_dict = asdict(task)
        
        # 根据状态分类存储
        status = task.status
        if status == "pending":
            tasks["pending"] = [t for t in tasks["pending"] if t.get("task_id") != task.task_id]
            tasks["pending"].append(task_dict)
        elif status == "running":
            tasks["running"] = [t for t in tasks["running"] if t.get("task_id") != task.task_id]
            tasks["running"].append(task_dict)
        elif status == "completed":
            tasks["completed"] = [t for t in tasks["completed"] if t.get("task_id") != task.task_id]
            tasks["completed"].append(task_dict)
        elif status == "failed":
            tasks["failed"] = [t for t in tasks["failed"] if t.get("task_id") != task.task_id]
            tasks["failed"].append(task_dict)
        
        self._save_json(self.tasks_file, tasks)
    
    def get_tasks(self) -> Dict[str, List[TaskInfo]]:
        """获取所有任务"""
        data = self._load_json(self.tasks_file) or {}
        result = {}
        for status, tasks in data.items():
            result[status] = [TaskInfo(**t) for t in tasks]
        return result
    
    def save_metrics(self, metrics: NetworkMetrics):
        """保存指标"""
        data = self._load_json(self.metrics_file) or {"current": {}, "history": []}
        metrics_dict = asdict(metrics)
        metrics_dict["timestamp"] = datetime.now().isoformat()
        
        data["current"] = metrics_dict
        
        # 保留最近100条历史记录
        history = data.get("history", [])
        history.append(metrics_dict)
        if len(history) > 100:
            history = history[-100:]
        data["history"] = history
        
        self._save_json(self.metrics_file, data)
    
    def get_metrics(self) -> NetworkMetrics:
        """获取当前指标"""
        data = self._load_json(self.metrics_file) or {}
        if data.get("current"):
            return NetworkMetrics(**data["current"])
        return NetworkMetrics()
    
    def get_metrics_history(self, limit: int = 20) -> List[NetworkMetrics]:
        """获取历史指标"""
        data = self._load_json(self.metrics_file) or {}
        history = data.get("history", [])
        return [NetworkMetrics(**m) for m in history[-limit:]]


class CollabDashboard:
    """协作网络可视化仪表盘"""
    
    def __init__(self):
        self.store = DashboardDataStore()
        self._update_lock = threading.Lock()
    
    # ========== Agent管理 ==========
    
    def register_agent(self, agent_id: str, name: str, capabilities: List[str]) -> AgentInfo:
        """注册新Agent"""
        agent = AgentInfo(
            agent_id=agent_id,
            name=name,
            status=AgentStatus.IDLE.value,
            capabilities=capabilities,
            last_heartbeat=datetime.now().isoformat()
        )
        self.store.save_agent(agent)
        return agent
    
    def update_agent_status(self, agent_id: str, status: str, 
                           current_task: Optional[str] = None,
                           load: Optional[float] = None):
        """更新Agent状态"""
        agents = self.store.get_agents()
        if agent_id in agents:
            agent = agents[agent_id]
            agent.status = status
            if current_task:
                agent.current_task = current_task
            if load is not None:
                agent.load = min(1.0, max(0.0, load))
            agent.last_heartbeat = datetime.now().isoformat()
            self.store.save_agent(agent)
    
    def update_agent_metrics(self, agent_id: str, success_rate: float = None,
                            avg_response_time: float = None, tasks_completed: int = None,
                            tasks_failed: int = None):
        """更新Agent性能指标"""
        agents = self.store.get_agents()
        if agent_id in agents:
            agent = agents[agent_id]
            if success_rate is not None:
                agent.success_rate = success_rate
            if avg_response_time is not None:
                agent.avg_response_time = avg_response_time
            if tasks_completed is not None:
                agent.tasks_completed = tasks_completed
            if tasks_failed is not None:
                agent.tasks_failed = tasks_failed
            self.store.save_agent(agent)
    
    def heartbeat(self, agent_id: str):
        """Agent心跳"""
        agents = self.store.get_agents()
        if agent_id in agents:
            agent = agents[agent_id]
            agent.last_heartbeat = datetime.now().isoformat()
            self.store.save_agent(agent)
    
    # ========== 任务管理 ==========
    
    def submit_task(self, task_id: str, name: str, priority: int = 2) -> TaskInfo:
        """提交新任务"""
        task = TaskInfo(
            task_id=task_id,
            name=name,
            priority=priority,
            status="pending",
            created_at=datetime.now().isoformat()
        )
        self.store.save_task(task)
        return task
    
    def assign_task(self, task_id: str, agent_id: str):
        """分配任务给Agent"""
        tasks = self.store.get_tasks()
        for status, task_list in tasks.items():
            for task in task_list:
                if task.task_id == task_id:
                    task.status = "running"
                    task.assigned_agent = agent_id
                    task.started_at = datetime.now().isoformat()
                    self.store.save_task(task)
                    
                    # 更新Agent状态
                    self.update_agent_status(agent_id, AgentStatus.BUSY.value, 
                                            current_task=task_id, load=1.0)
                    break
    
    def complete_task(self, task_id: str, success: bool = True):
        """完成任务"""
        tasks = self.store.get_tasks()
        for status, task_list in tasks.items():
            for task in task_list:
                if task.task_id == task_id:
                    task.status = "completed" if success else "failed"
                    task.completed_at = datetime.now().isoformat()
                    
                    if task.started_at:
                        start = datetime.fromisoformat(task.started_at)
                        task.duration = (datetime.now() - start).total_seconds()
                    
                    if task.assigned_agent:
                        # 更新Agent状态
                        if success:
                            agents = self.store.get_agents()
                            if task.assigned_agent in agents:
                                agent = agents[task.assigned_agent]
                                agent.tasks_completed = agent.tasks_completed + 1
                                agent.current_task = None
                                agent.load = 0.0
                                self.store.save_agent(agent)
                        else:
                            self.update_agent_status(task.assigned_agent, 
                                                    AgentStatus.IDLE.value, load=0.0)
                    
                    self.store.save_task(task)
                    break
    
    # ========== 指标计算 ==========
    
    def compute_metrics(self) -> NetworkMetrics:
        """计算网络指标"""
        agents = self.store.get_agents()
        tasks = self.store.get_tasks()
        
        active_count = sum(1 for a in agents.values() if a.status != AgentStatus.OFFLINE.value)
        
        total_tasks = (len(tasks.get("pending", [])) + 
                      len(tasks.get("running", [])) + 
                      len(tasks.get("completed", [])) + 
                      len(tasks.get("failed", [])))
        
        avg_load = sum(a.load for a in agents.values()) / max(len(agents), 1)
        avg_success = sum(a.success_rate for a in agents.values()) / max(len(agents), 1)
        
        metrics = NetworkMetrics(
            total_agents=len(agents),
            active_agents=active_count,
            total_tasks=total_tasks,
            pending_tasks=len(tasks.get("pending", [])),
            running_tasks=len(tasks.get("running", [])),
            completed_tasks=len(tasks.get("completed", [])),
            failed_tasks=len(tasks.get("failed", [])),
            avg_load=avg_load,
            avg_success_rate=avg_success,
            timestamp=datetime.now().isoformat()
        )
        
        self.store.save_metrics(metrics)
        return metrics
    
    # ========== 可视化输出 ==========
    
    def render_console(self) -> str:
        """渲染控制台视图"""
        agents = self.store.get_agents()
        tasks = self.store.get_tasks()
        metrics = self.compute_metrics()
        
        lines = []
        lines.append("=" * 60)
        lines.append("🤖 Agent协作网络可视化仪表盘")
        lines.append("=" * 60)
        lines.append(f"📊 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 网络概览
        lines.append("📈 网络概览")
        lines.append("-" * 40)
        lines.append(f"  Agents: {metrics.active_agents}/{metrics.total_agents} 在线")
        lines.append(f"  任务: {metrics.pending_tasks} 待处理 | {metrics.running_tasks} 运行中 | {metrics.completed_tasks} 完成 | {metrics.failed_tasks} 失败")
        lines.append(f"  平均负载: {metrics.avg_load:.1%}")
        lines.append(f"  成功率: {metrics.avg_success_rate:.1%}")
        lines.append("")
        
        # Agent状态
        lines.append("🔧 Agent状态")
        lines.append("-" * 40)
        if agents:
            for agent in sorted(agents.values(), key=lambda a: a.name):
                status_icon = {
                    "idle": "💤",
                    "busy": "⚡",
                    "offline": "❌",
                    "error": "⚠️"
                }.get(agent.status, "❓")
                
                task_info = f" → {agent.current_task[:20]}..." if agent.current_task else ""
                load_bar = "█" * int(agent.load * 10) + "░" * (10 - int(agent.load * 10))
                
                lines.append(f"  {status_icon} {agent.name}: {agent.status}{task_info}")
                lines.append(f"     负载: [{load_bar}] {agent.load:.0%} | 成功率: {agent.success_rate:.0%} | 完成任务: {agent.tasks_completed}")
        else:
            lines.append("  (暂无Agent)")
        lines.append("")
        
        # 任务队列
        lines.append("📋 任务队列")
        lines.append("-" * 40)
        pending = tasks.get("pending", [])
        if pending:
            for task in sorted(pending, key=lambda t: -t.priority)[:5]:
                priority_icon = {1: "⬇", 2: "▬", 3: "⬆", 4: "🔥"}.get(task.priority, "▬")
                lines.append(f"  {priority_icon} [{task.priority}] {task.name} ({task.task_id})")
        else:
            lines.append("  (无待处理任务)")
        
        running = tasks.get("running", [])
        if running:
            lines.append("")
            lines.append("  ⚡ 运行中:")
            for task in running[:5]:
                agent_name = ""
                if task.assigned_agent and task.assigned_agent in agents:
                    agent_name = f" @ {agents[task.assigned_agent].name}"
                lines.append(f"    → {task.name}{agent_name}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def render_html(self) -> str:
        """渲染HTML视图"""
        agents = self.store.get_agents()
        tasks = self.store.get_tasks()
        metrics = self.compute_metrics()
        
        # Agent卡片HTML
        agent_cards = ""
        for agent in agents.values():
            status_color = {
                "idle": "#4CAF50",
                "busy": "#2196F3", 
                "offline": "#9E9E9E",
                "error": "#F44336"
            }.get(agent.status, "#9E9E9E")
            
            load_width = int(agent.load * 100)
            
            agent_cards += f"""
            <div class="agent-card">
                <div class="agent-header">
                    <span class="agent-name">{agent.name}</span>
                    <span class="agent-status" style="background: {status_color}">{agent.status}</span>
                </div>
                <div class="agent-load">
                    <div class="load-bar" style="width: {load_width}%"></div>
                </div>
                <div class="agent-stats">
                    <span>成功率: {agent.success_rate:.0%}</span>
                    <span>任务: {agent.tasks_completed}</span>
                </div>
                {f'<div class="current-task">{agent.current_task}</div>' if agent.current_task else ''}
            </div>
            """
        
        # 任务列表HTML
        pending_tasks = ""
        for task in tasks.get("pending", []):
            priority_color = {1: "#9E9E9E", 2: "#4CAF50", 3: "#FF9800", 4: "#F44336"}.get(task.priority, "#9E9E9E")
            pending_tasks += f"""
            <div class="task-item" style="border-left: 3px solid {priority_color}">
                <span class="task-name">{task.name}</span>
                <span class="task-priority">P{task.priority}</span>
            </div>
            """
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Agent协作网络仪表盘</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; color: #00d4ff; }}
        .timestamp {{ color: #888; font-size: 14px; }}
        
        .metrics-grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
            gap: 15px; margin-bottom: 30px; 
        }}
        .metric-card {{
            background: #16213e; padding: 20px; border-radius: 10px; text-align: center;
            border: 1px solid #0f3460;
        }}
        .metric-value {{ font-size: 32px; font-weight: bold; color: #00d4ff; }}
        .metric-label {{ color: #888; font-size: 14px; margin-top: 5px; }}
        
        .section-title {{ color: #00d4ff; border-bottom: 1px solid #0f3460; padding-bottom: 10px; margin-bottom: 20px; }}
        
        .agents-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; margin-bottom: 30px;
        }}
        .agent-card {{ background: #16213e; border-radius: 10px; padding: 15px; border: 1px solid #0f3460; }}
        .agent-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .agent-name {{ font-weight: bold; color: #fff; }}
        .agent-status {{ padding: 3px 10px; border-radius: 12px; font-size: 12px; color: #fff; }}
        .agent-load {{ height: 6px; background: #0f3460; border-radius: 3px; margin-bottom: 10px; }}
        .load-bar {{ height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); border-radius: 3px; }}
        .agent-stats {{ display: flex; justify-content: space-between; color: #888; font-size: 12px; }}
        .current-task {{ margin-top: 10px; padding: 8px; background: #0f3460; border-radius: 5px; font-size: 12px; color: #aaa; }}
        
        .task-list {{ background: #16213e; border-radius: 10px; padding: 15px; border: 1px solid #0f3460; }}
        .task-item {{ padding: 10px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #0f3460; }}
        .task-item:last-child {{ border-bottom: none; }}
        .task-priority {{ background: #0f3460; padding: 2px 8px; border-radius: 8px; font-size: 12px; }}
        
        .gauge {{ 
            width: 120px; height: 60px; position: relative; overflow: hidden; margin: 0 auto;
        }}
        .gauge-bg {{ 
            width: 120px; height: 120px; border-radius: 50%; background: conic-gradient(#00d4ff 0%, #00ff88 100%); 
            position: absolute; top: 0; left: 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Agent协作网络仪表盘</h1>
        <div class="timestamp">更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-value">{metrics.active_agents}</div>
            <div class="metric-label">在线Agents</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{metrics.total_agents}</div>
            <div class="metric-label">总Agents</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{metrics.running_tasks}</div>
            <div class="metric-label">运行中</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{metrics.pending_tasks}</div>
            <div class="metric-label">待处理</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{metrics.avg_load:.0%}</div>
            <div class="metric-label">平均负载</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{metrics.avg_success_rate:.0%}</div>
            <div class="metric-label">成功率</div>
        </div>
    </div>
    
    <h2 class="section-title">🔧 Agent状态</h2>
    <div class="agents-grid">
        {agent_cards or '<div style="color:#888">暂无Agent</div>'}
    </div>
    
    <h2 class="section-title">📋 待处理任务</h2>
    <div class="task-list">
        {pending_tasks or '<div style="color:#888">无待处理任务</div>'}
    </div>
</body>
</html>
"""
        return html
    
    def render_json(self) -> str:
        """渲染JSON视图"""
        agents = self.store.get_agents()
        tasks = self.store.get_tasks()
        metrics = self.compute_metrics()
        
        return json.dumps({
            "timestamp": datetime.now().isoformat(),
            "metrics": asdict(metrics),
            "agents": {k: asdict(v) for k, v in agents.items()},
            "tasks": {k: [asdict(t) for t in v] for k, v in tasks.items()}
        }, indent=2, ensure_ascii=False)


# CLI接口
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent协作网络可视化仪表盘")
    parser.add_argument("--register", nargs=3, metavar=("AGENT_ID", "NAME", "CAPS"), 
                       help="注册Agent (id name capability1,capability2)")
    parser.add_argument("--status", action="store_true", help="显示状态")
    parser.add_argument("--html", action="store_true", help="生成HTML报告")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    parser.add_argument("--task-add", nargs=2, metavar=("TASK_ID", "NAME"), help="添加任务")
    parser.add_argument("--task-assign", nargs=2, metavar=("TASK_ID", "AGENT_ID"), help="分配任务")
    parser.add_argument("--task-complete", nargs=2, metavar=("TASK_ID", "SUCCESS"), help="完成任务 (true/false)")
    parser.add_argument("--agent-heartbeat", metavar="AGENT_ID", help="Agent心跳")
    parser.add_argument("--agent-load", nargs=2, metavar=("AGENT_ID", "LOAD"), type=float, help="更新Agent负载")
    parser.add_argument("--out", help="输出文件路径")
    
    args = parser.parse_args()
    
    dashboard = CollabDashboard()
    
    if args.register:
        agent_id, name, caps = args.register
        capabilities = caps.split(",") if "," in caps else [caps]
        dashboard.register_agent(agent_id, name, capabilities)
        print(f"✓ Agent注册成功: {name} ({agent_id})")
    
    elif args.agent_heartbeat:
        dashboard.heartbeat(args.agent_heartbeat)
        print(f"✓ 心跳: {args.agent_heartbeat}")
    
    elif args.agent_load:
        agent_id, load = args.agent_load
        dashboard.update_agent_status(agent_id, "busy", load=load)
        print(f"✓ 负载更新: {agent_id} = {load}")
    
    elif args.task_add:
        task_id, name = args.task_add
        dashboard.submit_task(task_id, name)
        print(f"✓ 任务添加: {name} ({task_id})")
    
    elif args.task_assign:
        task_id, agent_id = args.task_assign
        dashboard.assign_task(task_id, agent_id)
        print(f"✓ 任务分配: {task_id} → {agent_id}")
    
    elif args.task_complete:
        task_id, success = args.task_complete
        dashboard.complete_task(task_id, success.lower() == "true")
        print(f"✓ 任务完成: {task_id} ({success})")
    
    elif args.html:
        output = dashboard.render_html()
        if args.out:
            with open(args.out, 'w') as f:
                f.write(output)
            print(f"✓ HTML报告已保存: {args.out}")
        else:
            print(output)
    
    elif args.json:
        output = dashboard.render_json()
        if args.out:
            with open(args.out, 'w') as f:
                f.write(output)
            print(f"✓ JSON已保存: {args.out}")
        else:
            print(output)
    
    elif args.status:
        print(dashboard.render_console())
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()