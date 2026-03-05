#!/usr/bin/env python3
"""
Agent服务日志聚合与分析系统 V2
功能：
- 多源日志收集 (文件/API/syslog)
- 实时日志流处理
- 日志分析 (错误检测/模式识别/统计)
- 日志聚合API (端口18147)
- 日志搜索与过滤
- 日志告警
- 日志归档
"""

import asyncio
import json
import time
import re
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Event
import threading
import random
import hashlib
import gzip
import shutil

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class LogEntry:
    timestamp: str
    level: str
    service: str
    message: str
    source: str = "agent"
    metadata: Dict = field(default_factory=dict)
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.service}_{int(time.time()*1000)}"

class LogAggregator:
    """日志聚合器 V2"""
    
    def __init__(self, max_entries: int = 10000, db_path: str = "/root/.openclaw/workspace/ultron/tools/logs.db"):
        self.max_entries = max_entries
        self.db_path = db_path
        self.logs: List[LogEntry] = []
        self.lock = threading.Lock()
        self.services: Dict[str, dict] = {}
        self.file_watchers: Dict[str, List] = {}
        self.stop_event = Event()
        
        # 错误模式
        self.error_patterns = [
            (r"ERROR", "ERROR"),
            (r"Exception", "ERROR"),
            (r"Traceback\s+(?:most recent call|last)", "ERROR"),
            (r"Failed", "WARNING"),
            (r"CRITICAL", "CRITICAL"),
            (r"timeout", "WARNING"),
            (r"connection refused", "ERROR"),
            (r"OutOfMemory", "CRITICAL"),
            (r"Deadlock", "CRITICAL"),
        ]
        
        # 日志格式解析器
        self.log_formats = [
            # Python logging: 2026-03-06 00:00:00,000 INFO [service] message
            re.compile(r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+(\w+)\s+\[?(\w+)?\]?\s*(.*)$'),
            # Syslog: Mar  6 00:00:00 hostname service[pid]: message
            re.compile(r'^(\w+\s+\d+\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+?)(?:\[\d+\])?:\s*(.*)$'),
            # JSON: {"timestamp": "...", "level": "...", ...}
            # Simple: level: message
            re.compile(r'^(\w+):\s*(.*)$'),
        ]
        
        self.stats = {
            "total": 0,
            "by_level": defaultdict(int),
            "by_service": defaultdict(int),
            "errors": 0,
            "warnings": 0,
            "start_time": datetime.now().isoformat()
        }
        
        # 告警规则
        self.alert_rules = [
            {"pattern": r"CRITICAL|OutOfMemory|Deadlock", "level": "CRITICAL", "cooldown": 60},
            {"pattern": r"ERROR|Exception|connection refused", "level": "ERROR", "cooldown": 120},
            {"pattern": r"timeout|WARNING|Failed", "level": "WARNING", "cooldown": 300},
        ]
        self.last_alerts = {}
        
        # 初始化数据库
        self._init_db()
        
    def _init_db(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS logs (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            level TEXT,
            service TEXT,
            message TEXT,
            source TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_logs_service ON logs(service)''')
        c.execute('''CREATE TABLE IF NOT EXISTS log_stats (
            date TEXT PRIMARY KEY,
            total INTEGER,
            errors INTEGER,
            warnings INTEGER,
            by_service TEXT
        )''')
        conn.commit()
        conn.close()
        
    def _save_to_db(self, entry: LogEntry):
        """保存到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO logs 
                (id, timestamp, level, service, message, source, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (entry.id, entry.timestamp, entry.level, entry.service,
                 entry.message, entry.source, json.dumps(entry.metadata)))
            conn.commit()
            conn.close()
        except Exception as e:
            pass  # 静默失败
            
    def add_log(self, entry: LogEntry):
        with self.lock:
            self.logs.append(entry)
            if len(self.logs) > self.max_entries:
                self.logs = self.logs[-self.max_entries:]
            self.stats["total"] += 1
            self.stats["by_level"][entry.level] += 1
            self.stats["by_service"][entry.service] += 1
            if entry.level in ["ERROR", "CRITICAL"]:
                self.stats["errors"] += 1
            if entry.level == "WARNING":
                self.stats["warnings"] += 1
        
        # 保存到数据库
        self._save_to_db(entry)
        
        # 检查告警
        self._check_alerts(entry)
    
    def add_log_dict(self, data: Dict):
        entry = LogEntry(**data)
        self.add_log(entry)
        
    def _check_alerts(self, entry: LogEntry):
        """检查是否触发告警"""
        if entry.level not in ["ERROR", "WARNING", "CRITICAL"]:
            return
            
        for rule in self.alert_rules:
            if re.search(rule["pattern"], entry.message, re.IGNORECASE):
                alert_key = f"{entry.service}:{rule['pattern']}"
                now = time.time()
                
                if alert_key in self.last_alerts:
                    if now - self.last_alerts[alert_key] < rule["cooldown"]:
                        continue  # 冷却期内
                
                self.last_alerts[alert_key] = now
                # 这里可以触发告警通知
                print(f"[ALERT] {entry.level}: {entry.service} - {entry.message[:100]}")
                
    def parse_log_line(self, line: str, service: str = "unknown") -> Optional[LogEntry]:
        """解析日志行"""
        line = line.strip()
        if not line:
            return None
            
        # 尝试JSON解析
        if line.startswith("{"):
            try:
                data = json.loads(line)
                return LogEntry(
                    timestamp=data.get("timestamp", datetime.now().isoformat()),
                    level=data.get("level", "INFO"),
                    service=data.get("service", service),
                    message=data.get("message", line),
                    source=data.get("source", "file")
                )
            except:
                pass
                
        # 尝试正则匹配
        for fmt in self.log_formats:
            match = fmt.match(line)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    if len(groups) == 4:  # Python logging format
                        timestamp, level, svc, msg = groups
                        return LogEntry(
                            timestamp=timestamp,
                            level=level,
                            service=svc or service,
                            message=msg,
                            source="file"
                        )
                    elif len(groups) == 2:  # Simple format
                        level, msg = groups
                        return LogEntry(
                            timestamp=datetime.now().isoformat(),
                            level=level,
                            service=service,
                            message=msg,
                            source="file"
                        )
        
        # 默认解析
        return LogEntry(
            timestamp=datetime.now().isoformat(),
            level="INFO",
            service=service,
            message=line,
            source="file"
        )
        
    def watch_file(self, filepath: str, service: str = None):
        """监控日志文件"""
        if not os.path.exists(filepath):
            return
            
        service = service or os.path.basename(filepath)
        
        def watch():
            with open(filepath, 'r') as f:
                f.seek(0, 2)  # 跳到文件末尾
                while not self.stop_event.is_set():
                    line = f.readline()
                    if line:
                        entry = self.parse_log_line(line, service)
                        if entry:
                            self.add_log(entry)
                    time.sleep(0.1)
        
        thread = Thread(target=watch, daemon=True)
        thread.start()
        self.file_watchers[filepath] = thread
        
    def search(self, 
               query: str = None,
               level: str = None,
               service: str = None,
               since: str = None,
               until: str = None,
               limit: int = 100) -> List[Dict]:
        """搜索日志"""
        with self.lock:
            results = self.logs.copy()
            
        if query:
            results = [l for l in results if query.lower() in l.message.lower()]
        if level:
            results = [l for l in results if l.level == level]
        if service:
            results = [l for l in results if l.service == service]
        if since:
            since_dt = datetime.fromisoformat(since)
            results = [l for l in results 
                      if datetime.fromisoformat(l.timestamp) > since_dt]
        if until:
            until_dt = datetime.fromisoformat(until)
            results = [l for l in results 
                      if datetime.fromisoformat(l.timestamp) < until_dt]
            
        results = results[-limit:]
        return [asdict(l) for l in results]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            return {
                "total": self.stats["total"],
                "by_level": dict(self.stats["by_level"]),
                "by_service": dict(self.stats["by_service"]),
                "errors": self.stats["errors"],
                "warnings": self.stats["warnings"],
                "start_time": self.stats["start_time"],
                "recent_errors": len([l for l in self.logs[-100:] 
                                     if l.level in ["ERROR", "CRITICAL"]]),
                "recent_warnings": len([l for l in self.logs[-100:] 
                                        if l.level == "WARNING"]),
                "services_count": len(self.services),
                "file_watchers": len(self.file_watchers)
            }
    
    def get_error_summary(self) -> List[Dict]:
        """获取错误摘要"""
        with self.lock:
            errors = [l for l in self.logs if l.level in ["ERROR", "CRITICAL"]]
        
        # 按消息模式分组
        error_groups = defaultdict(list)
        for e in errors:
            # 提取错误模式 (简化: 取前80字符)
            msg = e.message[:80]
            error_groups[msg].append(e)
        
        return [
            {
                "pattern": msg,
                "count": len(entries),
                "last_occurrence": entries[-1].timestamp,
                "service": entries[0].service,
                "severity": max([e.level for e in entries])
            }
            for msg, entries in sorted(error_groups.items(), 
                                       key=lambda x: len(x[1]), 
                                       reverse=True)[:10]
        ]
    
    def get_service_health(self) -> Dict:
        """获取服务健康状态"""
        with self.lock:
            recent = self.logs[-500:]  # 最近500条
            
        health = {}
        for svc in set([l.service for l in recent]):
            svc_logs = [l for l in recent if l.service == svc]
            error_count = len([l for l in svc_logs if l.level in ["ERROR", "CRITICAL"]])
            warning_count = len([l for l in svc_logs if l.level == "WARNING"])
            total = len(svc_logs)
            
            if error_count > 5:
                status = "critical"
            elif error_count > 0 or warning_count > 10:
                status = "degraded"
            else:
                status = "healthy"
                
            health[svc] = {
                "status": status,
                "total": total,
                "errors": error_count,
                "warnings": warning_count,
                "error_rate": error_count / max(total, 1)
            }
            
        return health
    
    def register_service(self, name: str, log_path: str = None, 
                         api_endpoint: str = None):
        """注册服务"""
        self.services[name] = {
            "name": name,
            "log_path": log_path,
            "api_endpoint": api_endpoint,
            "registered_at": datetime.now().isoformat()
        }
        
    def get_trends(self, period_minutes: int = 60) -> Dict:
        """获取日志趋势"""
        since = datetime.now() - timedelta(minutes=period_minutes)
        
        with self.lock:
            recent = [l for l in self.logs 
                     if datetime.fromisoformat(l.timestamp) > since]
        
        # 按分钟统计
        by_minute = defaultdict(lambda: {"total": 0, "errors": 0, "warnings": 0})
        for l in recent:
            minute = l.timestamp[:16]  # YYYY-MM-DDTHH:MM
            by_minute[minute]["total"] += 1
            if l.level in ["ERROR", "CRITICAL"]:
                by_minute[minute]["errors"] += 1
            if l.level == "WARNING":
                by_minute[minute]["warnings"] += 1
                
        return {
            "period_minutes": period_minutes,
            "data": dict(sorted(by_minute.items())[-30:])  # 最近30分钟
        }
        
    def archive_old_logs(self, days: int = 7):
        """归档旧日志"""
        archive_dir = "/root/.openclaw/workspace/ultron/tools/log_archives"
        os.makedirs(archive_dir, exist_ok=True)
        
        since = datetime.now() - timedelta(days=days)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 获取旧日志
        c.execute("SELECT * FROM logs WHERE timestamp < ?", (since.isoformat(),))
        rows = c.fetchall()
        
        if rows:
            # 写入归档文件
            archive_file = f"{archive_dir}/logs_{since.strftime('%Y%m%d')}.jsonl.gz"
            with gzip.open(archive_file, 'wt') as f:
                for row in rows:
                    entry = {
                        "id": row[0], "timestamp": row[1], "level": row[2],
                        "service": row[3], "message": row[4], 
                        "source": row[5], "metadata": row[6]
                    }
                    f.write(json.dumps(entry) + "\n")
            
            # 删除旧日志
            c.execute("DELETE FROM logs WHERE timestamp < ?", (since.isoformat(),))
            conn.commit()
            
        conn.close()
        
# 全局日志聚合器实例
aggregator = LogAggregator()

# HTTP API服务器
class LogAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.strip("/")
        import urllib.parse
        
        if path == "health":
            self.send_json({"status": "ok", "service": "log-aggregator-v2", "port": 18147})
        elif path == "stats":
            self.send_json(aggregator.get_stats())
        elif path == "errors":
            self.send_json(aggregator.get_error_summary())
        elif path == "health_status":
            self.send_json(aggregator.get_service_health())
        elif path == "trends":
            query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            period = int(query.get("period", [60])[0])
            self.send_json(aggregator.get_trends(period))
        elif path.startswith("logs"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            results = aggregator.search(
                query=query.get("q", [None])[0],
                level=query.get("level", [None])[0],
                service=query.get("service", [None])[0],
                since=query.get("since", [None])[0],
                until=query.get("until", [None])[0],
                limit=int(query.get("limit", [100])[0])
            )
            self.send_json({"logs": results, "count": len(results)})
        elif path == "services":
            self.send_json({"services": list(aggregator.services.keys())})
        elif path == "watch":
            self.send_json({"file_watchers": list(aggregator.file_watchers.keys())})
        else:
            self.send_json({"error": "Not found"}, status=404)
            
    def do_POST(self):
        import urllib.parse
        if self.path == "/logs":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            aggregator.add_log_dict(data)
            self.send_json({"status": "ok"})
        elif self.path == "/register":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            aggregator.register_service(
                data.get("name"),
                data.get("log_path"),
                data.get("api_endpoint")
            )
            self.send_json({"status": "ok"})
        elif self.path == "/watch":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            aggregator.watch_file(data.get("path"), data.get("service"))
            self.send_json({"status": "ok", "watching": data.get("path")})
        else:
            self.send_json({"error": "Not found"}, status=404)
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass  # 抑制日志

def start_api_server(port=18147):
    """启动日志API服务器"""
    server = HTTPServer(("0.0.0.0", port), LogAPIHandler)
    print(f"Log Aggregator API V2 running on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    # 注册核心服务
    core_services = [
        "openclaw-gateway",
        "agent-orchestrator",
        "agent-interface-server",
        "mobile-gateway",
        "task-queue",
        "workflow-engine",
        "service-mesh",
        "orchestrator-api",
        "load-balancer-api"
    ]
    
    for svc in core_services:
        aggregator.register_service(svc)
    
    # 尝试监控一些日志文件
    log_files = [
        "/var/log/auth.log",
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            aggregator.watch_file(log_file, os.path.basename(log_file).replace(".log", ""))
    
    # 启动API服务器
    start_api_server(18147)