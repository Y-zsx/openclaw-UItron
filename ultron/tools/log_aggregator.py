#!/usr/bin/env python3
"""
Agent服务日志聚合与分析系统
功能：
- 多源日志收集 (文件/API/syslog)
- 实时日志流处理
- 日志分析 (错误检测/模式识别/统计)
- 日志聚合API (端口8091)
- 日志搜索与过滤
"""

import asyncio
import json
import time
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import threading

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
    """日志聚合器"""
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self.logs: List[LogEntry] = []
        self.lock = threading.Lock()
        self.services: Dict[str, dict] = {}
        self.error_patterns = [
            r"ERROR",
            r"Exception",
            r"Traceback",
            r"Failed",
            r"CRITICAL",
            r"timeout",
            r"connection refused"
        ]
        self.stats = {
            "total": 0,
            "by_level": defaultdict(int),
            "by_service": defaultdict(int),
            "errors": 0,
            "start_time": datetime.now().isoformat()
        }
        
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
    
    def add_log_dict(self, data: Dict):
        entry = LogEntry(**data)
        self.add_log(entry)
        
    def search(self, 
               query: str = None,
               level: str = None,
               service: str = None,
               since: str = None,
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
                "start_time": self.stats["start_time"],
                "recent_errors": len([l for l in self.logs[-100:] 
                                     if l.level in ["ERROR", "CRITICAL"]])
            }
    
    def get_error_summary(self) -> List[Dict]:
        """获取错误摘要"""
        errors = [l for l in self.logs if l.level in ["ERROR", "CRITICAL"]]
        error_groups = defaultdict(list)
        for e in errors:
            # 提取错误模式
            msg = e.message[:100]
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
    
    def register_service(self, name: str, log_path: str = None, 
                         api_endpoint: str = None):
        """注册服务"""
        self.services[name] = {
            "name": name,
            "log_path": log_path,
            "api_endpoint": api_endpoint,
            "registered_at": datetime.now().isoformat()
        }

# 全局日志聚合器实例
aggregator = LogAggregator()

# 模拟日志数据
def generate_sample_logs():
    """生成示例日志"""
    services = ["api-gateway", "service-mesh", "agent-orchestrator", 
                "workflow-engine", "agent-deployer"]
    messages = [
        ("INFO", "Service started successfully"),
        ("INFO", "Request processed in {ms}ms"),
        ("DEBUG", "Cache hit for key: user_{id}"),
        ("WARNING", "High memory usage detected: {mem}%"),
        ("ERROR", "Failed to connect to database: timeout"),
        ("INFO", "Task completed: {task_id}"),
        ("WARNING", "Rate limit approaching: {count}/100"),
        ("ERROR", "Authentication failed for user {user}"),
        ("INFO", "Health check passed"),
        ("CRITICAL", "Database connection lost"),
    ]
    
    for _ in range(50):
        service = services[int(time.time()) % len(services)]
        level, msg = messages[int(time.time() * 1000) % len(messages)]
        msg = msg.format(ms=random.randint(10, 500), 
                        id=random.randint(1000, 9999),
                        mem=random.randint(60, 95),
                        count=random.randint(80, 100),
                        user=f"user_{random.randint(1, 100)}",
                        task_id=f"task_{random.randint(1000, 9999)}")
        
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            service=service,
            message=msg,
            source="simulator"
        )
        aggregator.add_log(entry)
        time.sleep(0.1)

import random

# HTTP API服务器
class LogAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.strip("/")
        
        if path == "health":
            self.send_json({"status": "ok", "service": "log-aggregator"})
        elif path == "stats":
            self.send_json(aggregator.get_stats())
        elif path == "errors":
            self.send_json(aggregator.get_error_summary())
        elif path.startswith("logs"):
            # 解析查询参数
            import urllib.parse
            query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            results = aggregator.search(
                query=query.get("q", [None])[0],
                level=query.get("level", [None])[0],
                service=query.get("service", [None])[0],
                since=query.get("since", [None])[0],
                limit=int(query.get("limit", [100])[0])
            )
            self.send_json({"logs": results, "count": len(results)})
        elif path == "services":
            self.send_json({"services": aggregator.services})
        else:
            self.send_json({"error": "Not found"}, status=404)
            
    def do_POST(self):
        if self.path == "/logs":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            aggregator.add_log_dict(data)
            self.send_json({"status": "ok"})
        else:
            self.send_json({"error": "Not found"}, status=404)
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass  # 抑制日志

def start_api_server(port=8091):
    """启动日志API服务器"""
    server = HTTPServer(("0.0.0.0", port), LogAPIHandler)
    print(f"Log Aggregator API running on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    # 注册服务
    for svc in ["api-gateway", "service-mesh", "agent-orchestrator", 
                "workflow-engine", "agent-deployer"]:
        aggregator.register_service(svc)
    
    # 启动API服务器
    start_api_server(8091)