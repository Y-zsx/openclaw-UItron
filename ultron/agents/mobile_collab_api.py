#!/usr/bin/env python3
"""
移动端适配Agent协作网络API
第40世: Agent协作网络移动端适配与API增强

移动端优化:
- 摘要模式 (summary mode) - 返回精简数据
- 分页支持 - 高效加载大量数据
- 压缩传输 - gzip压缩支持
- 离线同步 - 增量同步机制
- Server-Sent Events - 实时推送

API增强:
- 批量操作 - 批量注册/更新/删除
- 过滤器增强 - 复杂查询
- 事件流 - 实时状态更新
- 速率限制 - 保护服务
"""

import json
import gzip
import time
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from flask import Flask, request, jsonify, Response, stream_with_context
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mobile-collab-api")

app = Flask(__name__)

# ========== 数据模型 ==========

@dataclass
class MobileAgent:
    """移动端Agent（精简版）"""
    agent_id: str
    status: str
    capabilities: List[str]
    last_heartbeat: float
    health_score: float = 100.0
    group_id: str = None
    
    def to_summary(self) -> Dict:
        """摘要模式 - 最小数据"""
        return {
            "id": self.agent_id,
            "s": self.status,
            "c": len(self.capabilities),
            "h": int(self.health_score),
            "t": int(self.last_heartbeat)
        }
    
    def to_compact(self) -> Dict:
        """紧凑模式"""
        return {
            "id": self.agent_id,
            "status": self.status,
            "capabilities": self.capabilities[:3],  # 限制3个
            "health": int(self.health_score),
            "heartbeat": int(self.last_heartbeat),
            "group": self.group_id
        }
    
    def to_full(self) -> Dict:
        """完整模式"""
        return asdict(self)


@dataclass
class MobileTask:
    """移动端任务"""
    task_id: str
    task_type: str
    status: str
    priority: int
    created_at: float
    assigned_agent: str = None
    result: str = None
    error: str = None
    
    def to_summary(self) -> Dict:
        return {
            "id": self.task_id,
            "t": self.task_type,
            "s": self.status,
            "p": self.priority
        }
    
    def to_compact(self) -> Dict:
        return {
            "id": self.task_id,
            "type": self.task_type,
            "status": self.status,
            "priority": self.priority,
            "created": int(self.created_at),
            "assigned": self.assigned_agent
        }


# ========== 核心类 ==========

class MobileCollabAPI:
    """移动端协作API"""
    
    def __init__(self):
        self.agents: Dict[str, MobileAgent] = {}
        self.tasks: Dict[str, MobileTask] = {}
        self.groups: Dict[str, Dict] = {}
        self.sync_tokens: Dict[str, float] = {}  # 客户端 -> 最后同步时间
        
        # 统计
        self.stats = {
            "requests": 0,
            "summary_requests": 0,
            "compact_requests": 0,
            "full_requests": 0,
            "errors": 0,
            "bytes_sent": 0
        }
        
        # 速率限制
        self.rate_limits: Dict[str, List[float]] = defaultdict(list)
        self.RATE_LIMIT = 60  # 每分钟60次
        self.RATE_WINDOW = 60
        
        # 事件订阅
        self.subscriptions: Dict[str, List[str]] = defaultdict(list)
        
        # 初始化
        self._init_demo_data()
        logger.info("移动端协作API初始化完成")
    
    def _init_demo_data(self):
        """初始化演示数据"""
        # 添加一些示例Agent
        demo_agents = [
            MobileAgent("agent-monitor-01", "active", ["monitor", "collect"], time.time(), 95.0, "monitor-group"),
            MobileAgent("agent-exec-01", "active", ["execute", "deploy"], time.time(), 88.0, "execution-group"),
            MobileAgent("agent-analyze-01", "idle", ["analyze", "predict"], time.time(), 92.0, "analysis-group"),
            MobileAgent("agent-monitor-02", "busy", ["monitor", "alert"], time.time(), 78.0, "monitor-group"),
            MobileAgent("agent-exec-02", "active", ["execute", "repair"], time.time(), 99.0, "execution-group"),
        ]
        for agent in demo_agents:
            self.agents[agent.agent_id] = agent
        
        # 添加示例组
        self.groups = {
            "monitor-group": {"id": "monitor-group", "name": "监控组", "count": 2},
            "execution-group": {"id": "execution-group", "name": "执行组", "count": 2},
            "analysis-group": {"id": "analysis-group", "name": "分析组", "count": 1}
        }
        
        # 添加示例任务
        demo_tasks = [
            MobileTask("task-001", "monitor", "completed", 5, time.time() - 3600, "agent-monitor-01"),
            MobileTask("task-002", "deploy", "running", 8, time.time() - 1800, "agent-exec-01"),
            MobileTask("task-003", "analyze", "pending", 3, time.time() - 600),
            MobileTask("task-004", "repair", "pending", 7, time.time() - 300),
        ]
        for task in demo_tasks:
            self.tasks[task.task_id] = task
        
        logger.info(f"演示数据: {len(self.agents)} agents, {len(self.tasks)} tasks")
    
    def _check_rate_limit(self, client_id: str) -> bool:
        """检查速率限制"""
        now = time.time()
        # 清理旧记录
        self.rate_limits[client_id] = [t for t in self.rate_limits[client_id] if now - t < self.RATE_WINDOW]
        
        if len(self.rate_limits[client_id]) >= self.RATE_LIMIT:
            return False
        
        self.rate_limits[client_id].append(now)
        return True
    
    def _get_response_mode(self) -> str:
        """获取响应模式"""
        mode = request.args.get('mode', 'full')
        if mode not in ['summary', 'compact', 'full']:
            mode = 'full'
        
        # 统计
        if mode == 'summary':
            self.stats['summary_requests'] += 1
        elif mode == 'compact':
            self.stats['compact_requests'] += 1
        else:
            self.stats['full_requests'] += 1
        
        return mode
    
    # ========== Agent操作 ==========
    
    def register_agent(self, agent_id: str, capabilities: List[str], 
                       group_id: str = None, metadata: Dict = None) -> Dict:
        """注册Agent"""
        if agent_id in self.agents:
            return {"success": False, "error": "Agent已存在"}
        
        agent = MobileAgent(
            agent_id=agent_id,
            status="active",
            capabilities=capabilities,
            last_heartbeat=time.time(),
            health_score=100.0,
            group_id=group_id
        )
        self.agents[agent_id] = agent
        return {"success": True, "agent_id": agent_id}
    
    def batch_register_agents(self, agents: List[Dict]) -> Dict:
        """批量注册Agent"""
        results = []
        for item in agents:
            result = self.register_agent(
                item.get('agent_id', f"agent-{uuid.uuid4().hex[:8]}"),
                item.get('capabilities', []),
                item.get('group_id')
            )
            results.append(result)
        
        success = sum(1 for r in results if r.get('success'))
        return {
            "total": len(agents),
            "success": success,
            "failed": len(agents) - success,
            "results": results
        }
    
    def heartbeat(self, agent_id: str, status: str = None, 
                  health_score: float = None) -> Dict:
        """Agent心跳"""
        if agent_id not in self.agents:
            return {"success": False, "error": "Agent不存在"}
        
        agent = self.agents[agent_id]
        agent.last_heartbeat = time.time()
        
        if status:
            agent.status = status
        if health_score is not None:
            agent.health_score = health_score
        
        return {"success": True, "timestamp": agent.last_heartbeat}
    
    def list_agents(self, group_id: str = None, status: str = None,
                    page: int = 1, page_size: int = 20) -> Dict:
        """列出Agent（支持分页）"""
        agents = list(self.agents.values())
        
        if group_id:
            agents = [a for a in agents if a.group_id == group_id]
        if status:
            agents = [a for a in agents if a.status == status]
        
        total = len(agents)
        start = (page - 1) * page_size
        end = start + page_size
        agents_page = agents[start:end]
        
        mode = self._get_response_mode()
        
        if mode == 'summary':
            data = [a.to_summary() for a in agents_page]
        elif mode == 'compact':
            data = [a.to_compact() for a in agents_page]
        else:
            data = [a.to_full() for a in agents_page]
        
        return {
            "data": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            },
            "mode": mode
        }
    
    def batch_update_agents(self, updates: List[Dict]) -> Dict:
        """批量更新Agent状态"""
        results = []
        for item in updates:
            agent_id = item.get('agent_id')
            if agent_id in self.agents:
                agent = self.agents[agent_id]
                if 'status' in item:
                    agent.status = item['status']
                if 'health_score' in item:
                    agent.health_score = item['health_score']
                results.append({"agent_id": agent_id, "success": True})
            else:
                results.append({"agent_id": agent_id, "success": False, "error": "not found"})
        
        return {"results": results, "total": len(results)}
    
    # ========== 任务操作 ==========
    
    def create_task(self, task_type: str, payload: Dict = None,
                   priority: int = 5, group_id: str = None) -> Dict:
        """创建任务"""
        task_id = f"task-{uuid.uuid4().hex[:10]}"
        task = MobileTask(
            task_id=task_id,
            task_type=task_type,
            status="pending",
            priority=priority,
            created_at=time.time(),
            assigned_agent=None
        )
        self.tasks[task_id] = task
        
        return {"success": True, "task_id": task_id, "status": "pending"}
    
    def list_tasks(self, status: str = None, agent_id: str = None,
                   page: int = 1, page_size: int = 20) -> Dict:
        """列出任务"""
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        if agent_id:
            tasks = [t for t in tasks if t.assigned_agent == agent_id]
        
        total = len(tasks)
        start = (page - 1) * page_size
        end = start + page_size
        tasks_page = sorted(tasks, key=lambda t: t.created_at, reverse=True)[start:end]
        
        mode = self._get_response_mode()
        
        if mode == 'summary':
            data = [t.to_summary() for t in tasks_page]
        elif mode == 'compact':
            data = [t.to_compact() for t in tasks_page]
        else:
            data = [asdict(t) for t in tasks_page]
        
        return {
            "data": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            }
        }
    
    def batch_create_tasks(self, tasks: List[Dict]) -> Dict:
        """批量创建任务"""
        results = []
        for item in tasks:
            result = self.create_task(
                item.get('task_type', 'default'),
                item.get('payload'),
                item.get('priority', 5),
                item.get('group_id')
            )
            results.append(result)
        
        return {
            "total": len(tasks),
            "created": sum(1 for r in results if r.get('success')),
            "results": results
        }
    
    # ========== 同步操作 ==========
    
    def sync(self, client_token: str, since: float = 0) -> Dict:
        """增量同步"""
        self.sync_tokens[client_token] = time.time()
        
        # 获取自上次同步以来的变化
        updated_agents = []
        for agent in self.agents.values():
            if agent.last_heartbeat > since:
                updated_agents.append(agent.to_compact())
        
        updated_tasks = []
        for task in self.tasks.values():
            if task.created_at > since:
                updated_tasks.append(task.to_compact())
        
        # 生成新的同步token
        sync_token = hashlib.sha256(f"{time.time()}{client_token}".encode()).hexdigest()[:16]
        
        return {
            "sync_token": sync_token,
            "timestamp": time.time(),
            "changes": {
                "agents": updated_agents,
                "tasks": updated_tasks
            },
            "stats": {
                "total_agents": len(self.agents),
                "total_tasks": len(self.tasks)
            }
        }
    
    # ========== 指标 ==========
    
    def get_metrics(self) -> Dict:
        """获取指标"""
        return {
            "stats": self.stats,
            "agents": {
                "total": len(self.agents),
                "by_status": self._count_by_status(),
                "by_group": self._count_by_group()
            },
            "tasks": {
                "total": len(self.tasks),
                "by_status": self._count_tasks_by_status()
            }
        }
    
    def _count_by_status(self) -> Dict:
        counts = defaultdict(int)
        for a in self.agents.values():
            counts[a.status] += 1
        return dict(counts)
    
    def _count_by_group(self) -> Dict:
        counts = defaultdict(int)
        for a in self.agents.values():
            if a.group_id:
                counts[a.group_id] += 1
        return dict(counts)
    
    def _count_tasks_by_status(self) -> Dict:
        counts = defaultdict(int)
        for t in self.tasks.values():
            counts[t.status] += 1
        return dict(counts)


# 全局实例
api = MobileCollabAPI()


# ========== 辅助函数 ==========

def check_rate_limit(f):
    """速率限制装饰器"""
    def wrapper(*args, **kwargs):
        client_id = request.headers.get('X-Client-ID', request.remote_addr)
        if not api._check_rate_limit(client_id):
            return jsonify({"error": "Rate limit exceeded"}), 429
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def compress_response(response: Dict) -> Response:
    """压缩响应"""
    json_str = json.dumps(response, default=str)
    
    if request.headers.get('Accept-Encoding', '').find('gzip') >= 0:
        compressed = gzip.compress(json_str.encode())
        resp = Response(compressed)
        resp.headers['Content-Encoding'] = 'gzip'
        resp.headers['Content-Length'] = len(compressed)
    else:
        resp = jsonify(response)
    
    return resp


# ========== API端点 ==========

@app.route('/health', methods=['GET'])
def health():
    return compress_response({"status": "ok", "service": "mobile-collab-api", "port": 18140})


@app.route('/metrics', methods=['GET'])
@check_rate_limit
def metrics():
    return compress_response(api.get_metrics())


# Agent管理
@app.route('/agents', methods=['GET'])
@check_rate_limit
def list_agents():
    group_id = request.args.get('group')
    status = request.args.get('status')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    
    result = api.list_agents(group_id, status, page, page_size)
    api.stats['requests'] += 1
    return compress_response(result)


@app.route('/agents', methods=['POST'])
@check_rate_limit
def register_agent():
    data = request.get_json() or {}
    
    # 批量注册
    if 'agents' in data:
        result = api.batch_register_agents(data['agents'])
    else:
        result = api.register_agent(
            data.get('agent_id', f"agent-{uuid.uuid4().hex[:8]}"),
            data.get('capabilities', []),
            data.get('group_id')
        )
    
    return compress_response(result)


@app.route('/agents/batch', methods=['PUT'])
@check_rate_limit
def batch_update_agents():
    data = request.get_json() or {}
    result = api.batch_update_agents(data.get('updates', []))
    return compress_response(result)


@app.route('/agents/<agent_id>/heartbeat', methods=['POST'])
@check_rate_limit
def agent_heartbeat(agent_id):
    data = request.get_json() or {}
    result = api.heartbeat(agent_id, data.get('status'), data.get('health_score'))
    return compress_response(result)


# 任务管理
@app.route('/tasks', methods=['GET'])
@check_rate_limit
def list_tasks():
    status = request.args.get('status')
    agent_id = request.args.get('agent_id')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    
    result = api.list_tasks(status, agent_id, page, page_size)
    return compress_response(result)


@app.route('/tasks', methods=['POST'])
@check_rate_limit
def create_task():
    data = request.get_json() or {}
    
    # 批量创建
    if 'tasks' in data:
        result = api.batch_create_tasks(data['tasks'])
    else:
        result = api.create_task(
            data.get('task_type', 'default'),
            data.get('payload'),
            data.get('priority', 5),
            data.get('group_id')
        )
    
    return compress_response(result)


# 同步
@app.route('/sync', methods=['GET'])
@check_rate_limit
def sync():
    client_token = request.args.get('token', 'default')
    since = float(request.args.get('since', 0))
    result = api.sync(client_token, since)
    return compress_response(result)


# 实时事件流 (SSE)
@app.route('/events', methods=['GET'])
def events():
    """Server-Sent Events 实时推送"""
    
    def generate():
        import random
        client_id = request.args.get('client_id', 'default')
        
        # 发送初始事件
        yield f"data: {json.dumps({'type': 'connected', 'client_id': client_id})}\n\n"
        
        # 模拟实时更新
        for i in range(30):  # 30秒内定期推送
            event_type = random.choice(['agent_update', 'task_update', 'health_alert'])
            event_data = {
                "type": event_type,
                "timestamp": time.time(),
                "data": {
                    "id": f"{event_type[:5]}-{i}",
                    "status": random.choice(['active', 'idle', 'completed'])
                }
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            time.sleep(1)
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


# Groups
@app.route('/groups', methods=['GET'])
@check_rate_limit
def list_groups():
    return compress_response({
        "groups": list(api.groups.values()),
        "count": len(api.groups)
    })


# 速率限制状态
@app.route('/rate-limit/status', methods=['GET'])
def rate_limit_status():
    client_id = request.headers.get('X-Client-ID', request.remote_addr)
    api._check_rate_limit(client_id)  # 触发更新
    remaining = api.RATE_LIMIT - len(api.rate_limits.get(client_id, []))
    
    return compress_response({
        "limit": api.RATE_LIMIT,
        "remaining": max(0, remaining),
        "reset_in": api.RATE_WINDOW
    })


if __name__ == '__main__':
    logger.info("启动移动端适配协作API服务 (端口 18140)")
    app.run(host='0.0.0.0', port=18140, debug=False, threaded=True)