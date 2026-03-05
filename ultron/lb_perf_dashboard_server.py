#!/usr/bin/env python3
"""
负载均衡性能仪表板静态文件服务
===============================
端口: 18234
"""

import os
from aiohttp import web

routes = web.RouteTableDef()

DASHBOARD_FILE = "/root/.openclaw/workspace/ultron/lb_perf_dashboard.html"


@routes.get("/health")
async def health(request):
    return web.json_response({"status": "ok", "service": "lb-perf-dashboard"})


@routes.get("/")
async def dashboard(request):
    """加载仪表板"""
    try:
        with open(DASHBOARD_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(text=content, content_type='text/html')
    except Exception as e:
        return web.Response(text=f"Error: {e}", status=500)


@routes.get("/api/lb-data")
async def lb_data(request):
    """获取负载均衡数据 - 代理到8093"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8093/api/agents") as resp:
            data = await resp.json()
    return web.json_response(data)


@routes.get("/api/lb-stats")
async def lb_stats(request):
    """获取负载均衡统计"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8093/api/stats") as resp:
            data = await resp.json()
    return web.json_response(data)


@routes.get("/api/failover-status")
async def failover_status(request):
    """获取故障转移状态"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8093/api/failover/status") as resp:
            data = await resp.json()
    return web.json_response(data)


@routes.get("/api/perf-metrics")
async def perf_metrics(request):
    """获取性能指标"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:18141/metrics") as resp:
            data = await resp.json()
    return web.json_response(data)


@routes.get("/api/optimizer-analysis")
async def optimizer_analysis(request):
    """获取优化分析"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:18142/api/analysis") as resp:
            data = await resp.json()
    return web.json_response(data)


@routes.put("/api/strategy")
async def set_strategy(request):
    """设置负载均衡策略"""
    import aiohttp
    data = await request.json()
    async with aiohttp.ClientSession() as session:
        async with session.put("http://localhost:8093/api/strategy", json=data) as resp:
            result = await resp.json()
    return web.json_response(result)


def create_app():
    app = web.Application()
    app.add_routes(routes)
    return app


if __name__ == "__main__":
    print("🚀 负载均衡性能仪表板 - http://0.0.0.0:18234")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=18234)