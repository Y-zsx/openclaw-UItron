#!/usr/bin/env python3
"""
Agent Monitor & Metrics Collection System - 增强版
第41世: 实现Agent监控与指标收集系统
功能:
- 实时Agent状态监控
- 性能指标收集与分析
- 历史数据存储与趋势分析
- 告警与通知
- API服务 (端口18098)
"""
import json
import time
import os
import sys
import psutil
import threading
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from functools import wraps
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('/root/.openclaw/workspace/ultron/logs/agent_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AgentMonitor')

# 数据库路径
DB_PATH = Path(__file__).parent / "data" / "agent_monitor.db"
DB_PATH.parent.mkdir(exist_ok=True)


@dataclass
class AgentSnapshot:
    """Agent快照数据"""
    agent_id: str
    agent_name: str
    status: str
    cpu_usage: float
    memory_usage: float
    tasks_total: int
    tasks_success: int
    tasks_failed: int
    avg_response_time: float
    last_task_time: Optional[str]
    registered_at: Optional[str]
    updated_at: str


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Agent注册表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                status TEXT DEFAULT 'offline',
                registered_at TEXT NOT NULL,
                last_seen TEXT,
                metadata TEXT
            )
        ''')
        
        # 指标历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                cpu_usage REAL,
                memory_usage REAL,
                tasks_total INTEGER,
                tasks_success INTEGER,
                tasks_failed INTEGER,
                success_rate REAL,
                avg_response_time REAL,
                status TEXT,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            )
        ''')
        
        # 告警表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                alert_type TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT,
                value REAL,
                threshold REAL,
                resolved INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
        ''')
        
        # 任务记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                task_id TEXT,
                success INTEGER NOT NULL,
                response_time REAL,
                error_message TEXT,
                executed_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_agent ON metrics_history(agent_id, recorded_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_agent ON task_records(agent_id, executed_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_agent ON alerts(agent_id, created_at)')
        
        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    def execute(self, query: str, params: tuple = ()):
        """执行SQL"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        result = cursor.lastrowid
        conn.close()
        return result
    
    def fetch_all(self, query: str, params: tuple = ()) -> List:
        """查询多条"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        conn.close()
        return result
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional:
        """查询单条"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        return result


class AgentMonitor:
    """Agent监控器"""
    
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
        
        self.db = DatabaseManager()
        self.agents: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        
        # 阈值配置
        self.thresholds = {
            "success_rate_min": 80.0,
            "response_time_max": 5000,
            "cpu_max": 90.0,
            "memory_max": 90.0,
            "error_rate_max": 20.0,
            "idle_timeout": 300
        }
        
        # 告警回调
        self.alert_callbacks: List[Callable] = []
        
        # 启动后台收集
        self._snapshot_interval = 60  # 每60秒收集一次
        self._running = False
        self._collect_thread = None
        
        # 加载现有agents
        self._load_agents()
        
        logger.info("AgentMonitor 初始化完成")
    
    def _load_agents(self):
        """从数据库加载已注册的Agent"""
        rows = self.db.fetch_all("SELECT agent_id, agent_name, status, registered_at, last_seen FROM agents")
        for row in rows:
            self.agents[row[0]] = {
                "agent_id": row[0],
                "agent_name": row[1],
                "status": row[2],
                "registered_at": row[3],
                "last_seen": row[4],
                "tasks_total": 0,
                "tasks_success": 0,
                "tasks_failed": 0,
                "total_response_time": 0.0,
                "cpu_usage": 0.0,
                "memory_usage": 0.0
            }
        logger.info(f"已加载 {len(self.agents)} 个Agent")
    
    def register_agent(self, agent_id: str, agent_name: str, metadata: Dict = None) -> bool:
        """注册新Agent"""
        with self.lock:
            if agent_id in self.agents:
                logger.warning(f"Agent {agent_id} 已注册")
                return False
            
            now = datetime.now().isoformat()
            self.agents[agent_id] = {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "status": "online",
                "registered_at": now,
                "last_seen": now,
                "tasks_total": 0,
                "tasks_success": 0,
                "tasks_failed": 0,
                "total_response_time": 0.0,
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "metadata": metadata or {}
            }
            
            # 写入数据库
            self.db.execute(
                "INSERT INTO agents (agent_id, agent_name, status, registered_at, last_seen, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (agent_id, agent_name, "online", now, now, json.dumps(metadata or {}))
            )
            
            logger.info(f"注册Agent: {agent_name} ({agent_id})")
            return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        with self.lock:
            if agent_id not in self.agents:
                return False
            
            del self.agents[agent_id]
            self.db.execute("UPDATE agents SET status = 'offline' WHERE agent_id = ?", (agent_id,))
            logger.info(f"注销Agent: {agent_id}")
            return True
    
    def update_status(self, agent_id: str, status: str):
        """更新Agent状态"""
        with self.lock:
            if agent_id in self.agents:
                self.agents[agent_id]["status"] = status
                self.agents[agent_id]["last_seen"] = datetime.now().isoformat()
                self.db.execute(
                    "UPDATE agents SET status = ?, last_seen = ? WHERE agent_id = ?",
                    (status, datetime.now().isoformat(), agent_id)
                )
    
    def record_task(self, agent_id: str, success: bool, response_time: float, error: str = None, task_id: str = None):
        """记录任务执行"""
        with self.lock:
            if agent_id not in self.agents:
                self.register_agent(agent_id, agent_id)
            
            agent = self.agents[agent_id]
            agent["tasks_total"] += 1
            agent["last_seen"] = datetime.now().isoformat()
            
            if success:
                agent["tasks_success"] += 1
            else:
                agent["tasks_failed"] += 1
            
            agent["total_response_time"] += response_time
            
            # 记录到数据库
            now = datetime.now().isoformat()
            self.db.execute(
                "INSERT INTO task_records (agent_id, task_id, success, response_time, error_message, executed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (agent_id, task_id, 1 if success else 0, response_time, error, now)
            )
            
            # 检查告警
            self._check_and_alert(agent)
    
    def update_resources(self, agent_id: str, cpu: float = None, memory: float = None):
        """更新资源使用"""
        with self.lock:
            if agent_id in self.agents:
                if cpu is not None:
                    self.agents[agent_id]["cpu_usage"] = cpu
                if memory is not None:
                    self.agents[agent_id]["memory_usage"] = memory
                self.agents[agent_id]["last_seen"] = datetime.now().isoformat()
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取Agent详情"""
        with self.lock:
            return self.agents.get(agent_id)
    
    def get_all_agents(self) -> List[Dict]:
        """获取所有Agent"""
        with self.lock:
            return list(self.agents.values())
    
    def get_summary(self) -> Dict:
        """获取汇总统计"""
        with self.lock:
            total_tasks = sum(a["tasks_total"] for a in self.agents.values())
            total_success = sum(a["tasks_success"] for a in self.agents.values())
            total_failed = sum(a["tasks_failed"] for a in self.agents.values())
            
            status_counts = defaultdict(int)
            for a in self.agents.values():
                status_counts[a["status"]] += 1
            
            avg_cpu = sum(a["cpu_usage"] for a in self.agents.values()) / len(self.agents) if self.agents else 0
            avg_memory = sum(a["memory_usage"] for a in self.agents.values()) / len(self.agents) if self.agents else 0
            
            return {
                "total_agents": len(self.agents),
                "online_agents": status_counts.get("online", 0),
                "busy_agents": status_counts.get("busy", 0),
                "idle_agents": status_counts.get("idle", 0),
                "offline_agents": status_counts.get("offline", 0),
                "total_tasks": total_tasks,
                "total_success": total_success,
                "total_failed": total_failed,
                "success_rate": round(total_success / total_tasks * 100, 2) if total_tasks > 0 else 100.0,
                "avg_cpu": round(avg_cpu, 2),
                "avg_memory": round(avg_memory, 2),
                "status_distribution": dict(status_counts),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_agent_stats(self, agent_id: str) -> Optional[Dict]:
        """获取Agent统计"""
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        tasks = agent["tasks_total"]
        success = agent["tasks_success"]
        failed = agent["tasks_failed"]
        
        return {
            "agent_id": agent_id,
            "agent_name": agent["agent_name"],
            "tasks_total": tasks,
            "tasks_success": success,
            "tasks_failed": failed,
            "success_rate": round(success / tasks * 100, 2) if tasks > 0 else 100.0,
            "avg_response_time": round(agent["total_response_time"] / success, 2) if success > 0 else 0,
            "uptime_seconds": (datetime.now() - datetime.fromisoformat(agent["registered_at"])).total_seconds()
        }
    
    def collect_snapshot(self) -> Dict:
        """收集当前快照"""
        with self.lock:
            now = datetime.now().isoformat()
            snapshot = {
                "timestamp": now,
                "summary": self.get_summary(),
                "agents": []
            }
            
            for agent_id, agent in self.agents.items():
                tasks = agent["tasks_total"]
                success = agent["tasks_success"]
                
                agent_data = {
                    "agent_id": agent_id,
                    "agent_name": agent["agent_name"],
                    "status": agent["status"],
                    "cpu_usage": agent["cpu_usage"],
                    "memory_usage": agent["memory_usage"],
                    "tasks_total": tasks,
                    "tasks_success": success,
                    "tasks_failed": agent["tasks_failed"],
                    "success_rate": round(success / tasks * 100, 2) if tasks > 0 else 100.0,
                    "avg_response_time": round(agent["total_response_time"] / success, 2) if success > 0 else 0,
                    "last_seen": agent["last_seen"]
                }
                
                snapshot["agents"].append(agent_data)
                
                # 写入历史
                self.db.execute(
                    '''INSERT INTO metrics_history 
                       (agent_id, cpu_usage, memory_usage, tasks_total, tasks_success, tasks_failed, success_rate, avg_response_time, status, recorded_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (agent_id, agent["cpu_usage"], agent["memory_usage"], tasks, success, agent["tasks_failed"],
                     agent_data["success_rate"], agent_data["avg_response_time"], agent["status"], now)
                )
            
            return snapshot
    
    def get_history(self, agent_id: str, minutes: int = 60) -> List[Dict]:
        """获取历史指标"""
        since = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        rows = self.db.fetch_all(
            '''SELECT cpu_usage, memory_usage, tasks_total, tasks_success, success_rate, avg_response_time, status, recorded_at
               FROM metrics_history WHERE agent_id = ? AND recorded_at > ? ORDER BY recorded_at DESC''',
            (agent_id, since)
        )
        return [
            {
                "cpu_usage": r[0],
                "memory_usage": r[1],
                "tasks_total": r[2],
                "tasks_success": r[3],
                "success_rate": r[4],
                "avg_response_time": r[5],
                "status": r[6],
                "recorded_at": r[7]
            }
            for r in rows
        ]
    
    def get_trends(self, agent_id: str) -> Dict:
        """分析趋势"""
        history = self.get_history(agent_id, 60)
        if len(history) < 2:
            return {"trend": "insufficient_data", "message": "数据不足"}
        
        recent = history[:10]
        older = history[10:]
        
        if not older:
            return {"trend": "insufficient_data", "message": "历史数据不足"}
        
        def avg(items, key):
            return sum(item.get(key, 0) for item in items) / len(items) if items else 0
        
        return {
            "success_rate_change": round(avg(recent, "success_rate") - avg(older, "success_rate"), 2),
            "response_time_change": round(avg(recent, "avg_response_time") - avg(older, "avg_response_time"), 2),
            "cpu_change": round(avg(recent, "cpu_usage") - avg(older, "cpu_usage"), 2),
            "data_points": len(history)
        }
    
    def check_alerts(self, agent_id: str = None) -> List[Dict]:
        """检查告警"""
        alerts = []
        target_agents = [agent_id] if agent_id else list(self.agents.keys())
        
        for aid in target_agents:
            agent = self.agents.get(aid)
            if not agent:
                continue
            
            tasks = agent["tasks_total"]
            success = agent["tasks_success"]
            success_rate = (success / tasks * 100) if tasks > 0 else 100.0
            error_rate = 100 - success_rate
            avg_response = agent["total_response_time"] / success if success > 0 else 0
            
            # 成功率低
            if success_rate < self.thresholds["success_rate_min"]:
                alerts.append({
                    "agent_id": aid,
                    "agent_name": agent["agent_name"],
                    "type": "success_rate_low",
                    "level": "warning",
                    "message": f"成功率过低: {success_rate}%",
                    "value": success_rate,
                    "threshold": self.thresholds["success_rate_min"]
                })
            
            # 响应时间长
            if avg_response > self.thresholds["response_time_max"]:
                alerts.append({
                    "agent_id": aid,
                    "agent_name": agent["agent_name"],
                    "type": "response_time_high",
                    "level": "warning",
                    "message": f"响应时间过长: {avg_response}ms",
                    "value": avg_response,
                    "threshold": self.thresholds["response_time_max"]
                })
            
            # CPU高
            if agent["cpu_usage"] > self.thresholds["cpu_max"]:
                alerts.append({
                    "agent_id": aid,
                    "agent_name": agent["agent_name"],
                    "type": "cpu_high",
                    "level": "critical",
                    "message": f"CPU使用率过高: {agent['cpu_usage']}%",
                    "value": agent["cpu_usage"],
                    "threshold": self.thresholds["cpu_max"]
                })
            
            # 内存高
            if agent["memory_usage"] > self.thresholds["memory_max"]:
                alerts.append({
                    "agent_id": aid,
                    "agent_name": agent["agent_name"],
                    "type": "memory_high",
                    "level": "critical",
                    "message": f"内存使用率过高: {agent['memory_usage']}%",
                    "value": agent["memory_usage"],
                    "threshold": self.thresholds["memory_max"]
                })
            
            # 离线
            if agent["status"] == "offline":
                alerts.append({
                    "agent_id": aid,
                    "agent_name": agent["agent_name"],
                    "type": "agent_offline",
                    "level": "critical",
                    "message": "Agent已离线",
                    "value": "offline",
                    "threshold": "online"
                })
            
            # 长时间无活动
            if agent["last_seen"]:
                last_seen = datetime.fromisoformat(agent["last_seen"])
                idle = (datetime.now() - last_seen).total_seconds()
                if idle > self.thresholds["idle_timeout"] and agent["status"] in ["idle", "online"]:
                    alerts.append({
                        "agent_id": aid,
                        "agent_name": agent["agent_name"],
                        "type": "agent_idle",
                        "level": "info",
                        "message": f"长时间无活动: {int(idle)}s",
                        "value": idle,
                        "threshold": self.thresholds["idle_timeout"]
                    })
        
        return alerts
    
    def get_unresolved_alerts(self) -> List[Dict]:
        """获取未解决的告警"""
        rows = self.db.fetch_all(
            "SELECT id, agent_id, alert_type, level, message, value, threshold, created_at FROM alerts WHERE resolved = 0 ORDER BY created_at DESC"
        )
        return [
            {
                "id": r[0],
                "agent_id": r[1],
                "type": r[2],
                "level": r[3],
                "message": r[4],
                "value": r[5],
                "threshold": r[6],
                "created_at": r[7]
            }
            for r in rows
        ]
    
    def resolve_alert(self, alert_id: int) -> bool:
        """解决告警"""
        self.db.execute(
            "UPDATE alerts SET resolved = 1, resolved_at = ? WHERE id = ?",
            (datetime.now().isoformat(), alert_id)
        )
        return True
    
    def set_thresholds(self, **kwargs):
        """设置阈值"""
        self.thresholds.update(kwargs)
        logger.info(f"阈值已更新: {self.thresholds}")
    
    def start_background_collection(self):
        """启动后台收集"""
        if self._running:
            return
        
        self._running = True
        self._collect_thread = threading.Thread(target=self._background_collect, daemon=True)
        self._collect_thread.start()
        logger.info("后台收集已启动")
    
    def stop_background_collection(self):
        """停止后台收集"""
        self._running = False
        if self._collect_thread:
            self._collect_thread.join(timeout=5)
        logger.info("后台收集已停止")
    
    def _background_collect(self):
        """后台收集循环"""
        while self._running:
            try:
                self.collect_snapshot()
            except Exception as e:
                logger.error(f"快照收集失败: {e}")
            time.sleep(self._snapshot_interval)
    
    def _check_and_alert(self, agent: Dict):
        """检查并生成告警"""
        tasks = agent["tasks_total"]
        success = agent["tasks_success"]
        success_rate = (success / tasks * 100) if tasks > 0 else 100.0
        
        if success_rate < self.thresholds["success_rate_min"]:
            self.db.execute(
                "INSERT INTO alerts (agent_id, alert_type, level, message, value, threshold, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agent["agent_id"], "success_rate_low", "warning", f"成功率过低: {success_rate}%", success_rate, self.thresholds["success_rate_min"], datetime.now().isoformat())
            )


def get_monitor() -> AgentMonitor:
    """获取监控器实例"""
    return AgentMonitor()


# 测试
if __name__ == "__main__":
    monitor = AgentMonitor()
    
    # 注册测试Agent
    monitor.register_agent("agent_001", "WebScraper", {"type": "worker"})
    monitor.register_agent("agent_002", "DataProcessor", {"type": "processor"})
    monitor.register_agent("agent_003", "MLEngine", {"type": "ml"})
    
    # 模拟任务
    monitor.record_task("agent_001", True, 120.5, task_id="task_001")
    monitor.record_task("agent_001", True, 98.2, task_id="task_002")
    monitor.record_task("agent_001", False, 2000.0, error="Timeout", task_id="task_003")
    monitor.record_task("agent_002", True, 500.0)
    monitor.record_task("agent_003", True, 1500.0)
    
    monitor.update_status("agent_001", "busy")
    monitor.update_resources("agent_001", 45.5, 62.3)
    
    # 输出汇总
    summary = monitor.get_summary()
    print(f"\n=== 监控汇总 ===")
    print(f"总Agent: {summary['total_agents']}")
    print(f"在线: {summary['online_agents']}, 忙碌: {summary['busy_agents']}, 空闲: {summary['idle_agents']}")
    print(f"总任务: {summary['total_tasks']}, 成功率: {summary['success_rate']}%")
    print(f"平均CPU: {summary['avg_cpu']}%, 平均内存: {summary['avg_memory']}%")
    
    # 快照
    snapshot = monitor.collect_snapshot()
    print(f"\n=== 快照已收集: {len(snapshot['agents'])} agents ===")
    
    # 告警
    alerts = monitor.check_alerts()
    print(f"\n=== 告警检查: {len(alerts)} ===")
    for a in alerts:
        print(f"[{a['level']}] {a['agent_name']}: {a['message']}")
    
    print("\n测试完成!")