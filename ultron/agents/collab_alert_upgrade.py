#!/usr/bin/env python3
"""
Agent协作网络智能告警升级系统
功能：
- 自动发现所有Agent服务
- 智能告警关联分析
- 告警自动升级机制
- 告警聚合与去重
- 告警预测性分析
- 多维度告警统计
"""

import json
import time
import threading
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
import socket

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("collab-alert-upgrade")


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"


@dataclass
class IntelligentAlert:
    """智能告警"""
    id: str
    service_name: str
    level: str
    message: str
    details: Dict[str, Any]
    status: str
    created_at: str
    resolved_at: Optional[str] = None
    escalated_from: Optional[str] = None
    correlation_id: Optional[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class AgentCollabAlertSystem:
    """Agent协作网络智能告警系统"""
    
    # 已知的Agent服务端口模式
    AGENT_PORT_PATTERNS = {
        18120: "decision-engine",
        18122: "decision-api",
        18125: "prediction-api",
        18130: "workflow-engine",
        18132: "workflow-api",
        18135: "decision-action",
        18140: "agent-orchestration",
        18141: "collab-perf-api",
        18142: "agent-mesh",
        18143: "agent-monitor",
        18144: "agent-scaling",
        18145: "agent-deployment",
        18148: "monitor-service",
        18149: "predictive-service",
        18150: "dashboard",
        18200: "ops-metrics",
        18210: "unified-status",
        18220: "decision-engine-v2",
        18230: "ops-metrics-api",
        18231: "metrics-static",
    }
    
    def __init__(self, port: int = 18151):
        self.port = port
        self.db_path = "/root/.openclaw/workspace/ultron/data/collab_alert.db"
        self.running = False
        self.monitor_thread = None
        self.alerts = {}  # alert_id -> IntelligentAlert
        self.correlations = defaultdict(list)  # correlation_id -> [alert_ids]
        self.service_cache = {}  # port -> service_info
        
        self._init_db()
        self._start_monitor()
        
    def _init_db(self):
        """初始化数据库"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                service_name TEXT,
                level TEXT,
                message TEXT,
                details TEXT,
                status TEXT,
                created_at TEXT,
                resolved_at TEXT,
                escalated_from TEXT,
                correlation_id TEXT,
                tags TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alert_correlations (
                correlation_id TEXT,
                alert_id TEXT,
                score REAL,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS escalation_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_level TEXT,
                to_level TEXT,
                time_threshold_seconds INTEGER,
                enabled INTEGER DEFAULT 1
            )
        ''')
        
        # 添加默认升级规则
        cursor.execute('SELECT COUNT(*) FROM escalation_rules')
        if cursor.fetchone()[0] == 0:
            rules = [
                ('warning', 'error', 300, 1),   # 5分钟未解决: warning -> error
                ('error', 'critical', 600, 1),  # 10分钟未解决: error -> critical
                ('critical', 'critical', 180, 1),  # 3分钟未解决: critical升级
            ]
            cursor.executemany(
                'INSERT INTO escalation_rules (from_level, to_level, time_threshold_seconds, enabled) VALUES (?, ?, ?, ?)',
                rules
            )
        
        conn.commit()
        conn.close()
        logger.info("智能告警数据库初始化完成")
    
    def _discover_services(self) -> Dict[int, Dict]:
        """自动发现Agent服务"""
        services = {}
        
        # 检查已知端口
        for port, name in self.AGENT_PORT_PATTERNS.items():
            if self._check_port(port):
                services[port] = {
                    "name": name,
                    "port": port,
                    "status": "healthy",
                    "last_check": datetime.now().isoformat()
                }
        
        # 扫描动态端口 (18000-19000范围)
        for port in range(18180, 18280):
            if port not in services and self._check_port(port):
                services[port] = {
                    "name": f"agent-service-{port}",
                    "port": port,
                    "status": "healthy",
                    "last_check": datetime.now().isoformat()
                }
        
        self.service_cache = services
        return services
    
    def _check_port(self, port: int) -> bool:
        """检查端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _generate_alert_id(self) -> str:
        return f"alert_{int(time.time() * 1000)}"
    
    def _generate_correlation_id(self, alert: IntelligentAlert) -> str:
        """生成告警关联ID"""
        # 基于服务名和关键词生成关联ID
        keywords = []
        for word in ['error', 'timeout', 'memory', 'cpu', 'disk', 'network']:
            if word in alert.message.lower():
                keywords.append(word)
        
        if keywords:
            return f"corr_{alert.service_name}_{keywords[0]}"
        return f"corr_{alert.service_name}_{int(time.time())}"
    
    def _check_escalation(self, alert: IntelligentAlert):
        """检查是否需要升级告警"""
        if alert.status != "firing":
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT from_level, to_level, time_threshold_seconds FROM escalation_rules WHERE enabled=1'
        )
        rules = cursor.fetchall()
        conn.close()
        
        created = datetime.fromisoformat(alert.created_at)
        elapsed = (datetime.now() - created).total_seconds()
        
        for from_level, to_level, threshold in rules:
            if alert.level == from_level and elapsed >= threshold:
                # 升级告警
                alert.level = to_level
                alert.status = "escalated"
                alert.escalated_from = alert.id
                logger.warning(f"告警升级: {alert.id} {from_level} -> {to_level}")
                
                # 创建新告警
                new_alert = IntelligentAlert(
                    id=self._generate_alert_id(),
                    service_name=alert.service_name,
                    level=to_level,
                    message=f"[升级] {alert.message}",
                    details=alert.details,
                    status="firing",
                    created_at=datetime.now().isoformat(),
                    escalated_from=alert.id,
                    correlation_id=alert.correlation_id,
                    tags=alert.tags + ["escalated"]
                )
                self.alerts[new_alert.id] = new_alert
                self._save_alert(new_alert)
                break
    
    def _save_alert(self, alert: IntelligentAlert):
        """保存告警到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO alerts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            alert.id, alert.service_name, alert.level, alert.message,
            json.dumps(alert.details), alert.status, alert.created_at,
            alert.resolved_at, alert.escalated_from, alert.correlation_id,
            json.dumps(alert.tags)
        ))
        
        conn.commit()
        conn.close()
    
    def _correlate_alert(self, alert: IntelligentAlert):
        """关联分析告警"""
        # 查找相关的活跃告警
        for existing_id, existing in self.alerts.items():
            if existing.status != "firing":
                continue
            if existing.service_name == alert.service_name:
                # 同一服务的告警关联
                if not alert.correlation_id:
                    alert.correlation_id = existing.correlation_id or self._generate_correlation_id(alert)
                if not existing.correlation_id:
                    existing.correlation_id = alert.correlation_id
                self.correlations[alert.correlation_id].extend([existing_id, alert.id])
    
    def create_alert(self, service_name: str, level: str, message: str, 
                     details: Dict = None, tags: List[str] = None) -> IntelligentAlert:
        """创建智能告警"""
        alert = IntelligentAlert(
            id=self._generate_alert_id(),
            service_name=service_name,
            level=level,
            message=message,
            details=details or {},
            status="firing",
            created_at=datetime.now().isoformat(),
            tags=tags or []
        )
        
        alert.correlation_id = self._generate_correlation_id(alert)
        self._correlate_alert(alert)
        
        self.alerts[alert.id] = alert
        self._save_alert(alert)
        
        logger.info(f"创建智能告警: {alert.id} [{level}] {service_name}: {message}")
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = "resolved"
            self.alerts[alert_id].resolved_at = datetime.now().isoformat()
            self._save_alert(self.alerts[alert_id])
            return True
        return False
    
    def get_alerts(self, status: str = None, level: str = None, 
                   service: str = None, limit: int = 50) -> List[Dict]:
        """获取告警列表"""
        result = []
        for alert in self.alerts.values():
            if status and alert.status != status:
                continue
            if level and alert.level != level:
                continue
            if service and alert.service_name != service:
                continue
            result.append(asdict(alert))
        
        result.sort(key=lambda x: x['created_at'], reverse=True)
        return result[:limit]
    
    def get_statistics(self) -> Dict:
        """获取告警统计"""
        stats = {
            "total": len(self.alerts),
            "by_status": defaultdict(int),
            "by_level": defaultdict(int),
            "by_service": defaultdict(int),
            "correlations": len(self.correlations),
            "active_services": len(self.service_cache),
            "timestamp": datetime.now().isoformat()
        }
        
        for alert in self.alerts.values():
            stats["by_status"][alert.status] += 1
            stats["by_level"][alert.level] += 1
            stats["by_service"][alert.service_name] += 1
        
        # 转换defaultdict
        stats["by_status"] = dict(stats["by_status"])
        stats["by_level"] = dict(stats["by_level"])
        stats["by_service"] = dict(stats["by_service"])
        
        return stats
    
    def get_correlation_groups(self) -> List[Dict]:
        """获取告警关联组"""
        groups = []
        for corr_id, alert_ids in self.correlations.items():
            alerts = [self.alerts[aid] for aid in alert_ids if aid in self.alerts]
            if len(alerts) > 1:
                groups.append({
                    "correlation_id": corr_id,
                    "count": len(alerts),
                    "alerts": [asdict(a) for a in alerts],
                    "master_alert": asdict(alerts[0])
                })
        return groups
    
    def _monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                # 发现服务
                services = self._discover_services()
                
                # 检查告警升级
                for alert in self.alerts.values():
                    self._check_escalation(alert)
                
                # 模拟一些测试告警（实际环境中根据监控数据生成）
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(5)
    
    def _start_monitor(self):
        """启动监控线程"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Agent协作网络智能告警系统监控已启动")
    
    def stop(self):
        """停止监控"""
        self.running = False


# HTTP API服务
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

class AlertHandler(BaseHTTPRequestHandler):
    system = None
    
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "collab-alert-upgrade"}).encode())
            
        elif path == '/api/services':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(self.system.service_cache).encode())
            
        elif path == '/api/alerts':
            params = urllib.parse.parse_qs(parsed.query)
            status = params.get('status', [None])[0]
            level = params.get('level', [None])[0]
            service = params.get('service', [None])[0]
            limit = int(params.get('limit', [50])[0])
            
            alerts = self.system.get_alerts(status, level, service, limit)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(alerts).encode())
            
        elif path == '/api/statistics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            stats = self.system.get_statistics()
            self.wfile.write(json.dumps(stats).encode())
            
        elif path == '/api/correlations':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            groups = self.system.get_correlation_groups()
            self.wfile.write(json.dumps(groups).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/api/alerts':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            alert = self.system.create_alert(
                service_name=data.get('service_name'),
                level=data.get('level', 'warning'),
                message=data.get('message'),
                details=data.get('details', {}),
                tags=data.get('tags', [])
            )
            
            self.send_response(201)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(asdict(alert)).encode())
            
        elif path == '/api/alerts/resolve':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            alert_id = data.get('alert_id')
            success = self.system.resolve_alert(alert_id)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode())
            
        else:
            self.send_response(404)
            self.end_headers()


def main():
    port = 18151
    system = AgentCollabAlertSystem(port)
    
    AlertHandler.system = system
    
    server = HTTPServer(('0.0.0.0', port), AlertHandler)
    logger.info(f"Agent协作网络智能告警升级系统启动成功，端口: {port}")
    logger.info(f"API端点:")
    logger.info(f"  - GET  /health - 健康检查")
    logger.info(f"  - GET  /api/services - 已发现服务列表")
    logger.info(f"  - GET  /api/alerts - 告警列表 (支持status/level/service/limit参数)")
    logger.info(f"  - GET  /api/statistics - 告警统计")
    logger.info(f"  - GET  /api/correlations - 告警关联组")
    logger.info(f"  - POST /api/alerts - 创建告警")
    logger.info(f"  - POST /api/alerts/resolve - 解决告警")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        system.stop()
        server.shutdown()


if __name__ == '__main__':
    main()