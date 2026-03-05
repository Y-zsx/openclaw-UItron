"""
Agent协作网络移动端适配器
提供移动端优化API、WebSocket实时推送、PWA支持
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from aiohttp import web, WSMsgType
import hashlib


class MobileAPIVersion(Enum):
    V1 = "v1"
    V2 = "v2"


@dataclass
class MobileDevice:
    """移动设备信息"""
    device_id: str
    device_type: str  # ios/android/web
    push_token: Optional[str] = None
    last_active: float = field(default_factory=time.time)
    preferences: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PushNotification:
    """推送通知"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    body: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    priority: str = "normal"  # normal, high
    device_id: Optional[str] = None
    sent_at: Optional[float] = None


class MobileAPIGateway:
    """移动端API网关 - 轻量级移动优先"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8091):
        self.host = host
        self.port = port
        self.app = web.Application()
        self._runner = None
        self._site = None
        
        # 移动设备注册
        self.devices: Dict[str, MobileDevice] = {}
        
        # 推送通知队列
        self.notifications: Dict[str, PushNotification] = {}
        
        # WebSocket连接
        self.ws_connections: Dict[str, web.WebSocketResponse] = {}
        
        # 缓存
        self._cache: Dict[str, tuple] = {}  # key -> (data, expire_time)
        self.cache_ttl = 30  # 30秒缓存
        
        self._setup_routes()
    
    def _setup_routes(self):
        """设置移动端API路由"""
        # 健康检查
        self.app.router.add_get('/health', self.health_check)
        
        # 设备注册
        self.app.router.add_post('/api/v1/device/register', self.register_device)
        self.app.router.add_post('/api/v1/device/unregister', self.unregister_device)
        
        # Agent操作 (移动端简化接口)
        self.app.router.add_get('/api/v1/agents', self.list_agents)
        self.app.router.add_get('/api/v1/agents/{agent_id}', self.get_agent)
        self.app.router.add_post('/api/v1/tasks', self.submit_task)
        self.app.router.add_get('/api/v1/tasks', self.list_tasks)
        self.app.router.add_get('/api/v1/tasks/{task_id}', self.get_task_status)
        
        # 实时推送
        self.app.router.add_get('/api/v1/stream', self.websocket_handler)
        
        # 统计数据
        self.app.router.add_get('/api/v1/stats', self.get_stats)
        
        # 推送通知
        self.app.router.add_post('/api/v1/push/register', self.register_push)
        
        # 移动端首页
        self.app.router.add_get('/', self.mobile_index)
        self.app.router.add_get('/app', self.mobile_app)
    
    async def health_check(self, request):
        """健康检查"""
        return web.json_response({
            "status": "ok",
            "version": "2.0",
            "timestamp": time.time(),
            "devices": len(self.devices),
            "connections": len(self.ws_connections)
        })
    
    async def register_device(self, request):
        """设备注册"""
        data = await request.json()
        device = MobileDevice(
            device_id=data.get('device_id', str(uuid.uuid4())),
            device_type=data.get('device_type', 'web'),
            push_token=data.get('push_token'),
            preferences=data.get('preferences', {})
        )
        self.devices[device.device_id] = device
        return web.json_response({"status": "ok", "device_id": device.device_id})
    
    async def unregister_device(self, request):
        """设备注销"""
        data = await request.json()
        device_id = data.get('device_id')
        if device_id and device_id in self.devices:
            del self.devices[device_id]
        return web.json_response({"status": "ok"})
    
    async def list_agents(self, request):
        """列出Agent (移动端优化)"""
        cache_key = "agents_list"
        cached = self._get_cache(cache_key)
        if cached:
            return web.json_response(cached)
        
        # 简化数据，减少传输
        agents = [
            {
                "id": "monitor",
                "name": "Monitor Agent",
                "status": "running",
                "capabilities": ["monitor", "alert"],
                "load": 0.3
            },
            {
                "id": "executor", 
                "name": "Executor Agent",
                "status": "running",
                "capabilities": ["execute", "run"],
                "load": 0.5
            },
            {
                "id": "analyzer",
                "name": "Analyzer Agent",
                "status": "running",
                "capabilities": ["analyze", "predict"],
                "load": 0.2
            },
            {
                "id": "communicator",
                "name": "Communicator Agent",
                "status": "running",
                "capabilities": ["notify", "message"],
                "load": 0.1
            },
            {
                "id": "coordinator",
                "name": "Coordinator Agent",
                "status": "running",
                "capabilities": ["orchestrate", "coordinate"],
                "load": 0.4
            }
        ]
        
        result = {"agents": agents, "count": len(agents), "timestamp": time.time()}
        self._set_cache(cache_key, result)
        return web.json_response(result)
    
    async def get_agent(self, request):
        """获取单个Agent详情"""
        agent_id = request.match_info['agent_id']
        # 简化返回
        return web.json_response({
            "id": agent_id,
            "status": "running",
            "uptime": 3600,
            "tasks_completed": 100,
            "load": 0.3
        })
    
    async def submit_task(self, request):
        """提交任务"""
        data = await request.json()
        task_id = str(uuid.uuid4())[:8]
        
        task = {
            "id": task_id,
            "agent_id": data.get('agent_id', 'coordinator'),
            "action": data.get('action', 'execute'),
            "payload": data.get('payload', {}),
            "status": "pending",
            "created_at": time.time()
        }
        
        # 广播给WebSocket客户端
        await self._broadcast({"type": "task_created", "task": task})
        
        return web.json_response({"status": "ok", "task_id": task_id})
    
    async def list_tasks(self, request):
        """列出任务"""
        limit = int(request.query.get('limit', 20))
        status = request.query.get('status')
        
        # 模拟任务数据
        tasks = [
            {"id": "task1", "agent_id": "executor", "status": "completed", "created_at": time.time() - 100},
            {"id": "task2", "agent_id": "monitor", "status": "running", "created_at": time.time() - 50},
            {"id": "task3", "agent_id": "analyzer", "status": "pending", "created_at": time.time() - 10},
        ]
        
        if status:
            tasks = [t for t in tasks if t['status'] == status]
        
        return web.json_response({"tasks": tasks[:limit], "count": len(tasks)})
    
    async def get_task_status(self, request):
        """获取任务状态"""
        task_id = request.match_info['task_id']
        return web.json_response({
            "id": task_id,
            "status": "running",
            "progress": 50,
            "result": None
        })
    
    async def websocket_handler(self, request):
        """WebSocket实时推送"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        client_id = str(uuid.uuid4())[:8]
        self.ws_connections[client_id] = ws
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get('type') == 'ping':
                        await ws.send_json({'type': 'pong', 'time': time.time()})
                elif msg.type == WSMsgType.ERROR:
                    break
        finally:
            if client_id in self.ws_connections:
                del self.ws_connections[client_id]
        
        return ws
    
    async def _broadcast(self, message: dict):
        """广播消息给所有WebSocket客户端"""
        for client_id, ws in self.ws_connections.items():
            try:
                await ws.send_json(message)
            except:
                pass
    
    async def get_stats(self, request):
        """获取统计信息"""
        return web.json_response({
            "agents": {"total": 5, "active": 5},
            "tasks": {"pending": 3, "running": 1, "completed": 100},
            "connections": len(self.ws_connections),
            "devices": len(self.devices),
            "timestamp": time.time()
        })
    
    async def register_push(self, request):
        """注册推送"""
        data = await request.json()
        device_id = data.get('device_id')
        if device_id and device_id in self.devices:
            self.devices[device_id].push_token = data.get('push_token')
        return web.json_response({"status": "ok"})
    
    async def mobile_index(self, request):
        """移动端首页"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Agent协作网络</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .header {
            padding: 20px;
            background: rgba(0,0,0,0.3);
            backdrop-filter: blur(10px);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header h1 { font-size: 1.2rem; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            padding: 16px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }
        .stat-value { font-size: 1.8rem; font-weight: bold; color: #00d4ff; }
        .stat-label { font-size: 0.8rem; opacity: 0.7; margin-top: 4px; }
        .agent-list { padding: 0 16px; }
        .agent-card {
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .agent-info h3 { font-size: 1rem; margin-bottom: 4px; }
        .agent-status {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 0.75rem;
            background: #00d4ff22;
            color: #00d4ff;
        }
        .agent-status.running { background: #00ff8822; color: #00ff88; }
        .quick-actions {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            padding: 16px;
        }
        .action-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 12px;
            padding: 16px 8px;
            color: #fff;
            font-size: 0.8rem;
            cursor: pointer;
        }
        .action-btn:active { transform: scale(0.95); }
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: #00d4ff;
            border: none;
            color: #000;
            font-size: 1.5rem;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,212,255,0.4);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Agent协作网络</h1>
    </div>
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value" id="agentCount">5</div>
            <div class="stat-label">活跃Agent</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="taskCount">12</div>
            <div class="stat-label">待处理任务</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="runCount">89</div>
            <div class="stat-label">今日任务</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="connCount">0</div>
            <div class="stat-label">在线设备</div>
        </div>
    </div>
    <div class="quick-actions">
        <button class="action-btn" onclick="submitTask('monitor')">📊 监控</button>
        <button class="action-btn" onclick="submitTask('executor')">⚡ 执行</button>
        <button class="action-btn" onclick="submitTask('analyzer')">📈 分析</button>
    </div>
    <h3 style="padding: 16px 16px 8px;">Agent状态</h3>
    <div class="agent-list" id="agentList"></div>
    <button class="refresh-btn" onclick="refresh()">↻</button>
    <script>
        let ws;
        function connect() {
            ws = new WebSocket(window.location.origin.replace('http','ws') + '/api/v1/stream');
            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.type === 'task_created') showToast('新任务: ' + data.task.id);
            };
        }
        function refresh() {
            fetch('/api/v1/stats').then(r=>r.json()).then(d=>{
                document.getElementById('agentCount').textContent = d.agents.active;
                document.getElementById('taskCount').textContent = d.tasks.pending;
                document.getElementById('runCount').textContent = d.tasks.completed;
                document.getElementById('connCount').textContent = d.connections;
            });
            fetch('/api/v1/agents').then(r=>r.json()).then(d=>{
                document.getElementById('agentList').innerHTML = d.agents.map(a=>\`
                    <div class="agent-card">
                        <div class="agent-info">
                            <h3>\${a.name}</h3>
                            <span class="agent-status \${a.status}">\${a.status}</span>
                        </div>
                        <div style="text-align:right">
                            <div style="font-size:0.9rem;color:#00d4ff">\${Math.round(a.load*100)}%</div>
                            <div style="font-size:0.7rem;opacity:0.6">负载</div>
                        </div>
                    </div>\`).join('');
            });
        }
        function submitTask(agent) {
            fetch('/api/v1/tasks', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({agent_id: agent, action: 'execute', payload:{}})
            }).then(r=>r.json()).then(d=>showToast('任务已提交: '+d.task_id));
        }
        function showToast(msg) {
            const t = document.createElement('div');
            t.textContent = msg;
            t.style = 'position:fixed;top:80px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.8);padding:12px 24px;border-radius:8px;z-index:1000';
            document.body.appendChild(t);
            setTimeout(()=>t.remove(),3000);
        }
        refresh();
        connect();
        setInterval(refresh, 10000);
    </script>
</body>
</html>"""
        return web.Response(text=html, content_type='text/html')
    
    async def mobile_app(self, request):
        """PWA应用入口"""
        manifest = json.dumps({
            "name": "Agent协作网络",
            "short_name": "AgentNet",
            "start_url": "/app",
            "display": "standalone",
            "background_color": "#1a1a2e",
            "theme_color": "#00d4ff",
            "icons": []
        })
        return web.Response(text=manifest, content_type='application/json')
    
    def _get_cache(self, key: str) -> Optional[dict]:
        """获取缓存"""
        if key in self._cache:
            data, expire = self._cache[key]
            if time.time() < expire:
                return data
            del self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: dict):
        """设置缓存"""
        self._cache[key] = (data, time.time() + self.cache_ttl)
    
    async def start(self):
        """启动服务"""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        print(f"🤖 Mobile API Gateway started on http://{self.host}:{self.port}")
    
    async def stop(self):
        """停止服务"""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()


if __name__ == "__main__":
    gateway = MobileAPIGateway(port=8091)
    asyncio.run(gateway.start())