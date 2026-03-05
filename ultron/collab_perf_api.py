#!/usr/bin/env python3
"""
Agent协作网络性能监控API
Port: 18141
"""

import json
import time
import asyncio
from aiohttp import web
import sys
sys.path.insert(0, "/root/.openclaw/workspace/ultron")

from collab_perf_monitor import get_monitor
from collab_perf_optimizer import get_optimizer

routes = web.RouteTableDef()
monitor = get_monitor()
optimizer = get_optimizer()

@routes.get("/health")
async def health(request):
    return web.json_response({"status": "ok", "service": "collab-perf-monitor"})

@routes.get("/metrics")
async def metrics(request):
    """获取性能指标"""
    return web.json_response(monitor.export_metrics())

@routes.get("/metrics/{metric_type}")
async def metric_detail(request):
    """获取特定指标详情"""
    metric_type = request.match_info["metric_type"]
    window = int(request.query.get("window", 300))
    return web.json_response(monitor.get_statistics(metric_type, window))

@routes.get("/endpoints")
async def endpoints(request):
    """获取各端点性能"""
    return web.json_response(monitor.get_endpoint_stats())

@routes.get("/stats")
async def stats(request):
    """获取优化器统计"""
    return web.json_response(optimizer.get_stats())

@routes.post("/record")
async def record_metric(request):
    """记录指标"""
    data = await request.json()
    monitor.record_metric(
        data.get("type", "custom"),
        data.get("value", 0),
        data.get("tags", {})
    )
    return web.json_response({"status": "recorded"})

@routes.post("/record-request")
async def record_request(request):
    """记录API请求"""
    data = await request.json()
    monitor.record_request(
        data.get("endpoint", "/"),
        data.get("duration_ms", 0),
        data.get("status", 200)
    )
    return web.json_response({"status": "recorded"})

@routes.get("/cache/stats")
async def cache_stats(request):
    """缓存统计"""
    return web.json_response(monitor.get_cache_stats())

@routes.post("/cache/invalidate")
async def cache_invalidate(request):
    """缓存失效"""
    data = await request.json()
    pattern = data.get("pattern", "")
    optimizer.cache.invalidate_pattern(pattern)
    return web.json_response({"status": "invalidated", "pattern": pattern})

@routes.get("/rate-limit/{client_id}")
async def rate_limit_status(request):
    """速率限制状态"""
    client_id = request.match_info["client_id"]
    remaining = optimizer.rate_limiter.get_remaining(client_id)
    return web.json_response({
        "client_id": client_id,
        "remaining": remaining,
        "limit": optimizer.rate_limiter.rpm
    })


async def background_monitor():
    """后台监控任务"""
    while True:
        await asyncio.sleep(30)
        health = monitor.check_health()
        if health.get("alerts"):
            print(f"[PERF-MONITOR] Alerts: {health['alerts']}")


def create_app():
    app = web.Application()
    app.add_routes(routes)
    return app


async def start_background(app):
    asyncio.create_task(background_monitor())


if __name__ == "__main__":
    app = create_app()
    app.on_startup.append(start_background)
    
    print("🚀 Agent协作网络性能监控服务启动 - Port 18141")
    web.run_app(app, host="0.0.0.0", port=18141)