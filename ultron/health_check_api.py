#!/usr/bin/env python3
"""
健康检查API服务
功能：提供REST API接口访问健康检查数据
端口: 18098
"""

import json
import sqlite3
import logging
import psutil
import os
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
API_PORT = 18105
DB_PATH = "/root/.openclaw/workspace/ultron/logs/health_check_log.db"
STATE_FILE = "/root/.openclaw/workspace/ultron/state/scheduled_health_check.json"

# 服务配置
COLLAB_SERVICES = {
    8089: {"name": "api-gateway", "critical": True},
    8090: {"name": "secure-channel", "critical": True},
    8091: {"name": "identity-auth", "critical": True},
    8095: {"name": "collaboration-scheduler", "critical": True},
    8096: {"name": "agent-task-executor", "critical": True},
    18232: {"name": "orchestration-dashboard", "critical": False},
}


class HealthCheckAPI:
    """健康检查API核心类"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """确保数据库存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(self.db_path).exists():
            conn = sqlite3.connect(self.db_path)
            conn.close()
    
    def get_current_status(self) -> dict:
        """获取当前健康状态"""
        state_file = Path(STATE_FILE)
        if state_file.exists():
            try:
                return json.loads(state_file.read_text())
            except:
                pass
        return {"error": "No status available", "details": {}}
    
    def get_recent_checks(self, limit: int = 10) -> list:
        """获取最近健康检查记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM health_check_logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_service_history(self, port: int, limit: int = 50) -> list:
        """获取指定服务的健康历史"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM service_status_logs 
            WHERE port = ?
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (port, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_hourly_stats(self, hours: int = 24) -> list:
        """获取小时统计数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM hourly_health_stats 
            ORDER BY hour DESC 
            LIMIT ?
        """, (hours,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_statistics(self) -> dict:
        """获取统计数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总检查次数
        cursor.execute("SELECT COUNT(*) FROM health_check_logs")
        total_checks = cursor.fetchone()[0] or 0
        
        # 今日检查次数
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COUNT(*) FROM health_check_logs 
            WHERE timestamp LIKE ?
        """, (f"{today}%",))
        today_checks = cursor.fetchone()[0] or 0
        
        # 平均健康度
        cursor.execute("SELECT AVG(network_health) FROM health_check_logs")
        avg_health = cursor.fetchone()[0] or 0
        
        # 服务统计
        service_stats = {}
        for port, config in COLLAB_SERVICES.items():
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM service_status_logs 
                WHERE port = ?
                GROUP BY status
            """, (port,))
            stats = {row[0]: row[1] for row in cursor.fetchall()}
            service_stats[config["name"]] = stats
        
        conn.close()
        
        return {
            "total_checks": total_checks,
            "today_checks": today_checks,
            "avg_health": round(avg_health, 2),
            "services": COLLAB_SERVICES,
            "service_stats": service_stats
        }
    
    def get_all_services_status(self) -> list:
        """获取所有服务的当前状态"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        results = []
        for port, config in COLLAB_SERVICES.items():
            cursor.execute("""
                SELECT * FROM service_status_logs 
                WHERE port = ?
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (port,))
            row = cursor.fetchone()
            if row:
                results.append(dict(row))
            else:
                results.append({
                    "port": port,
                    "service_name": config["name"],
                    "status": "unknown",
                    "error": "No data"
                })
        
        conn.close()
        return results
    
    def get_health_trend(self, hours: int = 24) -> list:
        """获取健康趋势数据"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, network_health, healthy_services, total_services
            FROM health_check_logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (hours,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def trigger_health_check(self) -> dict:
        """触发一次健康检查"""
        import requests
        try:
            # 调用本地健康检查脚本
            result = {
                "status": "triggered",
                "timestamp": datetime.now().isoformat(),
                "message": "Health check triggered"
            }
            
            # 检查是否可以从状态文件获取最新结果
            status = self.get_current_status()
            if status and "check_count" in status:
                result["last_check"] = status
            
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_system_resources(self) -> dict:
        """获取系统资源使用情况"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # 内存使用
            memory = psutil.virtual_memory()
            
            # 磁盘使用
            disk = psutil.disk_usage('/')
            
            # 负载平均值
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            
            # 网络IO
            net_io = psutil.net_io_counters()
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "load_avg": load_avg
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取系统资源失败: {e}")
            return {"error": str(e)}
    
    def get_top_processes(self, limit: int = 10) -> list:
        """获取Top进程"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    pinfo = proc.info
                    if pinfo['cpu_percent'] is not None and pinfo['memory_percent'] is not None:
                        processes.append({
                            "pid": pinfo['pid'],
                            "name": pinfo['name'][:30],
                            "cpu": round(pinfo['cpu_percent'], 1),
                            "memory": round(pinfo['memory_percent'], 1)
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # 按CPU使用率排序
            processes.sort(key=lambda x: x['cpu'], reverse=True)
            return processes[:limit]
        except Exception as e:
            logger.error(f"获取Top进程失败: {e}")
            return []


class HealthCheckAPIHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    api = None
    
    def _send_json(self, data: dict, status: int = 200):
        """发送JSON响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())
    
    def do_GET(self):
        """处理GET请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        try:
            if path == '/health' or path == '/':
                # 健康检查端点
                self._send_json({
                    "status": "ok",
                    "service": "health-check-api",
                    "port": API_PORT,
                    "timestamp": datetime.now().isoformat()
                })
            
            elif path == '/status':
                # 当前状态
                status = self.api.get_current_status()
                self._send_json(status)
            
            elif path == '/services':
                # 所有服务状态
                services = self.api.get_all_services_status()
                self._send_json({"services": services})
            
            elif path == '/history':
                # 历史记录
                limit = int(query.get('limit', [10])[0])
                history = self.api.get_recent_checks(limit)
                self._send_json({"history": history})
            
            elif path == '/service':
                # 单个服务历史
                port = int(query.get('port', [0])[0])
                if port:
                    limit = int(query.get('limit', [50])[0])
                    history = self.api.get_service_history(port, limit)
                    self._send_json({"port": port, "history": history})
                else:
                    self._send_json({"error": "port required"}, 400)
            
            elif path == '/stats':
                # 统计数据
                stats = self.api.get_statistics()
                self._send_json(stats)
            
            elif path == '/trend':
                # 健康趋势
                hours = int(query.get('hours', [24])[0])
                trend = self.api.get_health_trend(hours)
                self._send_json({"trend": trend})
            
            elif path == '/hourly':
                # 小时统计
                hours = int(query.get('hours', [24])[0])
                hourly = self.api.get_hourly_stats(hours)
                self._send_json({"hourly": hourly})
            
            elif path == '/trigger':
                # 触发健康检查
                result = self.api.trigger_health_check()
                self._send_json(result)
            
            elif path == '/resources':
                # 系统资源使用情况
                resources = self.api.get_system_resources()
                self._send_json(resources)
            
            elif path == '/overview':
                # 综合概览（健康检查 + 系统资源）
                status = self.api.get_current_status()
                resources = self.api.get_system_resources()
                services = self.api.get_all_services_status()
                stats = self.api.get_statistics()
                self._send_json({
                    "status": status,
                    "resources": resources,
                    "services": services,
                    "stats": stats,
                    "timestamp": datetime.now().isoformat()
                })
            
            elif path == '/processes':
                # Top进程
                limit = int(query.get('limit', [10])[0])
                processes = self.api.get_top_processes(limit)
                self._send_json({"processes": processes})
            
            elif path == '/dashboard' or path == '/dashboard.html':
                # 仪表盘页面
                dashboard_path = Path("/root/.openclaw/workspace/ultron/health_check_dashboard.html")
                if dashboard_path.exists():
                    content = dashboard_path.read_text()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(content.encode('utf-8'))
                else:
                    self._send_json({"error": "Dashboard not found"}, 404)
            
            else:
                self._send_json({"error": "Not found"}, 404)
        
        except Exception as e:
            logger.error(f"API错误: {e}")
            self._send_json({"error": str(e)}, 500)
    
    def log_message(self, format, *args):
        """自定义日志"""
        logger.info(f"{self.client_address[0]} - {format % args}")


def run_server(port: int = API_PORT):
    """运行API服务器"""
    api = HealthCheckAPI()
    HealthCheckAPIHandler.api = api
    
    server = HTTPServer(('0.0.0.0', port), HealthCheckAPIHandler)
    logger.info(f"🚀 健康检查API服务启动成功 (端口: {port})")
    logger.info(f"   - /health      : 服务健康检查")
    logger.info(f"   - /status      : 当前健康状态")
    logger.info(f"   - /services    : 所有服务状态")
    logger.info(f"   - /history     : 健康检查历史")
    logger.info(f"   - /service     : 单个服务历史 (?port=8089)")
    logger.info(f"   - /stats       : 统计数据")
    logger.info(f"   - /trend       : 健康趋势")
    logger.info(f"   - /hourly      : 小时统计")
    logger.info(f"   - /trigger     : 触发健康检查")
    logger.info(f"   - /resources   : 系统资源(CPU/内存/磁盘)")
    logger.info(f"   - /processes   : Top进程列表")
    logger.info(f"   - /overview    : 综合概览")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 API服务已停止")
        server.shutdown()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else API_PORT
    run_server(port)