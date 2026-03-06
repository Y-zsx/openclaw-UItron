#!/usr/bin/env python3
"""
系统总结报告API服务
统一入口，整合系统健康、服务状态、告警统计、任务执行等多维度数据
端口: 18199
"""
import json
import os
import sys
import socket
import sqlite3
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 配置
WORKSPACE = Path("/root/.openclaw/workspace")
REPORTS_DIR = WORKSPACE / "ultron" / "reports"
DATA_DIR = WORKSPACE / "ultron" / "data"
ALERTS_DB = DATA_DIR / "alerts.db"
HEALTH_DB = DATA_DIR / "health_check_logs.db"
SYSTEM_DB = DATA_DIR / "system_metrics.db"
TASKS_DB = DATA_DIR / "tasks.db"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 端口配置
PORT = 18199

# ============= 增强功能: 趋势分析 =============
import urllib.request
import urllib.parse

def push_summary_to_dingtalk(hours=24):
    """推送总结报告到钉钉"""
    try:
        # 获取报告数据
        report = generate_summary_report(hours)
        insights = get_smart_insights(hours)
        
        # 格式化消息
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # 告警图标
        status_icon = "🟢" if report["health_score"] >= 90 else "🟡" if report["health_score"] >= 75 else "🔴"
        
        # 构建消息
        msg = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"系统总结报告 - {report['health_score']}%",
                "text": f"""## {status_icon} 系统总结报告 - {timestamp}

**健康分数**: {report['health_score']}% ({report['status_cn']})
**检查周期**: 过去 {hours} 小时
**当前世**: 第{report['incarnation']['incarnation']}世

---

### 🖥️ 系统资源
- CPU负载: {report['resources'].get('cpu_load_1m', 'N/A')}
- 内存: {report['resources'].get('memory_percent', 'N/A')}%
- 磁盘: {report['resources'].get('disk_percent', 'N/A')}

### 🔧 服务状态
在线: {report['services']['summary']['online']}/{report['services']['summary']['total']} ({report['services']['summary']['health_percent']}%)
- 离线: {report['services']['summary']['offline']} 个

### 🚨 告警
过去{hours}小时共 {report['alerts'].get('total', 0)} 条告警

### 💡 智能洞察 ({len(insights['insights'])}条)
"""
                + "\n".join([f"- {i['title']}: {i['message']}" for i in insights['insights'][:5]])
                + f"""

---

*🤖 奥创系统自动生成*
"""
            }
        }
        
        # 发送请求
        config_path = WORKSPACE / "ultron" / "config" / "notification_channels.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            
            webhook = os.environ.get("DINGTALK_WEBHOOK")
            if not webhook:
                # 使用默认的测试webhook
                webhook = "https://oapi.dingtalk.com/robot/send?access_token=dingtalk_webhook_placeholder"
            
            # 检查是否有真实webhook
            if "placeholder" in webhook:
                return {"status": "skipped", "message": "未配置钉钉Webhook"}
            
            data = json.dumps(msg).encode('utf-8')
            req = urllib.request.Request(
                webhook,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                if result.get('errcode') == 0:
                    return {"status": "success", "message": "报告已推送"}
                else:
                    return {"status": "error", "message": result.get('errmsg', '未知错误')}
        
        return {"status": "skipped", "message": "无钉钉配置"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_trend_analysis(hours=24):
    """趋势分析 - 对比不同时段的数据"""
    current = generate_summary_report(hours)
    
    # 获取上一时段的数据作为对比
    previous = generate_summary_report(hours * 2)
    
    def compare(key, current_val, previous_val, higher_is_better=True):
        if current_val is None or previous_val is None or previous_val == 0:
            return {"change": 0, "direction": "stable"}
        
        change = ((current_val - previous_val) / previous_val) * 100
        
        if abs(change) < 5:
            direction = "stable"
        elif change > 0:
            direction = "up" if higher_is_better else "down"
        else:
            direction = "down" if higher_is_better else "up"
        
        return {
            "change": round(change, 1),
            "direction": direction,
            "current": current_val,
            "previous": previous_val
        }
    
    def safe_get(d, key, default=0):
        """安全获取字典值"""
        if isinstance(d, dict):
            return d.get(key, default) if "error" not in d else default
        return default
    
    return {
        "timestamp": datetime.now().isoformat(),
        "period_hours": hours,
        "health_score": compare("health_score", current["health_score"], previous["health_score"]),
        "services": compare("services", current["services"]["summary"]["health_percent"], 
                           previous["services"]["summary"]["health_percent"]),
        "alerts": compare("alerts", safe_get(current["alerts"], "total"), 
                         safe_get(previous["alerts"], "total"), 
                         higher_is_better=False),
        "memory": compare("memory", current["resources"]["memory_percent"], 
                         previous["resources"]["memory_percent"], higher_is_better=False),
        "cpu_load": compare("cpu_load", float(current["resources"]["cpu_load_1m"] or 0), 
                           float(previous["resources"]["cpu_load_1m"] or 0), higher_is_better=False)
    }

def get_smart_insights(hours=24):
    """智能洞察 - 基于数据生成优化建议"""
    report = generate_summary_report(hours)
    insights = []
    
    # 1. 服务可用性洞察
    service_health = report["services"]["summary"]["health_percent"]
    if service_health < 80:
        offline_services = [name for name, info in report["services"]["services"].items() 
                           if not info["healthy"]]
        insights.append({
            "type": "warning",
            "category": "services",
            "title": "服务可用性偏低",
            "message": f"当前可用率仅 {service_health}%，以下服务离线: {', '.join(offline_services[:5])}",
            "action": "检查离线服务状态并重启"
        })
    elif service_health >= 95:
        insights.append({
            "type": "success",
            "category": "services",
            "title": "服务运行良好",
            "message": f"服务可用率 {service_health}%，所有核心服务正常运行",
            "action": "继续保持"
        })
    
    # 2. 资源使用洞察
    mem_percent = report["resources"]["memory_percent"]
    if mem_percent > 85:
        insights.append({
            "type": "critical",
            "category": "resources",
            "title": "内存使用率过高",
            "message": f"内存使用率达 {mem_percent}%，建议清理不活跃进程",
            "action": "执行内存清理或扩展swap"
        })
    
    cpu_load = float(report["resources"]["cpu_load_1m"] or 0)
    cpu_count = report["resources"]["cpu_count"]
    if cpu_load > cpu_count * 2:
        insights.append({
            "type": "warning",
            "category": "resources",
            "title": "CPU负载过高",
            "message": f"1分钟负载 {cpu_load} 超过CPU核心数 {cpu_count} 的2倍",
            "action": "检查高负载进程，考虑扩容"
        })
    
    # 3. 告警洞察
    alert_data = report.get("alerts", {})
    if isinstance(alert_data, dict):
        alert_total = alert_data.get("total", 0) if "error" not in alert_data else 0
        by_severity = alert_data.get("by_severity", {}) if "error" not in alert_data else {}
    else:
        alert_total = 0
        by_severity = {}
    
    if alert_total > 10:
        critical = by_severity.get("critical", 0)
        error = by_severity.get("error", 0)
        insights.append({
            "type": "critical" if critical > 0 else "warning",
            "category": "alerts",
            "title": f"告警数量过多 ({alert_total}条)",
            "message": f"其中 critical: {critical}, error: {error}",
            "action": "分析告警根因并修复"
        })
    elif alert_total == 0:
        insights.append({
            "type": "success",
            "category": "alerts",
            "title": "无告警",
            "message": "过去24小时没有告警，系统运行平稳",
            "action": "继续保持"
        })
    
    # 4. 健康检查洞察
    health_uptime = report["health"].get("overall_uptime_percent", 0)
    if health_uptime < 95:
        failing_services = [s["service"] for s in report["health"].get("services", []) 
                          if s["uptime_percent"] < 95]
        insights.append({
            "type": "warning",
            "category": "health",
            "title": f"健康检查可用率偏低 ({health_uptime}%)",
            "message": f"以下服务可用率不足: {', '.join(failing_services[:3])}",
            "action": "检查服务健康状态"
        })
    
    # 5. 任务执行洞察
    task_total = report["tasks"].get("total", 0)
    if task_total == 0 and hours > 6:
        insights.append({
            "type": "info",
            "category": "tasks",
            "title": "无任务执行",
            "message": f"过去{hours}小时没有任务执行记录",
            "action": "检查任务调度器是否正常"
        })
    
    # 6. 转世系统洞察
    incarnation = report["incarnation"]
    task_status = incarnation.get("task_status", "unknown")
    if task_status != "completed":
        insights.append({
            "type": "info",
            "category": "incarnation",
            "title": f"第{incarnation['incarnation']}世任务进行中",
            "message": f"当前任务状态: {task_status}",
            "action": "监控任务执行进度"
        })
    
    return {
        "timestamp": datetime.now().isoformat(),
        "health_score": report["health_score"],
        "insights_count": len(insights),
        "insights": insights,
        "summary": {
            "critical": len([i for i in insights if i["type"] == "critical"]),
            "warning": len([i for i in insights if i["type"] == "warning"]),
            "success": len([i for i in insights if i["type"] == "success"]),
            "info": len([i for i in insights if i["type"] == "info"])
        }
    }

# ============= 数据收集函数 =============

def get_system_resources():
    """获取系统资源信息"""
    try:
        # CPU负载
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[:3]
        
        # 内存
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
            mem_total = int([l for l in meminfo.split('\n') if 'MemTotal' in l][0].split()[1])
            mem_available = int([l for l in meminfo.split('\n') if 'MemAvailable' in l][0].split()[1])
            mem_used = mem_total - mem_available
            mem_percent = round(mem_used / mem_total * 100, 1)
        
        # 磁盘
        disk_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        disk_parts = disk_result.stdout.split('\n')[1].split()
        disk_used = disk_parts[2]
        disk_percent = disk_parts[4]
        
        # 网络连接数
        try:
            net_result = subprocess.run(['ss', '-tun'], capture_output=True, text=True, timeout=5)
            conn_count = len([l for l in net_result.stdout.split('\n') if l.strip() and 'ESTAB' in l])
        except:
            conn_count = 0
        
        # 进程数
        try:
            proc_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
            process_count = len(proc_result.stdout.split('\n')) - 1
        except:
            process_count = 0
        
        return {
            "cpu_load_1m": load[0],
            "cpu_load_5m": load[1],
            "cpu_load_15m": load[2],
            "memory_percent": mem_percent,
            "memory_used_mb": round(mem_used / 1024, 1),
            "memory_total_mb": round(mem_total / 1024, 1),
            "disk_used": disk_used,
            "disk_percent": disk_percent,
            "connections": conn_count,
            "processes": process_count,
            "cpu_count": os.cpu_count() or 4
        }
    except Exception as e:
        return {"error": str(e)}

def get_core_services_status():
    """获取核心服务状态"""
    services = [
        ("Gateway", 18789),
        ("协作网络", 8089),
        ("Agent注册", 8100),
        ("Agent规范", 8110),
        ("Agent预测", 8120),
        ("工作流引擎", 18100),
        ("决策引擎", 18120),
        ("自动化引擎", 18128),
        ("Agent网络", 18150),
        ("任务执行器", 18210),
        ("健康监控", 18090),
        ("协作监控", 18093),
        ("运维仪表盘", 18095),
        ("告警集成", 18170),
        ("健康报告", 18180),
        ("任务监控", 18195),
        ("Agent健康", 18196),
        ("任务告警", 18197),
        ("增强日志", 18091),
        ("增强健康", 18092),
        ("跨域决策", 18132),
        ("反馈学习", 18122),
        ("决策仪表盘", 18121),
    ]
    
    result = {}
    for name, port in services:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            r = sock.connect_ex(('127.0.0.1', port))
            result[name] = {"port": port, "status": "online" if r == 0 else "offline", "healthy": r == 0}
        except Exception as e:
            result[name] = {"port": port, "status": "error", "healthy": False, "error": str(e)}
        finally:
            sock.close()
    
    # 统计
    total = len(result)
    online = sum(1 for s in result.values() if s["healthy"])
    
    return {
        "services": result,
        "summary": {
            "total": total,
            "online": online,
            "offline": total - online,
            "health_percent": round(online / total * 100, 1)
        }
    }

def get_alert_statistics(hours=24):
    """获取告警统计"""
    if not ALERTS_DB.exists():
        return {"total": 0, "by_severity": {}, "by_service": {}, "recent": []}
    
    try:
        conn = sqlite3.connect(str(ALERTS_DB))
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        # 按严重级别统计
        cursor.execute(
            "SELECT severity, COUNT(*) FROM alerts WHERE created_at >= ? GROUP BY severity",
            (since,)
        )
        by_severity = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 按服务统计
        cursor.execute(
            "SELECT source, COUNT(*) FROM alerts WHERE created_at >= ? GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10",
            (since,)
        )
        by_service = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 总数
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE created_at >= ?", (since,))
        total = cursor.fetchone()[0]
        
        # 最近告警
        cursor.execute(
            "SELECT id, severity, title, source, created_at FROM alerts WHERE created_at >= ? ORDER BY created_at DESC LIMIT 10",
            (since,)
        )
        recent = [
            {"id": r[0], "severity": r[1], "title": r[2], "source": r[3], "time": r[4]}
            for r in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "total": total,
            "by_severity": by_severity,
            "by_service": by_service,
            "recent": recent,
            "period_hours": hours
        }
    except Exception as e:
        return {"error": str(e)}

def get_health_check_stats(hours=24):
    """获取健康检查统计"""
    if not HEALTH_DB.exists():
        return {"services": [], "overall_uptime": 0}
    
    try:
        conn = sqlite3.connect(str(HEALTH_DB))
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 按服务统计
        cursor.execute('''
            SELECT 
                service_name,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
                AVG(latency_ms) as avg_latency
            FROM health_checks
            WHERE timestamp >= ?
            GROUP BY service_name
        ''', (since,))
        
        services = []
        total_healthy = 0
        total_checks = 0
        
        for row in cursor.fetchall():
            service, total, healthy, avg_lat = row
            uptime = (healthy / total * 100) if total > 0 else 0
            total_healthy += healthy
            total_checks += total
            services.append({
                "service": service,
                "total_checks": total,
                "healthy_checks": healthy,
                "uptime_percent": round(uptime, 2),
                "avg_latency_ms": round(avg_lat, 2) if avg_lat else 0
            })
        
        overall_uptime = (total_healthy / total_checks * 100) if total_checks > 0 else 0
        
        conn.close()
        
        return {
            "services": services,
            "overall_uptime_percent": round(overall_uptime, 2),
            "period_hours": hours
        }
    except Exception as e:
        return {"error": str(e)}

def get_task_statistics(hours=24):
    """获取任务执行统计"""
    tasks_db_paths = [
        DATA_DIR / "tasks.db",
        Path("/root/.openclaw/workspace/ultron-self/task-repo/tasks.db"),
    ]
    
    tasks_db = None
    for p in tasks_db_paths:
        if p.exists():
            tasks_db = p
            break
    
    if not tasks_db:
        return {"total": 0, "by_status": {}, "recent": []}
    
    try:
        conn = sqlite3.connect(str(tasks_db))
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 尝试获取任务统计
        try:
            cursor.execute(
                "SELECT status, COUNT(*) FROM tasks WHERE created_at >= ? GROUP BY status",
                (since,)
            )
            by_status = {row[0]: row[1] for row in cursor.fetchall()}
        except:
            by_status = {}
        
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE created_at >= ?",
                (since,)
            )
            total = cursor.fetchone()[0]
        except:
            total = 0
        
        # 最近任务
        try:
            cursor.execute(
                "SELECT id, task_type, status, created_at FROM tasks WHERE created_at >= ? ORDER BY created_at DESC LIMIT 10",
                (since,)
            )
            recent = [
                {"id": r[0], "type": r[1], "status": r[2], "time": r[3]}
                for r in cursor.fetchall()
            ]
        except:
            recent = []
        
        conn.close()
        
        return {
            "total": total,
            "by_status": by_status,
            "recent": recent,
            "period_hours": hours
        }
    except Exception as e:
        return {"error": str(e)}

def get_decision_stats(hours=24):
    """获取决策引擎统计"""
    decision_db = DATA_DIR / "decisions.db"
    if not decision_db.exists():
        return {"total": 0, "by_type": {}, "by_risk": {}}
    
    try:
        conn = sqlite3.connect(str(decision_db))
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 统计
        try:
            cursor.execute("SELECT COUNT(*) FROM decisions WHERE created_at >= ?", (since,))
            total = cursor.fetchone()[0]
        except:
            total = 0
        
        try:
            cursor.execute(
                "SELECT decision_type, COUNT(*) FROM decisions WHERE created_at >= ? GROUP BY decision_type",
                (since,)
            )
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
        except:
            by_type = {}
        
        try:
            cursor.execute(
                "SELECT risk_level, COUNT(*) FROM decisions WHERE created_at >= ? GROUP BY risk_level",
                (since,)
            )
            by_risk = {str(row[0]): row[1] for row in cursor.fetchall()}
        except:
            by_risk = {}
        
        conn.close()
        
        return {
            "total": total,
            "by_type": by_type,
            "by_risk": by_risk,
            "period_hours": hours
        }
    except Exception as e:
        return {"error": str(e)}

def get_workflow_stats(hours=24):
    """获取工作流统计"""
    workflow_db = DATA_DIR / "workflows.db"
    if not workflow_db.exists():
        return {"total": 0, "by_status": {}}
    
    try:
        conn = sqlite3.connect(str(workflow_db))
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM workflows WHERE created_at >= ?", (since,))
            total = cursor.fetchone()[0]
        except:
            total = 0
        
        try:
            cursor.execute(
                "SELECT status, COUNT(*) FROM workflows WHERE created_at >= ? GROUP BY status",
                (since,)
            )
            by_status = {row[0]: row[1] for row in cursor.fetchall()}
        except:
            by_status = {}
        
        conn.close()
        
        return {
            "total": total,
            "by_status": by_status,
            "period_hours": hours
        }
    except Exception as e:
        return {"error": str(e)}

def get_incarnation_info():
    """获取当前转世信息"""
    state_file = WORKSPACE / "ultron-workflow" / "state.json"
    if not state_file.exists():
        return {"incarnation": "unknown", "ambition": "unknown"}
    
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        return {
            "incarnation": state.get("current", {}).get("incarnation", "unknown"),
            "ambition": state.get("current", {}).get("ambition", "unknown"),
            "task_status": state.get("current", {}).get("task_status", "unknown"),
            "last_wake": state.get("current", {}).get("last_wake", "unknown")
        }
    except Exception as e:
        return {"error": str(e)}

# ============= 报告生成 =============

def generate_summary_report(hours=24):
    """生成综合总结报告"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 收集所有数据
    resources = get_system_resources()
    services = get_core_services_status()
    alerts = get_alert_statistics(hours)
    health = get_health_check_stats(hours)
    tasks = get_task_statistics(hours)
    decisions = get_decision_stats(hours)
    workflows = get_workflow_stats(hours)
    incarnation = get_incarnation_info()
    
    # 计算综合健康分数
    health_score = 0
    factors = []
    
    # 服务健康 (40%)
    service_health = services["summary"]["health_percent"]
    factors.append(("服务可用性", service_health, 0.4))
    
    # 健康检查 (30%)
    health_uptime = health.get("overall_uptime_percent", 100)
    factors.append(("健康检查", health_uptime, 0.3))
    
    # 告警 (20%)
    alert_score = 100
    if alerts.get("total", 0) > 0:
        critical = alerts.get("by_severity", {}).get("critical", 0)
        error = alerts.get("by_severity", {}).get("error", 0)
        alert_score = max(0, 100 - critical * 10 - error * 5)
    factors.append(("告警状态", alert_score, 0.2))
    
    # 资源 (10%)
    resource_score = 100
    if resources.get("cpu_load_1m"):
        load = float(resources["cpu_load_1m"])
        cpu_count = resources.get("cpu_count", 4)
        if load > cpu_count:
            resource_score = max(0, 100 - (load - cpu_count) * 20)
    factors.append(("资源状态", resource_score, 0.1))
    
    # 计算总分
    health_score = sum(score * weight for _, score, weight in factors)
    
    # 确定状态
    if health_score >= 90:
        status = "excellent"
        status_cn = "优秀"
    elif health_score >= 75:
        status = "good"
        status_cn = "良好"
    elif health_score >= 50:
        status = "degraded"
        status_cn = "一般"
    else:
        status = "critical"
        status_cn = "危险"
    
    report = {
        "timestamp": timestamp,
        "period_hours": hours,
        "health_score": round(health_score, 1),
        "status": status,
        "status_cn": status_cn,
        "resources": resources,
        "services": services,
        "alerts": alerts,
        "health": health,
        "tasks": tasks,
        "decisions": decisions,
        "workflows": workflows,
        "incarnation": incarnation,
        "factors": [{"name": n, "score": s, "weight": w} for n, s, w in factors]
    }
    
    return report

def generate_markdown_report(hours=24):
    """生成Markdown格式报告"""
    report = generate_summary_report(hours)
    timestamp = datetime.now().strftime('%Y年%m月%d日 %H:%M')
    
    md = f"""# 📊 系统总结报告 - {timestamp}

**综合健康分数**: {report['health_score']}% ({report['status_cn']})
**检查周期**: 过去 {hours} 小时
**当前世**: 第{report['incarnation']['incarnation']}世 - {report['incarnation'].get('ambition', 'N/A')}

---

## 🖥️ 系统资源

| 指标 | 数值 |
|------|------|
| CPU负载 (1m/5m/15m) | {report['resources'].get('cpu_load_1m', 'N/A')} / {report['resources'].get('cpu_load_5m', 'N/A')} / {report['resources'].get('cpu_load_15m', 'N/A')} |
| 内存使用 | {report['resources'].get('memory_percent', 'N/A')}% ({report['resources'].get('memory_used_mb', 'N/A')}MB / {report['resources'].get('memory_total_mb', 'N/A')}MB) |
| 磁盘使用 | {report['resources'].get('disk_used', 'N/A')} ({report['resources'].get('disk_percent', 'N/A')}) |
| 网络连接 | {report['resources'].get('connections', 'N/A')} |
| 进程数 | {report['resources'].get('processes', 'N/A')} |

---

## 🔧 服务状态

**在线**: {report['services']['summary']['online']} / {report['services']['summary']['total']} ({report['services']['summary']['health_percent']}%)

| 服务 | 状态 | 端口 |
|------|------|------|
"""
    
    for name, info in report['services']['services'].items():
        status_icon = "✅" if info["healthy"] else "❌"
        md += f"| {name} | {status_icon} {info['status']} | {info['port']} |\n"
    
    md += f"""
---

## 🚨 告警统计 (过去{hours}小时)

**总计**: {report['alerts'].get('total', 0)} 条

| 级别 | 数量 |
|------|------|
"""
    
    severity_map = {"critical": "🔴 Critical", "error": "🟠 Error", "warning": "🟡 Warning", "info": "🔵 Info"}
    for sev, count in report['alerts'].get('by_severity', {}).items():
        md += f"| {severity_map.get(sev, sev)} | {count} |\n"
    
    if report['alerts'].get('recent'):
        md += f"""
### 最近告警

| 时间 | 级别 | 标题 | 来源 |
|------|------|------|------|
"""
        for a in report['alerts']['recent'][:5]:
            md += f"| {a['time'][:16]} | {a['severity']} | {a['title'][:30]} | {a['source']} |\n"
    
    md += f"""
---

## 📈 健康检查

**整体可用率**: {report['health'].get('overall_uptime_percent', 0)}%

| 服务 | 可用率 | 平均延迟 |
|------|--------|----------|
"""
    
    for svc in report['health'].get('services', [])[:10]:
        status_icon = "✅" if svc['uptime_percent'] >= 99 else "⚠️" if svc['uptime_percent'] >= 95 else "❌"
        md += f"| {svc['service']} | {status_icon} {svc['uptime_percent']}% | {svc['avg_latency_ms']}ms |\n"
    
    md += f"""
---

## 📊 任务与决策统计

| 指标 | 数值 |
|------|------|
| 任务总数 | {report['tasks'].get('total', 0)} |
| 决策总数 | {report['decisions'].get('total', 0)} |
| 工作流总数 | {report['workflows'].get('total', 0)} |
"""
    
    if report['tasks'].get('by_status'):
        md += f"""
### 任务状态分布
"""
        for status, count in report['tasks']['by_status'].items():
            md += f"- {status}: {count}\n"
    
    md += f"""
---

## 💡 健康因素分析

| 因素 | 分数 | 权重 |
|------|------|------|
"""
    
    for f in report['factors']:
        md += f"| {f['name']} | {f['score']}% | {f['weight']*100:.0f}% |\n"
    
    md += f"""
---

## 🎯 当前状态

- **当前世**: 第{report['incarnation']['incarnation']}世
- **夙愿**: {report['incarnation'].get('ambition', 'N/A')}
- **任务状态**: {report['incarnation'].get('task_status', 'N/A')}
- **最后醒来**: {report['incarnation'].get('last_wake', 'N/A')[:19] if report['incarnation'].get('last_wake') else 'N/A'}

---

*🤖 奥创系统总结报告 - 生成于 {timestamp}*
"""
    
    return md, report

# ============= HTTP服务器 =============

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # 获取小时参数
        hours = int(query.get('hours', [24])[0])
        
        if path == '/' or path == '/summary':
            # 综合总结报告
            report = generate_summary_report(hours)
            self.send_json(report)
        
        elif path == '/markdown':
            # Markdown格式报告
            md, _ = generate_markdown_report(hours)
            self.send_response(200)
            self.send_header('Content-Type', 'text/markdown; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(md.encode('utf-8'))
        
        elif path == '/resources':
            self.send_json(get_system_resources())
        
        elif path == '/services':
            self.send_json(get_core_services_status())
        
        elif path == '/alerts':
            self.send_json(get_alert_statistics(hours))
        
        elif path == '/health':
            self.send_json(get_health_check_stats(hours))
        
        elif path == '/tasks':
            self.send_json(get_task_statistics(hours))
        
        elif path == '/decisions':
            self.send_json(get_decision_stats(hours))
        
        elif path == '/workflows':
            self.send_json(get_workflow_stats(hours))
        
        elif path == '/incarnation':
            self.send_json(get_incarnation_info())
        
        elif path == '/health-score':
            report = generate_summary_report(hours)
            self.send_json({
                "score": report['health_score'],
                "status": report['status'],
                "status_cn": report['status_cn'],
                "factors": report['factors']
            })
        
        elif path == '/healthz':
            # 健康检查
            self.send_json({"status": "ok", "port": PORT})
        
        # ========== 增强功能 ==========
        elif path == '/trend':
            # 趋势分析
            self.send_json(get_trend_analysis(hours))
        
        elif path == '/insights':
            # 智能洞察
            self.send_json(get_smart_insights(hours))
        
        elif path == '/report/push':
            # 推送报告到钉钉
            result = push_summary_to_dingtalk(hours)
            self.send_json(result)
        
        elif path == '/full':
            # 完整报告（含趋势和洞察）
            report = generate_summary_report(hours)
            trend = get_trend_analysis(hours)
            insights = get_smart_insights(hours)
            self.send_json({
                "report": report,
                "trend": trend,
                "insights": insights
            })
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"✅ 系统总结报告API服务启动成功")
    print(f"   端口: {PORT}")
    print(f"   端点:")
    print(f"   - GET /              综合总结报告")
    print(f"   - GET /summary       JSON格式总结")
    print(f"   - GET /markdown      Markdown格式报告")
    print(f"   - GET /resources     系统资源")
    print(f"   - GET /services      服务状态")
    print(f"   - GET /alerts        告警统计")
    print(f"   - GET /health        健康检查")
    print(f"   - GET /tasks         任务统计")
    print(f"   - GET /decisions     决策统计")
    print(f"   - GET /workflows     工作流统计")
    print(f"   - GET /incarnation   转世信息")
    print(f"   - GET /health-score  健康分数")
    print(f"   - GET /healthz       健康检查")
    print(f"   - GET /trend         趋势分析")
    print(f"   - GET /insights      智能洞察")
    print(f"   - GET /report/push   推送报告到钉钉")
    print(f"   - GET /full          完整报告(含趋势+洞察)")
    print(f"\n📰 按 Ctrl+C 停止服务")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
        server.shutdown()

if __name__ == "__main__":
    run_server()