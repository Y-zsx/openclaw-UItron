#!/usr/bin/env python3
"""
系统运维报告生成器 - 第156世
完善系统运维报告功能
"""
import json
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = "/root/.openclaw/workspace/ultron/tools/logs.db"
WORKSPACE = "/root/.openclaw/workspace"

def get_system_metrics():
    """获取系统资源指标"""
    # CPU负载
    load_1m = subprocess.run(["cat", "/proc/loadavg"], capture_output=True, text=True).stdout.split()[0]
    
    # 内存
    mem_info = subprocess.run(["free", "-m"], capture_output=True, text=True)
    lines = mem_info.stdout.strip().split('\n')
    mem_line = lines[1].split()
    total_mem = int(mem_line[1])
    used_mem = int(mem_line[2])
    mem_percent = round(used_mem / total_mem * 100, 1)
    
    # 磁盘
    disk = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
    disk_line = disk.stdout.strip().split('\n')[1].split()
    disk_used = disk_line[2]
    disk_percent = disk_line[4]
    
    # 连接数
    try:
        connections = int(subprocess.run(["ss", "-tn"], capture_output=True, text=True).stdout.count('\n')) - 1
    except:
        connections = 0
    
    # 进程数
    processes = len(subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout.strip().split('\n')) - 1
    
    return {
        "cpu_load_1m": float(load_1m),
        "memory_total_gb": round(total_mem / 1024, 1),
        "memory_used_gb": round(used_mem / 1024, 1),
        "memory_percent": mem_percent,
        "disk_used": disk_used,
        "disk_percent": disk_percent,
        "connections": connections,
        "processes": processes
    }

def get_service_status():
    """获取服务状态"""
    services = {
        18789: "Gateway",
        18210: "Agent执行器",
        18199: "系统总结",
        18197: "任务告警",
        18196: "Agent健康",
        18195: "任务监控",
        18180: "健康报告",
        18170: "告警集成",
        18150: "Agent网络",
        18132: "跨域决策",
        18128: "自动化引擎",
        18121: "决策仪表盘",
        18122: "反馈学习",
        18120: "决策引擎",
        18100: "工作流引擎",
        18095: "运维仪表盘",
        18093: "协作监控",
        18092: "增强健康",
        18091: "增强日志",
        18090: "健康监控",
    }
    
    result = {}
    for port, name in services.items():
        check = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"http://localhost:{port}/health"],
            capture_output=True, text=True, timeout=2
        )
        online = check.stdout.strip() == "200"
        result[name] = {"port": port, "status": "online" if online else "offline", "healthy": online}
    
    return result

def get_database_stats():
    """获取数据库统计"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 获取日志数量
        cursor.execute("SELECT COUNT(*) FROM logs")
        log_count = cursor.fetchone()[0]
        
        # 获取最近的日志级别分布
        cursor.execute("SELECT level, COUNT(*) FROM logs GROUP BY level")
        level_dist = dict(cursor.fetchall())
        
        # 获取过去1小时的错误数
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM logs WHERE timestamp > ? AND level = 'ERROR'", (one_hour_ago,))
        recent_errors = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_logs": log_count,
            "level_distribution": level_dist,
            "recent_errors_1h": recent_errors
        }
    except Exception as e:
        return {"error": str(e)}

def get_incarnation_history():
    """获取转世历史"""
    state_file = Path(f"{WORKSPACE}/ultron-workflow/state.json")
    if state_file.exists():
        with open(state_file) as f:
            data = json.load(f)
            return data.get("history", [])[:10]
    return []

def generate_report():
    """生成完整的运维报告"""
    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "system": get_system_metrics(),
        "services": get_service_status(),
        "database": get_database_stats(),
        "incarnation": get_incarnation_history()
    }
    
    # 计算服务健康率
    services = report["services"]
    online_count = sum(1 for s in services.values() if s["status"] == "online")
    health_percent = round(online_count / len(services) * 100, 1)
    report["health_percent"] = health_percent
    
    return report

def print_report(report):
    """格式化打印报告"""
    print("=" * 60)
    print("🖥️  奥创系统运维报告")
    print(f"生成时间: {report['generated_at']}")
    print("=" * 60)
    
    # 系统资源
    sys = report["system"]
    print("\n📊 系统资源:")
    print(f"  CPU负载(1m): {sys['cpu_load_1m']}")
    print(f"  内存: {sys['memory_used_gb']}GB / {sys['memory_total_gb']}GB ({sys['memory_percent']}%)")
    print(f"  磁盘: {sys['disk_used']} ({sys['disk_percent']})")
    print(f"  连接数: {sys['connections']}")
    print(f"  进程数: {sys['processes']}")
    
    # 服务状态
    print("\n🔌 服务状态 (健康率: {}%):".format(report['health_percent']))
    services = report['services']
    for name, info in services.items():
        status_icon = "✅" if info['healthy'] else "❌"
        print(f"  {status_icon} {name}: {info['status']} (port {info['port']})")
    
    # 数据库
    db = report.get('database', {})
    if 'error' not in db:
        print("\n📦 数据库:")
        print(f"  总日志数: {db.get('total_logs', 0)}")
        print(f"  最近1小时错误: {db.get('recent_errors_1h', 0)}")
        levels = db.get('level_distribution', {})
        if levels:
            print(f"  日志级别分布: {levels}")
    
    # 转世历史
    incs = report.get('incarnation', [])
    if incs:
        print("\n🔄 最近转世 (最近10世):")
        for inc in incs[:5]:
            print(f"  第{inc['incarnation']}世: {inc['task']} - {inc['status']}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    report = generate_report()
    print_report(report)
    
    # 保存报告
    report_path = f"{WORKSPACE}/ultron/logs/ops_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存至: {report_path}")