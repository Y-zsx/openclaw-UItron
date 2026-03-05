#!/usr/bin/env python3
"""
健康检测API服务
端口: 8098
"""

import asyncio
import json
from aiohttp import web
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from health_monitor import HealthMonitor, get_monitor, HealthStatus

monitor = get_monitor()

async def health_handler(request):
    """健康检查端点"""
    return web.json_response({"status": "ok", "service": "health-monitor"})

async def status_handler(request):
    """获取所有服务状态"""
    return web.json_response(monitor.get_status())

async def check_handler(request):
    """手动触发检测"""
    results = await monitor.check_all()
    return web.json_response({
        k: {
            "status": v.status.value,
            "response_time": round(v.response_time, 3),
            "timestamp": v.timestamp,
            "error": v.error
        } for k, v in results.items()
    })

async def add_service_handler(request):
    """添加服务"""
    data = await request.json()
    from health_monitor import ServiceEndpoint
    monitor.add_service(ServiceEndpoint(
        name=data["name"],
        port=data["port"],
        health_check_path=data.get("path", "/health"),
        max_response_time=data.get("timeout", 2.0)
    ))
    return web.json_response({"status": "added", "name": data["name"]})

async def start_handler(request):
    """启动监控"""
    monitor.start()
    return web.json_response({"status": "started"})

async def stop_handler(request):
    """停止监控"""
    monitor.stop()
    return web.json_response({"status": "stopped"})

async def history_handler(request):
    """获取历史"""
    service = request.query.get("service")
    limit = int(request.query.get("limit", 50))
    
    if service and service in monitor.health_history:
        history = monitor.health_history[service][-limit:]
    else:
        history = []
        for h in monitor.health_history.values():
            history.extend(h[-limit:])
        history.sort(key=lambda x: x.timestamp, reverse=True)
        history = history[:limit]
    
    return web.json_response([{
        "service": h.service,
        "status": h.status.value,
        "response_time": round(h.response_time, 3),
        "timestamp": h.timestamp
    } for h in history])

async def alerts_handler(request):
    """获取告警"""
    return web.json_response(monitor.alert_manager.alerts[-20:])

def create_app():
    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/status", status_handler)
    app.router.add_post("/check", check_handler)
    app.router.add_post("/service", add_service_handler)
    app.router.add_post("/start", start_handler)
    app.router.add_post("/stop", stop_handler)
    app.router.add_get("/history", history_handler)
    app.router.add_get("/alerts", alerts_handler)
    return app

async def main():
    print("Starting health monitor API on port 8098...")
    monitor.start()
    # 启动后台检测
    asyncio.create_task(monitor.monitor_loop())
    
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8098)
    await site.start()
    print("Health monitor API running on http://0.0.0.0:8098")
    
    # 保持运行
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())