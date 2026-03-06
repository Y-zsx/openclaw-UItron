#!/usr/bin/env python3
"""
API服务治理中心
功能：统一管理API服务自动启动、健康检查和故障恢复
端口: 18170
"""

import json
import sqlite3
import logging
import subprocess
import psutil
import os
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
API_PORT = int(os.environ.get('PORT', 18250))
DB_PATH = "/root/.openclaw/workspace/ultron/logs/service_governance.db"
STATE_DIR = "/root/.openclaw/workspace/ultron/state"

# 服务配置：端口 -> 服务信息
SERVICE_REGISTRY = {
    18120: {"name": "decision-engine", "script": "decision_engine_api.py", "critical": True},
    18121: {"name": "decision-dashboard", "script": "decision_dashboard.py", "critical": False},
    18122: {"name": "feedback-learning", "script": "feedback_learning_api.py", "critical": False},
    18128: {"name": "decision-automation", "script": "automation.py", "critical": True},
    18150: {"name": "agent-collaboration", "script": "agent_collaboration_hub.py", "critical": True},
    18180: {"name": "collab-center", "script": "collab_center_api.py", "critical": True},
    18190: {"name": "collab-enhanced", "script": "collab_enhanced_api.py", "critical": False},
    18195: {"name": "ops-metrics", "script": "ops_metrics_api.py", "critical": True},
    18196: {"name": "task-monitor", "script": "task_monitor_api.py", "critical": True},
    18197: {"name": "task-alert-retry", "script": "task_alert_retry_api.py", "critical": False},
    18199: {"name": "alert-integration", "script": "alert_integration_api.py", "critical": True},
    18200: {"name": "health-check-api", "script": "health_check_api.py", "critical": True},
    18201: {"name": "scheduled-health", "script": "scheduled_health_check.py", "critical": True},
    18210: {"name": "agent-executor", "script": "agent_executor.py", "critical": True},
    18215: {"name": "agent-network-health", "script": "agent_network_health.py", "critical": True},
    18220: {"name": "fault-predictor", "script": "fault_predictor_api.py", "critical": False},
    18231: {"name": "collab-gateway", "script": "collab_gateway.py", "critical": True},
    18232: {"name": "orchestration-api", "script": "orchestration_api.py", "critical": True},
    18233: {"name": "lb-perf-optimizer", "script": "lb_perf_optimizer_api.py", "critical": False},
    18234: {"name": "mobile-adapter", "script": "mobile_adapter.py", "critical": False},
    18235: {"name": "identity-auth", "script": "identity_auth_api.py", "critical": True},
    18238: {"name": "federation-api", "script": "federation_api.py", "critical": False},
    18239: {"name": "health-prediction", "script": "health_prediction_enhanced.py", "critical": False},
    18240: {"name": "alert-statistics", "script": "alert_statistics_api.py", "critical": False},
    18241: {"name": "collab-perf", "script": "collab_perf_api.py", "critical": False},
    18242: {"name": "alert-intelligence", "script": "alert_intelligence_api.py", "critical": False},
    18243: {"name": "trigger-network", "script": "trigger_network_health.py", "critical": False},
    18270: {"name": "ultron-monitor", "script": "ultron_monitor.py", "critical": True},
    18290: {"name": "cross-system", "script": "cross_system_workflow.py", "critical": True},
    18096: {"name": "agent-mesh", "script": "agent_mesh_api.py", "critical": True},
    18097: {"name": "agent-lifecycle", "script": "agent_lifecycle_api.py", "critical": True},
    18098: {"name": "health-check", "script": "health_check_api.py", "critical": True},
    18099: {"name": "agent-monitor", "script": "agent_monitor.py", "critical": True},
    18101: {"name": "workflow-engine", "script": "workflow_engine.py", "critical": True},
}


class ServiceGovernance:
    """服务治理核心类"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.base_dir = "/root/.openclaw/workspace/ultron"
        self._ensure_db()
        self._init_registry()
    
    def _ensure_db(self):
        """确保数据库存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 服务状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                port INTEGER UNIQUE,
                name TEXT NOT NULL,
                script TEXT,
                status TEXT DEFAULT 'unknown',
                health_score REAL DEFAULT 0,
                last_check TIMESTAMP,
                last_start TIMESTAMP,
                restart_count INTEGER DEFAULT 0,
                critical INTEGER DEFAULT 0,
                auto_start INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 健康检查历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                port INTEGER,
                name TEXT,
                status TEXT,
                response_time REAL,
                details TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 自动启动配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auto_start_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                port INTEGER UNIQUE,
                enabled INTEGER DEFAULT 1,
                check_interval INTEGER DEFAULT 60,
                max_restarts INTEGER DEFAULT 3,
                restart_delay INTEGER DEFAULT 10,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _init_registry(self):
        """初始化服务注册表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for port, info in SERVICE_REGISTRY.items():
            cursor.execute("""
                INSERT OR IGNORE INTO service_status (port, name, script, critical)
                VALUES (?, ?, ?, ?)
            """, (port, info["name"], info.get("script", ""), 1 if info.get("critical") else 0))
            
            cursor.execute("""
                INSERT OR IGNORE INTO auto_start_config (port, enabled)
                VALUES (?, 1)
            """, (port,))
        
        conn.commit()
        conn.close()
    
    def check_port_health(self, port: int) -> dict:
        """检查端口健康状态"""
        start_time = time.time()
        result = {
            "port": port,
            "status": "down",
            "response_time": 0,
            "details": {}
        }
        
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            conn = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if conn == 0:
                result["status"] = "up"
                result["response_time"] = (time.time() - start_time) * 1000
                
                # 尝试获取健康检查端点
                try:
                    import urllib.request
                    req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
                    req.add_header('User-Agent', 'ServiceGovernance/1.0')
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        result["details"]["health_endpoint"] = resp.status == 200
                except:
                    pass
        except Exception as e:
            result["details"]["error"] = str(e)
        
        return result
    
    def check_all_services(self) -> list:
        """检查所有服务健康状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT port, name, script FROM service_status")
        services = cursor.fetchall()
        conn.close()
        
        results = []
        for port, name, script in services:
            health = self.check_port_health(port)
            results.append({
                "port": port,
                "name": name,
                "status": health["status"],
                "response_time": health["response_time"],
                "details": health.get("details", {})
            })
            
            # 更新数据库
            self._update_service_status(port, health)
        
        return results
    
    def _update_service_status(self, port: int, health: dict):
        """更新服务状态到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 更新服务状态
        score = 100 if health["status"] == "up" else 0
        cursor.execute("""
            UPDATE service_status 
            SET status = ?, health_score = ?, last_check = ?
            WHERE port = ?
        """, (health["status"], score, datetime.now().isoformat(), port))
        
        # 记录健康历史
        cursor.execute("""
            INSERT INTO health_history (port, name, status, response_time, details)
            VALUES (?, ?, ?, ?, ?)
        """, (port, SERVICE_REGISTRY.get(port, {}).get("name", "unknown"),
              health["status"], health["response_time"], json.dumps(health.get("details", {}))))
        
        conn.commit()
        conn.close()
    
    def get_service_status(self, port: int = None) -> dict:
        """获取服务状态"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if port:
            cursor.execute("SELECT * FROM service_status WHERE port = ?", (port,))
        else:
            cursor.execute("SELECT * FROM service_status ORDER BY critical DESC, port")
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_auto_start_config(self, port: int = None) -> dict:
        """获取自动启动配置"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if port:
            cursor.execute("SELECT * FROM auto_start_config WHERE port = ?", (port,))
        else:
            cursor.execute("SELECT * FROM auto_start_config")
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def update_auto_start(self, port: int, enabled: bool, check_interval: int = 60, 
                          max_restarts: int = 3, restart_delay: int = 10) -> bool:
        """更新自动启动配置"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO auto_start_config 
            (port, enabled, check_interval, max_restarts, restart_delay, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (port, 1 if enabled else 0, check_interval, max_restarts, restart_delay, 
              datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return True
    
    def get_health_trends(self, port: int = None, hours: int = 24) -> list:
        """获取健康趋势"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM health_history 
            WHERE checked_at > datetime('now', '-{} hours')
        """.format(hours)
        
        if port:
            query += f" AND port = {port}"
        
        query += " ORDER BY checked_at DESC LIMIT 1000"
        
        cursor.execute(query)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总服务数
        cursor.execute("SELECT COUNT(*) FROM service_status")
        total = cursor.fetchone()[0]
        
        # 运行中
        cursor.execute("SELECT COUNT(*) FROM service_status WHERE status = 'up'")
        running = cursor.fetchone()[0]
        
        # 关键服务
        cursor.execute("SELECT COUNT(*) FROM service_status WHERE critical = 1")
        critical = cursor.fetchone()[0]
        
        # 关键服务运行数
        cursor.execute("SELECT COUNT(*) FROM service_status WHERE critical = 1 AND status = 'up'")
        critical_running = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_services": total,
            "running_services": running,
            "down_services": total - running,
            "critical_services": critical,
            "critical_running": critical_running,
            "critical_down": critical - critical_running,
            "health_percentage": round(running / total * 100, 1) if total > 0 else 0
        }
    
    def restart_service(self, port: int) -> dict:
        """重启服务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取服务信息
        cursor.execute("SELECT name, script FROM service_status WHERE port = ?", (port,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {"success": False, "error": "Service not found"}
        
        name, script = row
        
        # 更新重启次数
        cursor.execute("""
            UPDATE service_status 
            SET restart_count = restart_count + 1, last_start = ?
            WHERE port = ?
        """, (datetime.now().isoformat(), port))
        
        conn.commit()
        conn.close()
        
        # 执行重启（通过systemd）
        service_name = f"{name}.service"
        try:
            subprocess.run(["systemctl", "restart", service_name], 
                         capture_output=True, timeout=30)
            return {"success": True, "message": f"Service {name} restarted"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GovernanceAPIHandler(BaseHTTPRequestHandler):
    """API请求处理"""
    
    governance = ServiceGovernance()
    
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")
    
    def send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == '/health':
            self.send_json({"status": "ok", "service": "service-governance"})
        
        elif path == '/services':
            services = self.governance.get_service_status()
            self.send_json({"services": services})
        
        elif path == '/services/all':
            # 实时检查所有服务
            services = self.governance.check_all_services()
            self.send_json({"services": services, "checked_at": datetime.now().isoformat()})
        
        elif path == '/services/stats':
            stats = self.governance.get_statistics()
            self.send_json(stats)
        
        elif path.startswith('/services/'):
            try:
                port = int(path.split('/')[-1])
                service = self.governance.get_service_status(port)
                if service:
                    self.send_json(service[0])
                else:
                    self.send_json({"error": "Service not found"}, 404)
            except:
                self.send_json({"error": "Invalid port"}, 400)
        
        elif path == '/auto-start':
            config = self.governance.get_auto_start_config()
            self.send_json({"config": config})
        
        elif path.startswith('/auto-start/'):
            try:
                port = int(path.split('/')[-1])
                config = self.governance.get_auto_start_config(port)
                if config:
                    self.send_json(config[0])
                else:
                    self.send_json({"error": "Config not found"}, 404)
            except:
                self.send_json({"error": "Invalid port"}, 400)
        
        elif path == '/trends':
            port = params.get('port', [None])[0]
            hours = int(params.get('hours', [24])[0])
            trends = self.governance.get_health_trends(int(port) if port else None, hours)
            self.send_json({"trends": trends})
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        if path == '/services/check':
            # 触发服务检查
            services = self.governance.check_all_services()
            self.send_json({"services": services, "checked_at": datetime.now().isoformat()})
        
        elif path.startswith('/services/'):
            # 提取端口号
            parts = path.split('/')
            if len(parts) >= 3 and parts[-1] == 'restart':
                try:
                    port = int(parts[-2])
                    result = self.governance.restart_service(port)
                    self.send_json(result)
                except:
                    self.send_json({"error": "Invalid request"}, 400)
            else:
                self.send_json({"error": "Not found"}, 404)
        
        elif path == '/auto-start':
            # 更新自动启动配置
            port = data.get('port')
            enabled = data.get('enabled', True)
            check_interval = data.get('check_interval', 60)
            max_restarts = data.get('max_restarts', 3)
            restart_delay = data.get('restart_delay', 10)
            
            if port:
                result = self.governance.update_auto_start(
                    port, enabled, check_interval, max_restarts, restart_delay
                )
                self.send_json({"success": result})
            else:
                self.send_json({"error": "Port required"}, 400)
        
        else:
            self.send_json({"error": "Not found"}, 404)


def run_server():
    """运行服务"""
    server = HTTPServer(('0.0.0.0', API_PORT), GovernanceAPIHandler)
    logger.info(f"Service Governance API started on port {API_PORT}")
    print(f"🔧 Service Governance API running on http://0.0.0.0:{API_PORT}")
    print(f"   Endpoints:")
    print(f"   - GET  /health              - 健康检查")
    print(f"   - GET  /services            - 服务列表")
    print(f"   - GET  /services/all        - 实时检查所有服务")
    print(f"   - GET  /services/stats      - 统计信息")
    print(f"   - GET  /services/<port>     - 指定服务状态")
    print(f"   - POST /services/check      - 触发检查")
    print(f"   - POST /services/<port>/restart - 重启服务")
    print(f"   - GET  /auto-start          - 自动启动配置")
    print(f"   - POST /auto-start          - 更新自动启动配置")
    print(f"   - GET  /trends              - 健康趋势")
    server.serve_forever()


if __name__ == '__main__':
    run_server()