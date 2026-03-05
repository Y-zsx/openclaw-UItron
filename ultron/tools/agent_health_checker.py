#!/usr/bin/env python3
"""Agent健康检查与自愈系统"""
import json
import subprocess
import time
from datetime import datetime

# Agent API端点列表
AGENT_ENDPOINTS = {
    "Agent API": "http://localhost:18131",
    "Agent Gateway": "http://localhost:18290",
    "Workflow Engine": "http://localhost:18100",
    "Task Queue": "http://localhost:18180",
    "Service Mesh": "http://localhost:18270",
    "Orchestrator": "http://localhost:18220",
    "Deployment Manager": "http://localhost:18231",
    "Monitor API": "http://localhost:18232",
    "Agent Healer": "http://localhost:18190",  # 可能复用
}

def check_endpoint(name, url):
    """检查单个端点"""
    try:
        start = time.time()
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=5
        )
        elapsed = (time.time() - start) * 1000
        status_code = result.stdout.strip()
        
        if status_code in ["200", "201", "204"]:
            return {"name": name, "status": "healthy", "latency_ms": round(elapsed, 1), "code": status_code}
        else:
            return {"name": name, "status": "degraded", "latency_ms": round(elapsed, 1), "code": status_code}
    except Exception as e:
        return {"name": name, "status": "unhealthy", "error": str(e)}

def check_process_health():
    """检查关键进程"""
    processes = [
        "agent_api_gateway.py",
        "agent_orchestrator.py",
        "agent_interface_server.py",
        "task_queue.py",
        "workflow_engine.py",
        "agent_monitor_api.py",
        "service_mesh.py",
        "agent_scaling_api.py",
        "agent-healer.py",
        "load_balancer_api.py"
    ]
    
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True, text=True
    )
    
    running = []
    for proc in processes:
        if proc in result.stdout:
            running.append(proc)
    
    return running

def main():
    print("=" * 50)
    print("Agent健康检查系统")
    print("=" * 50)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查端点
    print("【端点健康检查】")
    results = []
    for name, url in AGENT_ENDPOINTS.items():
        r = check_endpoint(name, url)
        results.append(r)
        emoji = "✅" if r["status"] == "healthy" else "⚠️" if r["status"] == "degraded" else "❌"
        print(f"  {emoji} {name}: {r['status']} (latency: {r.get('latency_ms', 'N/A')}ms)")
    
    # 检查进程
    print("\n【进程健康检查】")
    running_procs = check_process_health()
    print(f"  运行中: {len(running_procs)}/{len(AGENT_ENDPOINTS)}")
    for proc in running_procs[:10]:
        print(f"    ✅ {proc}")
    
    # 总结
    healthy_count = sum(1 for r in results if r["status"] == "healthy")
    total = len(results)
    health_score = round(healthy_count / total * 100, 1) if total > 0 else 0
    
    print(f"\n【健康评分】: {health_score}% ({healthy_count}/{total})")
    
    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "endpoints": results,
        "processes_running": len(running_procs),
        "health_score": health_score,
        "recommendation": "正常" if health_score > 80 else "需要关注" if health_score > 50 else "需要干预"
    }
    
    with open("/root/.openclaw/workspace/ultron/data/health_check_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n报告已保存: /root/.openclaw/workspace/ultron/data/health_check_report.json")
    print("=" * 50)

if __name__ == "__main__":
    main()