#!/usr/bin/env python3
"""
故障预测与预防性维护系统
Agent Service Fault Prediction and Preventive Maintenance

功能:
1. 故障预测 - 基于历史数据预测潜在故障
2. 预防性维护 - 自动执行维护任务防止故障
3. 异常检测 - 实时检测异常模式
4. 健康评分 - 服务健康状况评分
"""

import asyncio
import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import statistics

# ============ 配置 ============
DATA_DIR = Path("/root/.openclaw/workspace/ultron/data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "fault_prediction.db"

# 预测阈值配置
CONFIG = {
    "cpu_warning": 70.0,       # CPU警告阈值%
    "cpu_critical": 85.0,      # CPU危险阈值%
    "memory_warning": 75.0,    # 内存警告阈值%
    "memory_critical": 90.0,   # 内存危险阈值%
    "error_rate_warning": 5.0, # 错误率警告阈值%
    "error_rate_critical": 15.0, # 错误率危险阈值%
    "response_time_warning": 1000,  # 响应时间警告(ms)
    "response_time_critical": 3000, # 响应时间危险(ms)
    "prediction_window": 30,   # 预测时间窗口(分钟)
    "history_retention": 30,   # 历史数据保留天数
    "maintenance_interval": 3600, # 维护检查间隔(秒)
}

# ============ 数据模型 ============
@dataclass
class ServiceMetrics:
    """服务指标数据"""
    timestamp: float
    service_name: str
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    error_rate: float = 0.0
    response_time: float = 0.0
    request_count: int = 0
    active_connections: int = 0

@dataclass
class FaultPrediction:
    """故障预测结果"""
    service_name: str
    prediction_type: str  # cpu/memory/error_rate/response_time/composite
    severity: str  # low/medium/high/critical
    probability: float  # 0-1
    predicted_time: Optional[datetime]
    description: str
    recommended_actions: List[str]
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class MaintenanceTask:
    """维护任务"""
    task_id: str
    service_name: str
    task_type: str  # restart/cleanup/scale/backup/check
    description: str
    scheduled_at: datetime
    status: str  # pending/running/completed/failed
    result: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

# ============ 数据库管理 ============
class FaultPredictionDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 服务指标历史
            conn.execute("""
                CREATE TABLE IF NOT EXISTS service_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    service_name TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    error_rate REAL,
                    response_time REAL,
                    request_count INTEGER,
                    active_connections INTEGER
                )
            """)
            
            # 故障预测记录
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fault_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT NOT NULL,
                    prediction_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    probability REAL,
                    predicted_time TEXT,
                    description TEXT,
                    recommended_actions TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # 维护任务记录
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_tasks (
                    task_id TEXT PRIMARY KEY,
                    service_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    description TEXT,
                    scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # 服务健康评分
            conn.execute("""
                CREATE TABLE IF NOT EXISTS service_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT NOT NULL,
                    health_score REAL NOT NULL,
                    factors TEXT,
                    checked_at TEXT NOT NULL
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_time ON service_metrics(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_service ON service_metrics(service_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_predictions_service ON fault_predictions(service_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON maintenance_tasks(status)")
            
            conn.commit()
    
    def save_metrics(self, metrics: ServiceMetrics):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO service_metrics 
                (timestamp, service_name, cpu_percent, memory_percent, error_rate, response_time, request_count, active_connections)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (metrics.timestamp, metrics.service_name, metrics.cpu_percent, metrics.memory_percent,
                  metrics.error_rate, metrics.response_time, metrics.request_count, metrics.active_connections))
            conn.commit()
    
    def get_recent_metrics(self, service_name: str, minutes: int = 60) -> List[ServiceMetrics]:
        cutoff = time.time() - (minutes * 60)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM service_metrics 
                WHERE service_name = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (service_name, cutoff)).fetchall()
        
        return [ServiceMetrics(
            timestamp=r["timestamp"],
            service_name=r["service_name"],
            cpu_percent=r["cpu_percent"],
            memory_percent=r["memory_percent"],
            error_rate=r["error_rate"],
            response_time=r["response_time"],
            request_count=r["request_count"],
            active_connections=r["active_connections"]
        ) for r in rows]
    
    def save_prediction(self, prediction: FaultPrediction):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO fault_predictions
                (service_name, prediction_type, severity, probability, predicted_time, description, recommended_actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (prediction.service_name, prediction.prediction_type, prediction.severity,
                  prediction.probability, prediction.predicted_time.isoformat() if prediction.predicted_time else None,
                  prediction.description, json.dumps(prediction.recommended_actions), prediction.created_at.isoformat()))
            conn.commit()
    
    def save_maintenance_task(self, task: MaintenanceTask):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO maintenance_tasks
                (task_id, service_name, task_type, description, scheduled_at, status, result, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (task.task_id, task.service_name, task.task_type, task.description,
                  task.scheduled_at.isoformat(), task.status, task.result, task.created_at.isoformat()))
            conn.commit()
    
    def get_pending_tasks(self) -> List[MaintenanceTask]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Get all pending tasks (regardless of scheduled time for display)
            rows = conn.execute("""
                SELECT * FROM maintenance_tasks 
                WHERE status = 'pending'
                ORDER BY scheduled_at
            """).fetchall()
        
        return [MaintenanceTask(
            task_id=r["task_id"],
            service_name=r["service_name"],
            task_type=r["task_type"],
            description=r["description"],
            scheduled_at=datetime.fromisoformat(r["scheduled_at"]),
            status=r["status"],
            result=r["result"],
            created_at=datetime.fromisoformat(r["created_at"])
        ) for r in rows]
    
    def update_task_status(self, task_id: str, status: str, result: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE maintenance_tasks SET status = ?, result = ? WHERE task_id = ?
            """, (status, result, task_id))
            conn.commit()
    
    def save_health_score(self, service_name: str, score: float, factors: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO service_health (service_name, health_score, factors, checked_at)
                VALUES (?, ?, ?, ?)
            """, (service_name, score, json.dumps(factors), datetime.now().isoformat()))
            conn.commit()
    
    def get_health_history(self, service_name: str, hours: int = 24) -> List[Dict]:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM service_health 
                WHERE service_name = ? AND checked_at > ?
                ORDER BY checked_at DESC
            """, (service_name, cutoff)).fetchall()
        return [dict(r) for r in rows]


# ============ 预测引擎 ============
class PredictionEngine:
    """基于历史数据的故障预测引擎"""
    
    def __init__(self, db: FaultPredictionDB):
        self.db = db
    
    def analyze_trend(self, values: List[float], window: int = 5) -> str:
        """分析趋势 - 上升/下降/稳定"""
        if len(values) < window:
            return "unknown"
        
        recent = values[:window]
        older = values[window:window*2] if len(values) >= window*2 else values
        
        if not older:
            return "unknown"
        
        recent_avg = statistics.mean(recent)
        older_avg = statistics.mean(older)
        
        change_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        
        if change_pct > 10:
            return "rising"
        elif change_pct < -10:
            return "falling"
        return "stable"
    
    def calculate_probability(self, current: float, threshold: float, trend: str) -> float:
        """计算故障概率"""
        if trend == "rising":
            proximity = min(current / threshold, 1.5)
            return min(proximity * 0.7 + 0.3, 1.0)
        elif trend == "stable":
            proximity = min(current / threshold, 1.2)
            return min(proximity * 0.5, 1.0)
        else:
            return max(0.1, (current / threshold) * 0.3)
    
    def predict_cpu_failure(self, metrics: List[ServiceMetrics]) -> Optional[FaultPrediction]:
        """预测CPU故障"""
        if not metrics:
            return None
        
        # metrics are ordered newest first from get_recent_metrics
        # We need to check current (newest) value
        cpu_values = [m.cpu_percent for m in metrics]
        trend = self.analyze_trend(cpu_values)
        current_cpu = cpu_values[0] if cpu_values else 0  # newest value
        
        if trend == "rising" and current_cpu > CONFIG["cpu_warning"]:
            probability = self.calculate_probability(current_cpu, CONFIG["cpu_critical"], trend)
            severity = "critical" if probability > 0.8 else "high" if probability > 0.6 else "medium"
            
            return FaultPrediction(
                service_name=metrics[0].service_name,
                prediction_type="cpu",
                severity=severity,
                probability=probability,
                predicted_time=datetime.now() + timedelta(minutes=CONFIG["prediction_window"]),
                description=f"CPU使用率持续上升，当前{current_cpu:.1f}%，趋势{trend}",
                recommended_actions=[
                    "增加CPU资源或扩容",
                    "优化高CPU占用进程",
                    "检查是否存在异常计算任务"
                ]
            )
        return None
    
    def predict_memory_failure(self, metrics: List[ServiceMetrics]) -> Optional[FaultPrediction]:
        """预测内存故障"""
        if not metrics:
            return None
        
        # metrics ordered newest first
        memory_values = [m.memory_percent for m in metrics]
        trend = self.analyze_trend(memory_values)
        current_mem = memory_values[0] if memory_values else 0
        
        if trend == "rising" and current_mem > CONFIG["memory_warning"]:
            probability = self.calculate_probability(current_mem, CONFIG["memory_critical"], trend)
            severity = "critical" if probability > 0.8 else "high" if probability > 0.6 else "medium"
            
            return FaultPrediction(
                service_name=metrics[0].service_name,
                prediction_type="memory",
                severity=severity,
                probability=probability,
                predicted_time=datetime.now() + timedelta(minutes=CONFIG["prediction_window"]),
                description=f"内存使用率持续上升，当前{current_mem:.1f}%，趋势{trend}",
                recommended_actions=[
                    "清理缓存释放内存",
                    "增加内存资源",
                    "检查内存泄漏"
                ]
            )
        return None
    
    def predict_error_rate_failure(self, metrics: List[ServiceMetrics]) -> Optional[FaultPrediction]:
        """预测错误率故障"""
        if not metrics:
            return None
        
        # metrics ordered newest first
        error_values = [m.error_rate for m in metrics]
        trend = self.analyze_trend(error_values)
        current_err = error_values[0] if error_values else 0
        
        if trend == "rising" and current_err > CONFIG["error_rate_warning"]:
            probability = self.calculate_probability(current_err, CONFIG["error_rate_critical"], trend)
            severity = "critical" if probability > 0.8 else "high" if probability > 0.6 else "medium"
            
            return FaultPrediction(
                service_name=metrics[0].service_name,
                prediction_type="error_rate",
                severity=severity,
                probability=probability,
                predicted_time=datetime.now() + timedelta(minutes=CONFIG["prediction_window"]),
                description=f"错误率持续上升，当前{current_err:.2f}%，趋势{trend}",
                recommended_actions=[
                    "检查日志分析错误原因",
                    "回滚最近变更",
                    "启用熔断保护"
                ]
            )
        return None
    
    def predict_response_time_failure(self, metrics: List[ServiceMetrics]) -> Optional[FaultPrediction]:
        """预测响应时间故障"""
        if not metrics:
            return None
        
        # metrics ordered newest first
        rt_values = [m.response_time for m in metrics]
        trend = self.analyze_trend(rt_values)
        current_rt = rt_values[0] if rt_values else 0
        
        if trend == "rising" and current_rt > CONFIG["response_time_warning"]:
            probability = self.calculate_probability(current_rt, CONFIG["response_time_critical"], trend)
            severity = "critical" if probability > 0.8 else "high" if probability > 0.6 else "medium"
            
            return FaultPrediction(
                service_name=metrics[0].service_name,
                prediction_type="response_time",
                severity=severity,
                probability=probability,
                predicted_time=datetime.now() + timedelta(minutes=CONFIG["prediction_window"]),
                description=f"响应时间持续上升，当前{current_rt:.0f}ms，趋势{trend}",
                recommended_actions=[
                    "检查数据库查询性能",
                    "增加连接池大小",
                    "启用缓存减少响应时间"
                ]
            )
        return None
    
    def predict_composite(self, metrics: List[ServiceMetrics]) -> Optional[FaultPrediction]:
        """综合预测 - 检测多个指标同时恶化"""
        if len(metrics) < 10:
            return None
        
        # metrics ordered newest first
        cpu_values = [m.cpu_percent for m in metrics]
        mem_values = [m.memory_percent for m in metrics]
        err_values = [m.error_rate for m in metrics]
        
        cpu_trend = self.analyze_trend(cpu_values)
        mem_trend = self.analyze_trend(mem_values)
        err_trend = self.analyze_trend(err_values)
        
        # 多指标同时恶化
        worsening = sum([1 for t in [cpu_trend, mem_trend, err_trend] if t == "rising"])
        
        if worsening >= 2:
            severity = "critical" if worsening == 3 else "high"
            
            return FaultPrediction(
                service_name=metrics[0].service_name,
                prediction_type="composite",
                severity=severity,
                probability=0.7 + (worsening * 0.1),
                predicted_time=datetime.now() + timedelta(minutes=CONFIG["prediction_window"] // 2),
                description=f"多指标同时恶化 - CPU:{cpu_trend}, 内存:{mem_trend}, 错误率:{err_trend}",
                recommended_actions=[
                    "立即进行系统检查",
                    "考虑自动扩容",
                    "准备故障转移"
                ]
            )
        return None
    
    def predict_all(self, service_name: str) -> List[FaultPrediction]:
        """对服务进行全量预测"""
        metrics = self.db.get_recent_metrics(service_name, minutes=60)
        if not metrics:
            return []
        
        # metrics are already ordered newest first from get_recent_metrics
        # No reversal needed
        
        predictions = []
        
        # 各项预测
        for pred_fn in [self.predict_cpu_failure, self.predict_memory_failure,
                        self.predict_error_rate_failure, self.predict_response_time_failure]:
            pred = pred_fn(metrics)
            if pred:
                predictions.append(pred)
        
        # 综合预测
        comp_pred = self.predict_composite(metrics)
        if comp_pred:
            predictions.append(comp_pred)
        
        return predictions


# ============ 健康评分引擎 ============
class HealthScoreEngine:
    """服务健康评分引擎"""
    
    def __init__(self, db: FaultPredictionDB):
        self.db = db
    
    def calculate_health_score(self, metrics: List[ServiceMetrics]) -> tuple[float, Dict]:
        """计算健康评分 (0-100)"""
        if not metrics:
            return 50.0, {"error": "No metrics available"}
        
        latest = metrics[0]
        factors = {}
        
        # CPU评分
        if latest.cpu_percent < CONFIG["cpu_warning"]:
            cpu_score = 100
        elif latest.cpu_percent < CONFIG["cpu_critical"]:
            cpu_score = 100 - ((latest.cpu_percent - CONFIG["cpu_warning"]) / 
                              (CONFIG["cpu_critical"] - CONFIG["cpu_warning"]) * 50)
        else:
            cpu_score = 50 - ((latest.cpu_percent - CONFIG["cpu_critical"]) / 10 * 50)
        cpu_score = max(0, min(100, cpu_score))
        factors["cpu"] = {"score": cpu_score, "value": latest.cpu_percent}
        
        # 内存评分
        if latest.memory_percent < CONFIG["memory_warning"]:
            mem_score = 100
        elif latest.memory_percent < CONFIG["memory_critical"]:
            mem_score = 100 - ((latest.memory_percent - CONFIG["memory_warning"]) / 
                              (CONFIG["memory_critical"] - CONFIG["memory_warning"]) * 50)
        else:
            mem_score = 50 - ((latest.memory_percent - CONFIG["memory_critical"]) / 10 * 50)
        mem_score = max(0, min(100, mem_score))
        factors["memory"] = {"score": mem_score, "value": latest.memory_percent}
        
        # 错误率评分
        if latest.error_rate < CONFIG["error_rate_warning"]:
            err_score = 100
        elif latest.error_rate < CONFIG["error_rate_critical"]:
            err_score = 100 - ((latest.error_rate - CONFIG["error_rate_warning"]) / 
                              (CONFIG["error_rate_critical"] - CONFIG["error_rate_warning"]) * 50)
        else:
            err_score = max(0, 50 - (latest.error_rate - CONFIG["error_rate_critical"]) * 10)
        factors["error_rate"] = {"score": err_score, "value": latest.error_rate}
        
        # 响应时间评分
        if latest.response_time < CONFIG["response_time_warning"]:
            rt_score = 100
        elif latest.response_time < CONFIG["response_time_critical"]:
            rt_score = 100 - ((latest.response_time - CONFIG["response_time_warning"]) / 
                             (CONFIG["response_time_critical"] - CONFIG["response_time_warning"]) * 50)
        else:
            rt_score = max(0, 50 - (latest.response_time - CONFIG["response_time_critical"]) / 100)
        factors["response_time"] = {"score": rt_score, "value": latest.response_time}
        
        # 综合评分
        weights = {"cpu": 0.25, "memory": 0.25, "error_rate": 0.3, "response_time": 0.2}
        health_score = sum(factors[k]["score"] * weights[k] for k in weights)
        
        return health_score, factors


# ============ 预防性维护引擎 ============
class PreventiveMaintenanceEngine:
    """预防性维护引擎"""
    
    def __init__(self, db: FaultPredictionDB):
        self.db = db
        self.maintenance_handlers = {
            "restart": self._restart_service,
            "cleanup": self._cleanup_service,
            "scale": self._scale_service,
            "backup": self._backup_service,
            "check": self._health_check
        }
    
    async def _restart_service(self, service_name: str) -> str:
        """重启服务"""
        import subprocess
        try:
            result = subprocess.run(
                ["systemctl", "restart", service_name],
                capture_output=True, text=True, timeout=30
            )
            return f"Restarted {service_name}: {result.returncode}"
        except Exception as e:
            return f"Failed to restart {service_name}: {e}"
    
    async def _cleanup_service(self, service_name: str) -> str:
        """清理服务缓存/临时文件"""
        import subprocess
        try:
            # 清理日志
            log_dirs = [f"/root/.openclaw/workspace/ultron/logs"]
            for log_dir in log_dirs:
                if Path(log_dir).exists():
                    subprocess.run(f"find {log_dir} -type f -mtime +7 -delete", shell=True)
            return f"Cleaned up for {service_name}"
        except Exception as e:
            return f"Cleanup failed: {e}"
    
    async def _scale_service(self, service_name: str) -> str:
        """扩展服务"""
        # 调用Autoscaler API
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post("http://localhost:18160/scale", 
                    json={"service": service_name, "factor": 1.5}) as resp:
                    result = await resp.json()
                    return f"Scaled {service_name}: {result}"
        except Exception as e:
            return f"Scaling {service_name} failed: {e}"
    
    async def _backup_service(self, service_name: str) -> str:
        """备份服务数据"""
        import subprocess
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"/root/.openclaw/workspace/ultron/data/backups/{service_name}_{timestamp}"
        Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
        
        try:
            subprocess.run(f"cp -r /root/.openclaw/workspace/ultron/data {backup_path}", shell=True)
            return f"Backed up {service_name} to {backup_path}"
        except Exception as e:
            return f"Backup failed: {e}"
    
    async def _health_check(self, service_name: str) -> str:
        """健康检查"""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:18146/health/{service_name}") as resp:
                    result = await resp.json()
                    return f"Health check for {service_name}: {result.get('status', 'unknown')}"
        except Exception as e:
            return f"Health check failed: {e}"
    
    async def execute_task(self, task: MaintenanceTask) -> str:
        """执行维护任务"""
        handler = self.maintenance_handlers.get(task.task_type)
        if not handler:
            return f"Unknown task type: {task.task_type}"
        
        try:
            result = await handler(task.service_name)
            self.db.update_task_status(task.task_id, "completed", result)
            return result
        except Exception as e:
            self.db.update_task_status(task.task_id, "failed", str(e))
            return f"Task failed: {e}"
    
    def schedule_maintenance(self, service_name: str, task_type: str, 
                           description: str, delay_minutes: int = 0) -> MaintenanceTask:
        """调度维护任务"""
        task = MaintenanceTask(
            task_id=f"{service_name}_{task_type}_{int(time.time())}",
            service_name=service_name,
            task_type=task_type,
            description=description,
            scheduled_at=datetime.now() + timedelta(minutes=delay_minutes),
            status="pending"
        )
        self.db.save_maintenance_task(task)
        return task
    
    def create_preventive_tasks(self, predictions: List[FaultPrediction]) -> List[MaintenanceTask]:
        """根据预测自动创建预防性任务"""
        tasks = []
        
        for pred in predictions:
            if pred.probability > 0.7:
                if pred.prediction_type in ["cpu", "memory"]:
                    task = self.schedule_maintenance(
                        pred.service_name, "scale",
                        f"预防性扩容: {pred.description}",
                        delay_minutes=5
                    )
                    tasks.append(task)
                elif pred.prediction_type == "error_rate":
                    task = self.schedule_maintenance(
                        pred.service_name, "check",
                        f"预防性检查: {pred.description}",
                        delay_minutes=2
                    )
                    tasks.append(task)
        
        return tasks


# ============ 主服务 ============
class FaultPredictionService:
    def __init__(self):
        self.db = FaultPredictionDB(DB_PATH)
        self.prediction_engine = PredictionEngine(self.db)
        self.health_engine = HealthScoreEngine(self.db)
        self.maintenance_engine = PreventiveMaintenanceEngine(self.db)
        
        # 已知服务列表
        self.services = [
            "agent-orchestrator", "agent-monitor", "agent-scaling",
            "agent-service-mesh", "agent-orchestration", "agent-deployment",
            "log-aggregator", "health-monitor", "autoscaler", "loadbalancer"
        ]
        
        self._running = False
    
    async def collect_metrics(self):
        """收集服务指标"""
        import aiohttp
        
        for service in self.services:
            try:
                # 尝试从监控系统获取指标
                async with aiohttp.ClientSession() as session:
                    # 尝试多个可能的API端点
                    endpoints = [
                        f"http://localhost:18146/metrics/{service}",
                        f"http://localhost:18141/metrics/{service}",
                        f"http://localhost:18160/status"
                    ]
                    
                    metrics = None
                    for url in endpoints:
                        try:
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    metrics = data
                                    break
                        except:
                            continue
                    
                    if metrics:
                        # 提取指标
                        cpu = metrics.get("cpu_percent", metrics.get("cpu", 0))
                        mem = metrics.get("memory_percent", metrics.get("memory", 0))
                        err = metrics.get("error_rate", 0)
                        rt = metrics.get("response_time", metrics.get("latency", 0))
                        
                        self.db.save_metrics(ServiceMetrics(
                            timestamp=time.time(),
                            service_name=service,
                            cpu_percent=cpu,
                            memory_percent=mem,
                            error_rate=err,
                            response_time=rt,
                            request_count=metrics.get("requests", 0),
                            active_connections=metrics.get("connections", 0)
                        ))
            except Exception as e:
                pass  # 静默跳过收集失败
    
    async def run_predictions(self):
        """运行预测分析"""
        for service in self.services:
            predictions = self.prediction_engine.predict_all(service)
            for pred in predictions:
                self.db.save_prediction(pred)
                
                # 高概率预测自动创建维护任务
                if pred.probability > 0.6:
                    self.maintenance_engine.create_preventive_tasks([pred])
    
    async def calculate_health_scores(self):
        """计算健康评分"""
        for service in self.services:
            metrics = self.db.get_recent_metrics(service, minutes=30)
            if metrics:
                score, factors = self.health_engine.calculate_health_score(metrics)
                self.db.save_health_score(service, score, factors)
    
    async def execute_pending_tasks(self):
        """执行待处理的维护任务"""
        tasks = self.db.get_pending_tasks()
        for task in tasks:
            await self.maintenance_engine.execute_task(task)
    
    async def run_maintenance_cycle(self):
        """运行完整的维护周期"""
        await self.collect_metrics()
        await self.run_predictions()
        await self.calculate_health_scores()
        await self.execute_pending_tasks()
    
    async def start(self):
        """启动服务"""
        self._running = True
        print(f"🔮 Fault Prediction Service started")
        print(f"   Monitoring {len(self.services)} services")
        
        while self._running:
            try:
                await self.run_maintenance_cycle()
            except Exception as e:
                print(f"Error in maintenance cycle: {e}")
            
            await asyncio.sleep(CONFIG["maintenance_interval"])
    
    def stop(self):
        """停止服务"""
        self._running = False


# ============ API服务器 ============
from aiohttp import web

class FaultPredictionAPI:
    def __init__(self, service: FaultPredictionService):
        self.service = service
        self.app = web.Application()
        self._setup_routes()
    
    def _setup_routes(self):
        self.app.router.add_get("/health", self.health)
        self.app.router.add_get("/services", self.list_services)
        self.app.router.add_get("/predict/{service}", self.get_predictions)
        self.app.router.add_get("/healthscore/{service}", self.get_health_score)
        self.app.router.add_get("/maintenance/tasks", self.list_tasks)
        self.app.router.add_post("/maintenance/schedule", self.schedule_task)
        self.app.router.add_post("/collect", self.manual_collect)
    
    async def health(self, request):
        return web.json_response({"status": "ok", "service": "fault-prediction"})
    
    async def list_services(self, request):
        return web.json_response({"services": self.service.services})
    
    async def get_predictions(self, request):
        service = request.match_info["service"]
        predictions = self.service.prediction_engine.predict_all(service)
        
        return web.json_response({
            "service": service,
            "predictions": [{
                "type": p.prediction_type,
                "severity": p.severity,
                "probability": p.probability,
                "predicted_time": p.predicted_time.isoformat() if p.predicted_time else None,
                "description": p.description,
                "recommendations": p.recommended_actions
            } for p in predictions]
        })
    
    async def get_health_score(self, request):
        service = request.match_info["service"]
        metrics = self.service.db.get_recent_metrics(service, minutes=30)
        
        if not metrics:
            return web.json_response({"error": "No metrics available"}, status=404)
        
        score, factors = self.service.health_engine.calculate_health_score(metrics)
        
        return web.json_response({
            "service": service,
            "health_score": score,
            "factors": factors,
            "status": "healthy" if score > 70 else "warning" if score > 50 else "critical"
        })
    
    async def list_tasks(self, request):
        tasks = self.service.db.get_pending_tasks()
        return web.json_response({
            "tasks": [{
                "task_id": t.task_id,
                "service": t.service_name,
                "type": t.task_type,
                "description": t.description,
                "scheduled_at": t.scheduled_at.isoformat()
            } for t in tasks]
        })
    
    async def schedule_task(self, request):
        data = await request.json()
        task = self.service.maintenance_engine.schedule_maintenance(
            data["service"], data["type"], data.get("description", ""),
            data.get("delay_minutes", 0)
        )
        return web.json_response({"task_id": task.task_id, "status": "scheduled"})
    
    async def manual_collect(self, request):
        await self.service.collect_metrics()
        return web.json_response({"status": "collected"})
    
    def run(self, host="0.0.0.0", port=18170):
        # 使用静态run方式避免线程问题
        import threading
        def _run():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            runner = web.AppRunner(self.app)
            loop.run_until_complete(runner.setup())
            site = web.TCPSite(runner, host, port)
            loop.run_until_complete(site.start())
            print(f"✓ Fault Prediction API running on port {port}")
            loop.run_forever()
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread


# ============ 主入口 ============
async def main():
    service = FaultPredictionService()
    api = FaultPredictionAPI(service)
    
    # 启动API服务器 (非阻塞)
    api.run(port=18170)
    
    # 启动主服务 (非阻塞)
    asyncio.create_task(service.start())
    
    # 保持运行
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())