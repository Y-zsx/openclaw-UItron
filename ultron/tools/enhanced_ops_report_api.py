#!/usr/bin/env python3
"""
增强版运维报告API服务 - 第156世
提供统一的运维报告端点
"""
import json
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

WORKSPACE = "/root/.openclaw/workspace"
DB_PATH = f"{WORKSPACE}/ultron/tools/logs.db"
REPORT_DIR = f"{WORKSPACE}/ultron/logs"
Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)

class OpsReportHandler(BaseHTTPRequestHandler):
    """运维报告HTTP处理"""
    
    def do_GET(self):
        path = self.path
        
        if path == "/health":
            self.send_json({"status": "online", "service": "ops-report-api"})
        elif path == "/report":
            self.send_json(self.generate_report())
        elif path == "/metrics":
            self.send_json(self.get_prometheus_metrics())
        elif path == "/summary":
            report = self.generate_report()
            self.send_json({
                "health_score": report["health_score"],
                "services_online": report["services_online"],
                "services_total": report["services_total"],
                "cpu_load": report["system"]["cpu_load_1m"],
                "memory_percent": report["system"]["memory_percent"],
                "generated_at": report["generated_at"]
            })
        else:
            self.send_error(404)
    
    def generate_report(self):
        """生成完整报告"""
        sys_metrics = self.get_system_metrics()
        services = self.get_services()
        
        # 计算健康分数
        services_online = sum(1 for s in services.values() if s["healthy"])
        services_total = len(services)
        service_health = (services_online / services_total * 100) if services_total > 0 else 0
        
        # 资源健康
        cpu_health = max(0, 100 - sys_metrics["cpu_load_1m"] * 20)
        mem_health = max(0, 100 - sys_metrics["memory_percent"])
        
        # 综合健康分数
        health_score = round(
            service_health * 0.5 + cpu_health * 0.25 + mem_health * 0.25, 1
        )
        
        # 获取数据库统计
        db_stats = self.get_db_stats()
        
        return {
            "generated_at": datetime.now().isoformat(),
            "health_score": health_score,
            "services_online": services_online,
            "services_total": services_total,
            "system": sys_metrics,
            "services": services,
            "database": db_stats,
            "health_factors": [
                {"name": "服务可用性", "score": service_health, "weight": 0.5},
                {"name": "CPU负载", "score": cpu_health, "weight": 0.25},
                {"name": "内存使用", "score": mem_health, "weight": 0.25}
            ]
        }
    
    def get_system_metrics(self):
        """获取系统指标"""
        try:
            # CPU
            load = subprocess.run(["cat", "/proc/loadavg"], capture_output=True, text=True).stdout.split()
            
            # 内存
            mem = subprocess.run(["free", "-m"], capture_output=True, text=True).stdout.split()
            mem_total = int(mem[7])
            mem_used = int(mem[8])
            
            # 磁盘
            disk = subprocess.run(["df", "-h", "/"], capture_output=True, text=True).stdout.split()
            
            # 连接
            conn_count = len(subprocess.run(["ss", "-tn"], capture_output=True, text=True).stdout.split('\n')) - 1
            
            return {
                "cpu_load_1m": float(load[0]),
                "cpu_load_5m": float(load[1]),
                "cpu_load_15m": float(load[2]),
                "memory_total_mb": mem_total,
                "memory_used_mb": mem_used,
                "memory_percent": round(mem_used / mem_total * 100, 1),
                "disk_used": disk[2].decode() if isinstance(disk[2], bytes) else disk[2],
                "disk_percent": disk[4].decode() if isinstance(disk[4], bytes) else disk[4],
                "connections": conn_count
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_services(self):
        """获取服务状态"""
        # 统一健康检查端点
        services = {
            18789: ("Gateway", "/health"),
            18210: ("Agent执行器", "/health"),
            18199: ("系统总结", "/summary"),
            18197: ("任务告警", "/health"),
            18196: ("Agent健康", "/health"),
            18195: ("任务监控", "/health"),
            18180: ("健康报告", "/health"),
            18170: ("告警集成", "/health"),
            18150: ("Agent网络", "/health"),
            18132: ("跨域决策", "/health"),
            18128: ("自动化引擎", "/health"),
            18121: ("决策仪表盘", "/health"),
            18120: ("决策引擎", "/health"),
            18100: ("工作流引擎", "/health"),
        }
        
        result = {}
        for port, (name, endpoint) in services.items():
            try:
                resp = subprocess.run(
                    ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"http://localhost:{port}{endpoint}"],
                    capture_output=True, text=True, timeout=3
                )
                code = resp.stdout.strip()
                healthy = code == "200"
                result[name] = {"port": port, "status": "online" if healthy else "offline", "healthy": healthy}
            except:
                result[name] = {"port": port, "status": "unknown", "healthy": False}
        
        return result
    
    def get_db_stats(self):
        """获取数据库统计"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM logs")
            total = cur.fetchone()[0]
            
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            cur.execute("SELECT COUNT(*) FROM logs WHERE timestamp > ? AND level = 'ERROR'", (one_hour_ago,))
            recent_err = cur.fetchone()[0]
            
            conn.close()
            return {"total_logs": total, "recent_errors_1h": recent_err}
        except Exception as e:
            return {"error": str(e)}
    
    def get_prometheus_metrics(self):
        """Prometheus格式指标"""
        report = self.generate_report()
        metrics = [
            f'# HELP ultron_health_score Overall system health score',
            f'# TYPE ultron_health_score gauge',
            f'ultron_health_score {report["health_score"]}',
            f'',
            f'# HELP ultron_services_online Number of online services',
            f'# TYPE ultron_services_online gauge',
            f'ultron_services_online {report["services_online"]}',
            f'',
            f'# HELP ultron_cpu_load System CPU load (1min)',
            f'# TYPE ultron_cpu_load gauge',
            f'ultron_cpu_load {report["system"]["cpu_load_1m"]}',
            f'',
            f'# HELP ultron_memory_percent Memory usage percent',
            f'# TYPE ultron_memory_percent gauge',
            f'ultron_memory_percent {report["system"]["memory_percent"]}',
        ]
        return {"metrics": "\n".join(metrics)}
    
    def send_json(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

def start_server(port=18200):
    """启动API服务"""
    server = HTTPServer(("0.0.0.0", port), OpsReportHandler)
    print(f"🚀 运维报告API启动: http://0.0.0.0:{port}")
    print(f"   - /health 健康检查")
    print(f"   - /report 完整报告")
    print(f"   - /summary 简要摘要")
    print(f"   - /metrics Prometheus指标")
    server.serve_forever()

if __name__ == "__main__":
    start_server(18200)