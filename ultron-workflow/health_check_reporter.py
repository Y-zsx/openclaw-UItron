#!/usr/bin/env python3
"""健康检查报告生成器"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

LOG_FILE = Path(__file__).parent / "logs" / "health_check_log.json"

def add_log(entry: dict):
    """添加日志条目"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"logs": [], "metadata": {}}
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            data = json.load(f)
    
    entry["timestamp"] = datetime.now().isoformat()
    data["logs"].append(entry)
    
    # 保留最近1000条
    if len(data["logs"]) > 1000:
        data["logs"] = data["logs"][-1000:]
    
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def generate_report(hours: int = 24) -> dict:
    """生成报告"""
    if not LOG_FILE.exists():
        return {"error": "No logs available"}
    
    with open(LOG_FILE) as f:
        data = json.load(f)
    
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = [l for l in data["logs"] if datetime.fromisoformat(l["timestamp"]) > cutoff]
    
    summary = {
        "period": f"{hours}h",
        "total_checks": len(recent),
        "healthy": len([l for l in recent if l.get("status") == "healthy"]),
        "unhealthy": len([l for l in recent if l.get("status") == "unhealthy"]),
        "services": {}
    }
    
    for log in recent:
        svc = log.get("service", "unknown")
        if svc not in summary["services"]:
            summary["services"][svc] = {"healthy": 0, "unhealthy": 0}
        status = log.get("status", "unknown")
        if status in summary["services"][svc]:
            summary["services"][svc][status] += 1
    
    return summary

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        print(json.dumps(generate_report(int(sys.argv[2] if len(sys.argv) > 2 else 24)), indent=2))
    else:
        add_log({"service": "reporter", "status": "healthy", "message": "Report module ready"})
        print("Health check reporter initialized")