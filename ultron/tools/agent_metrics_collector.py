#!/usr/bin/env python3
"""
Agent监控与指标收集系统 v1.0
统一指标收集框架，支持多种指标类型：
- 系统指标：CPU、内存、磁盘、网络
- Agent指标：进程状态、生命周期、任务执行
- 运维指标：告警、事件、性能
"""

import json
import os
import sqlite3
import subprocess
import psutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import deque
import time

# 配置
METRICS_DB = Path("/root/.openclaw/workspace/ultron/metrics.db")
REPORTS_DIR = Path("/root/.openclaw/workspace/ultron/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 指标配置
METRICS_CONFIG = {
    "system": {
        "interval": 60,  # 60秒
        "retention_days": 7,
        "enabled": True
    },
    "agent": {
        "interval": 30,  # 30秒
        "retention_days": 14,
        "enabled": True
    },
    "ops": {
        "interval": 120,  # 2分钟
        "retention_days": 30,
        "enabled": True
    }
}

# 内存缓存（最近1小时）
CACHE_SIZE = 3600
_metrics_cache = {
    "system": deque(maxlen=CACHE_SIZE),
    "agent": deque(maxlen=CACHE_SIZE),
    "ops": deque(maxlen=CACHE_SIZE)
}


def init_db():
    """初始化指标数据库"""
    conn = sqlite3.connect(METRICS_DB)
    c = conn.cursor()
    
    # 系统指标表
    c.execute('''CREATE TABLE IF NOT EXISTS system_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        cpu_percent REAL,
        memory_percent REAL,
        memory_available_gb REAL,
        disk_percent REAL,
        disk_io_read_mb REAL,
        disk_io_write_mb REAL,
        network_sent_mb REAL,
        network_recv_mb REAL,
        load_avg_1m REAL,
        load_avg_5m REAL,
        load_avg_15m REAL,
        process_count INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Agent指标表
    c.execute('''CREATE TABLE IF NOT EXISTS agent_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        agent_id TEXT,
        agent_name TEXT,
        status TEXT,
        cpu_percent REAL,
        memory_percent REAL,
        memory_mb REAL,
        pid INTEGER,
        uptime_seconds REAL,
        tasks_total INTEGER,
        tasks_completed INTEGER,
        tasks_failed INTEGER,
        last_task_time TEXT,
        health_score REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 运维指标表
    c.execute('''CREATE TABLE IF NOT EXISTS ops_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        metric_type TEXT,
        metric_name TEXT,
        value REAL,
        unit TEXT,
        tags TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 创建索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_system_ts ON system_metrics(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_agent_ts ON agent_metrics(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_agent_id ON agent_metrics(agent_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_ops_ts ON ops_metrics(timestamp)')
    
    conn.commit()
    conn.close()
    print(f"✅ 指标数据库初始化完成: {METRICS_DB}")


def collect_system_metrics() -> Dict[str, Any]:
    """收集系统指标"""
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # IO统计
    try:
        disk_io = psutil.disk_io_counters()
        disk_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0
        disk_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0
    except:
        disk_read_mb = disk_write_mb = 0
    
    # 网络统计
    try:
        net_io = psutil.net_io_counters()
        net_sent_mb = net_io.bytes_sent / (1024 * 1024) if net_io else 0
        net_recv_mb = net_io.bytes_recv / (1024 * 1024) if net_io else 0
    except:
        net_sent_mb = net_recv_mb = 0
    
    # 负载
    try:
        load_avg = os.getloadavg()
    except:
        load_avg = (0, 0, 0)
    
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": round(cpu_percent, 2),
        "memory_percent": round(mem.percent, 2),
        "memory_available_gb": round(mem.available / (1024**3), 2),
        "disk_percent": disk.percent,
        "disk_io_read_mb": round(disk_read_mb, 2),
        "disk_io_write_mb": round(disk_write_mb, 2),
        "network_sent_mb": round(net_sent_mb, 2),
        "network_recv_mb": round(net_recv_mb, 2),
        "load_avg_1m": round(load_avg[0], 2),
        "load_avg_5m": round(load_avg[1], 2),
        "load_avg_15m": round(load_avg[2], 2),
        "process_count": len(psutil.pids())
    }
    
    # 缓存
    _metrics_cache["system"].append(metrics)
    
    return metrics


def collect_agent_metrics() -> List[Dict[str, Any]]:
    """收集Agent指标"""
    agents = []
    AGENT_KEYWORDS = ["python", "node", "openclaw", "agent", "cron", "ultron"]
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent', 'create_time']):
        try:
            pinfo = proc.info
            cmdline = ' '.join(pinfo.get('cmdline', []))
            name = pinfo.get('name', '')
            
            if any(kw in cmdline.lower() or kw in name.lower() for kw in AGENT_KEYWORDS):
                uptime = time.time() - pinfo.get('create_time', time.time())
                
                agent = {
                    "timestamp": datetime.now().isoformat(),
                    "agent_id": str(pinfo.get('pid')),
                    "agent_name": name,
                    "status": "running" if proc.is_running() else "stopped",
                    "cpu_percent": round(pinfo.get('cpu_percent', 0), 2),
                    "memory_percent": round(pinfo.get('memory_percent', 0), 2),
                    "memory_mb": round(proc.memory_info().rss / (1024 * 1024), 2),
                    "pid": pinfo.get('pid'),
                    "uptime_seconds": round(uptime, 0),
                    "tasks_total": 0,
                    "tasks_completed": 0,
                    "tasks_failed": 0,
                    "last_task_time": None,
                    "health_score": calculate_agent_health(pinfo.get('cpu_percent', 0), pinfo.get('memory_percent', 0))
                }
                agents.append(agent)
                _metrics_cache["agent"].append(agent)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return agents


def calculate_agent_health(cpu: float, memory: float) -> float:
    """计算Agent健康评分"""
    score = 100
    if cpu > 80:
        score -= 30
    elif cpu > 50:
        score -= 15
    
    if memory > 80:
        score -= 30
    elif memory > 60:
        score -= 15
    
    return max(0, round(score, 1))


def collect_ops_metrics() -> Dict[str, Any]:
    """收集运维指标"""
    ops_data = {
        "timestamp": datetime.now().isoformat(),
        "metrics": []
    }
    
    # OpenClaw状态
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            status = json.loads(result.stdout)
            ops_data["metrics"].append({
                "type": "openclaw",
                "name": "gateway_status",
                "value": 1 if status.get("gateway", {}).get("running") else 0,
                "unit": "bool"
            })
    except:
        ops_data["metrics"].append({
            "type": "openclaw",
            "name": "gateway_status",
            "value": 0,
            "unit": "bool"
        })
    
    # Cron任务数
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list"],
            capture_output=True, text=True, timeout=10
        )
        cron_count = len([l for l in result.stdout.split('\n') if 'cron' in l.lower()])
        ops_data["metrics"].append({
            "type": "cron",
            "name": "active_jobs",
            "value": cron_count,
            "unit": "count"
        })
    except:
        pass
    
    # 内存缓存
    ops_data["metrics"].append({
        "type": "cache",
        "name": "system_metrics_buffer",
        "value": len(_metrics_cache["system"]),
        "unit": "count"
    })
    ops_data["metrics"].append({
        "type": "cache",
        "name": "agent_metrics_buffer",
        "value": len(_metrics_cache["agent"]),
        "unit": "count"
    })
    
    _metrics_cache["ops"].append(ops_data)
    return ops_data


def save_metrics(metrics_type: str, data: Any):
    """保存指标到数据库"""
    conn = sqlite3.connect(METRICS_DB)
    c = conn.cursor()
    
    if metrics_type == "system":
        c.execute('''INSERT INTO system_metrics 
            (timestamp, cpu_percent, memory_percent, memory_available_gb, disk_percent,
             disk_io_read_mb, disk_io_write_mb, network_sent_mb, network_recv_mb,
             load_avg_1m, load_avg_5m, load_avg_15m, process_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (data["timestamp"], data["cpu_percent"], data["memory_percent"],
             data["memory_available_gb"], data["disk_percent"], data["disk_io_read_mb"],
             data["disk_io_write_mb"], data["network_sent_mb"], data["network_recv_mb"],
             data["load_avg_1m"], data["load_avg_5m"], data["load_avg_15m"], data["process_count"])
        )
    
    elif metrics_type == "agent":
        c.execute('''INSERT INTO agent_metrics
            (timestamp, agent_id, agent_name, status, cpu_percent, memory_percent,
             memory_mb, pid, uptime_seconds, tasks_total, tasks_completed, tasks_failed,
             last_task_time, health_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (data["timestamp"], data["agent_id"], data["agent_name"], data["status"],
             data["cpu_percent"], data["memory_percent"], data["memory_mb"], data["pid"],
             data["uptime_seconds"], data["tasks_total"], data["tasks_completed"],
             data["tasks_failed"], data["last_task_time"], data["health_score"])
        )
    
    elif metrics_type == "ops":
        for m in data.get("metrics", []):
            c.execute('''INSERT INTO ops_metrics
                (timestamp, metric_type, metric_name, value, unit, tags)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (data["timestamp"], m.get("type"), m.get("name"), m.get("value"), m.get("unit"), json.dumps({}))
            )
    
    conn.commit()
    conn.close()


def query_metrics(metrics_type: str, since: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """查询指标历史"""
    conn = sqlite3.connect(METRICS_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    table_map = {
        "system": "system_metrics",
        "agent": "agent_metrics",
        "ops": "ops_metrics"
    }
    
    table = table_map.get(metrics_type)
    if not table:
        return []
    
    if since:
        c.execute(f"SELECT * FROM {table} WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?", 
                  (since, limit))
    else:
        c.execute(f"SELECT * FROM {table} ORDER BY timestamp DESC LIMIT ?", (limit,))
    
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_current_metrics() -> Dict[str, Any]:
    """获取当前所有指标（从缓存）"""
    return {
        "system": _metrics_cache["system"][-1] if _metrics_cache["system"] else None,
        "agent": list(_metrics_cache["agent"])[-10:] if _metrics_cache["agent"] else [],
        "ops": _metrics_cache["ops"][-1] if _metrics_cache["ops"] else None,
        "cache_size": {
            "system": len(_metrics_cache["system"]),
            "agent": len(_metrics_cache["agent"]),
            "ops": len(_metrics_cache["ops"])
        }
    }


def run_collection_cycle():
    """运行一轮指标收集"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 开始收集指标...")
    
    # 系统指标
    try:
        sys_metrics = collect_system_metrics()
        save_metrics("system", sys_metrics)
        print(f"  📊 系统: CPU {sys_metrics['cpu_percent']}%, MEM {sys_metrics['memory_percent']}%, DISK {sys_metrics['disk_percent']}%")
    except Exception as e:
        print(f"  ❌ 系统指标收集失败: {e}")
    
    # Agent指标
    try:
        agent_metrics = collect_agent_metrics()
        for agent in agent_metrics:
            save_metrics("agent", agent)
        print(f"  🤖 Agent: {len(agent_metrics)} 个进程")
    except Exception as e:
        print(f"  ❌ Agent指标收集失败: {e}")
    
    # 运维指标
    try:
        ops_metrics = collect_ops_metrics()
        save_metrics("ops", ops_metrics)
        print(f"  ⚙️ 运维: {len(ops_metrics.get('metrics', []))} 项")
    except Exception as e:
        print(f"  ❌ 运维指标收集失败: {e}")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 指标收集完成")


def cleanup_old_metrics():
    """清理过期指标"""
    conn = sqlite3.connect(METRICS_DB)
    c = conn.cursor()
    
    for metric_type, config in METRICS_CONFIG.items():
        retention = config["retention_days"]
        cutoff = (datetime.now() - timedelta(days=retention)).isoformat()
        
        table_map = {
            "system": "system_metrics",
            "agent": "agent_metrics",
            "ops": "ops_metrics"
        }
        
        table = table_map.get(metric_type)
        if table:
            c.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))
    
    conn.commit()
    deleted = c.rowcount
    conn.close()
    
    if deleted > 0:
        print(f"🗑️ 清理了 {deleted} 条过期指标")


def export_metrics_json(output_path: str = None):
    """导出指标到JSON"""
    if not output_path:
        output_path = REPORTS_DIR / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    data = {
        "export_time": datetime.now().isoformat(),
        "current": get_current_metrics(),
        "recent_system": query_metrics("system", limit=60),
        "recent_agent": query_metrics("agent", limit=50),
        "recent_ops": query_metrics("ops", limit=30)
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    return str(output_path)


def generate_summary_report() -> str:
    """生成指标摘要报告"""
    current = get_current_metrics()
    sys = current.get("system", {})
    
    report = f"""
╔══════════════════════════════════════════════════════════╗
║         Agent监控与指标收集系统 - 实时报告               ║
║                  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                       ║
╠══════════════════════════════════════════════════════════╣
║  系统指标                                                ║
║  ├─ CPU:     {sys.get('cpu_percent', 'N/A'):>6}%                              ║
║  ├─ 内存:    {sys.get('memory_percent', 'N/A'):>6}%                              ║
║  ├─ 可用内存: {sys.get('memory_available_gb', 'N/A'):>5.1f} GB                        ║
║  ├─ 磁盘:    {sys.get('disk_percent', 'N/A'):>6}%                              ║
║  ├─ 负载:    {sys.get('load_avg_1m', 'N/A'):>6} / {sys.get('load_avg_5m', 'N/A'):>5} / {sys.get('load_avg_15m', 'N/A'):>5}             ║
║  └─ 进程数:  {sys.get('process_count', 'N/A'):>6}                              ║
╠══════════════════════════════════════════════════════════╣
║  缓存状态                                                ║
║  ├─ 系统指标:  {current['cache_size']['system']:>4} 条                        ║
║  ├─ Agent指标: {current['cache_size']['agent']:>4} 条                        ║
║  └─ 运维指标:  {current['cache_size']['ops']:>4} 条                        ║
╚══════════════════════════════════════════════════════════╝
"""
    return report


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent监控与指标收集系统")
    parser.add_argument("--init", action="store_true", help="初始化数据库")
    parser.add_argument("--collect", action="store_true", help="执行一次收集")
    parser.add_argument("--report", action="store_true", help="生成报告")
    parser.add_argument("--export", action="store_true", help="导出JSON")
    parser.add_argument("--cleanup", action="store_true", help="清理过期数据")
    parser.add_argument("--query", choices=["system", "agent", "ops"], help="查询指标")
    parser.add_argument("--limit", type=int, default=10, help="查询限制")
    parser.add_argument("--daemon", action="store_true", help="守护进程模式")
    parser.add_argument("--interval", type=int, default=60, help="收集间隔(秒)")
    
    args = parser.parse_args()
    
    if args.init:
        init_db()
    elif args.collect:
        init_db()
        run_collection_cycle()
    elif args.report:
        print(generate_summary_report())
    elif args.export:
        path = export_metrics_json()
        print(f"✅ 指标已导出: {path}")
    elif args.cleanup:
        cleanup_old_metrics()
    elif args.query:
        init_db()
        results = query_metrics(args.query, limit=args.limit)
        print(json.dumps(results, indent=2, default=str))
    elif args.daemon:
        init_db()
        print("🚀 启动指标收集守护进程...")
        cleanup_old_metrics()
        while True:
            run_collection_cycle()
            time.sleep(args.interval)
    else:
        # 默认显示报告
        init_db()
        run_collection_cycle()
        print(generate_summary_report())