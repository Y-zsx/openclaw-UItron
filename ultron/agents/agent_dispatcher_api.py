#!/usr/bin/env python3
"""
Agent请求分发与负载均衡API服务
=============================
为协调Agent提供智能请求分发和流量管理

端口: 18132
功能:
- 智能请求路由 (根据Agent能力/负载/健康状态)
- 请求队列管理 (优先级/超时/重试)
- 流量控制 (限流/熔断)
- 请求追踪与监控
- 故障转移与自动重试
"""

import json
import time
import uuid
import threading
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from collections import defaultdict
from dataclasses import dataclass, asdict
from enum import Enum
import heapq

app = Flask(__name__)

# ============ 数据模型 ============

class RequestStatus(Enum):
    PENDING = "pending"
    ROUTING = "routing"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class RequestPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class RoutingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_LOAD = "least_load"
    PERFORMANCE = "performance"
    WEIGHTED = "weighted"

class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开

@dataclass
class DispatchRequest:
    id: str
    name: str
    payload: dict
    priority: int = 1
    strategy: str = "least_load"
    required_capabilities: list = None
    timeout: int = 30
    retry_count: int = 0
    max_retries: int = 3
    status: str = "pending"
    agent_id: str = None
    created_at: str = None
    dispatched_at: str = None
    completed_at: str = None
    result: dict = None
    error: str = None
    circuit_state: str = "closed"
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.required_capabilities is None:
            self.required_capabilities = []

@dataclass
class AgentEndpoint:
    id: str
    name: str
    url: str
    capabilities: list = None
    weight: int = 100
    status: str = "healthy"
    current_requests: int = 0
    max_concurrent: int = 10
    response_time: float = 0.0
    success_rate: float = 100.0
    circuit_failures: int = 0
    circuit_state: str = "closed"
    last_failure: str = None
    registered_at: str = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.registered_at is None:
            self.registered_at = datetime.now().isoformat()

# ============ 数据库 ============

class DispatchDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT,
            priority INTEGER DEFAULT 1, strategy TEXT DEFAULT 'least_load',
            required_capabilities TEXT, timeout INTEGER DEFAULT 30,
            retry_count INTEGER DEFAULT 0, max_retries INTEGER DEFAULT 3,
            status TEXT DEFAULT 'pending', agent_id TEXT,
            created_at TEXT, dispatched_at TEXT, completed_at TEXT,
            result TEXT, error TEXT, circuit_state TEXT DEFAULT 'closed'
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS endpoints (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
            capabilities TEXT, weight INTEGER DEFAULT 100,
            status TEXT DEFAULT 'healthy', current_requests INTEGER DEFAULT 0,
            max_concurrent INTEGER DEFAULT 10, response_time REAL DEFAULT 0.0,
            success_rate REAL DEFAULT 100.0, circuit_failures INTEGER DEFAULT 0,
            circuit_state TEXT DEFAULT 'closed', last_failure TEXT,
            registered_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS circuit_breaker (
            endpoint_id TEXT PRIMARY KEY, state TEXT DEFAULT 'closed',
            failure_count INTEGER DEFAULT 0, last_failure_time TEXT,
            next_retry_time TEXT
        )''')
        
        conn.commit()
        conn.close()
    
    def save_request(self, req: DispatchRequest):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO requests 
            (id, name, payload, priority, strategy, required_capabilities, timeout,
             retry_count, max_retries, status, agent_id, created_at, dispatched_at,
             completed_at, result, error, circuit_state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (req.id, req.name, json.dumps(req.payload), req.priority, req.strategy,
             json.dumps(req.required_capabilities), req.timeout, req.retry_count,
             req.max_retries, req.status, req.agent_id, req.created_at, req.dispatched_at,
             req.completed_at, json.dumps(req.result) if req.result else None,
             req.error, req.circuit_state))
        conn.commit()
        conn.close()
    
    def get_request(self, request_id: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM requests WHERE id = ?', (request_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return self._row_to_request(row)
        return None
    
    def _row_to_request(self, row):
        return DispatchRequest(
            id=row[0], name=row[1], payload=json.loads(row[2]) if row[2] else {},
            priority=row[3], strategy=row[4],
            required_capabilities=json.loads(row[5]) if row[5] else [],
            timeout=row[6], retry_count=row[7], max_retries=row[8],
            status=row[9], agent_id=row[10], created_at=row[11],
            dispatched_at=row[12], completed_at=row[13],
            result=json.loads(row[14]) if row[14] else None,
            error=row[15], circuit_state=row[16]
        )
    
    def save_endpoint(self, endpoint: AgentEndpoint):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO endpoints
            (id, name, url, capabilities, weight, status, current_requests,
             max_concurrent, response_time, success_rate, circuit_failures,
             circuit_state, last_failure, registered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (endpoint.id, endpoint.name, endpoint.url,
             json.dumps(endpoint.capabilities), endpoint.weight, endpoint.status,
             endpoint.current_requests, endpoint.max_concurrent, endpoint.response_time,
             endpoint.success_rate, endpoint.circuit_failures, endpoint.circuit_state,
             endpoint.last_failure, endpoint.registered_at))
        conn.commit()
        conn.close()
    
    def get_endpoint(self, endpoint_id: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM endpoints WHERE id = ?', (endpoint_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return self._row_to_endpoint(row)
        return None
    
    def _row_to_endpoint(self, row):
        return AgentEndpoint(
            id=row[0], name=row[1], url=row[2],
            capabilities=json.loads(row[3]) if row[3] else [],
            weight=row[4], status=row[5], current_requests=row[6],
            max_concurrent=row[7], response_time=row[8], success_rate=row[9],
            circuit_failures=row[10], circuit_state=row[11],
            last_failure=row[12], registered_at=row[13]
        )
    
    def get_all_endpoints(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM endpoints')
        rows = c.fetchall()
        conn.close()
        return [self._row_to_endpoint(row) for row in rows]
    
    def get_healthy_endpoints(self, capabilities: list = None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if capabilities:
            for cap in capabilities:
                c.execute('SELECT * FROM endpoints WHERE capabilities LIKE ? AND status = ? AND circuit_state != ?',
                          (f'%{cap}%', 'healthy', 'open'))
        else:
            c.execute('SELECT * FROM endpoints WHERE status = ? AND circuit_state != ?', ('healthy', 'open'))
        rows = c.fetchall()
        conn.close()
        return [self._row_to_endpoint(row) for row in rows]
    
    def update_endpoint_stats(self, endpoint_id: str, success: bool, response_time: float):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if success:
            c.execute('''UPDATE endpoints SET 
                success_rate = (success_rate * 0.9 + 100 * 0.1),
                response_time = (response_time * 0.7 + ? * 0.3),
                circuit_failures = 0
                WHERE id = ?''', (response_time, endpoint_id))
        else:
            c.execute('''UPDATE endpoints SET 
                success_rate = (success_rate * 0.9),
                circuit_failures = circuit_failures + 1,
                last_failure = ?
                WHERE id = ?''', (datetime.now().isoformat(), endpoint_id))
            
            # 检查是否需要熔断
            c.execute('SELECT circuit_failures FROM endpoints WHERE id = ?', (endpoint_id,))
            row = c.fetchone()
            if row and row[0] >= 5:
                c.execute('''UPDATE endpoints SET circuit_state = 'open' WHERE id = ?''', (endpoint_id,))
        
        conn.commit()
        conn.close()


# ============ 负载均衡器 ============

class RequestDispatcher:
    def __init__(self, db: DispatchDatabase):
        self.db = db
        self.round_robin_index = defaultdict(int)
        self.lock = threading.Lock()
    
    def select_endpoint(self, strategy: str, capabilities: list = None) -> AgentEndpoint:
        """根据策略选择最优Endpoint"""
        endpoints = self.db.get_healthy_endpoints(capabilities)
        
        if not endpoints:
            return None
        
        with self.lock:
            if strategy == "round_robin":
                idx = self.round_robin_index.get("default", 0)
                selected = endpoints[idx % len(endpoints)]
                self.round_robin_index["default"] = idx + 1
                return selected
            
            elif strategy == "least_connections":
                return min(endpoints, key=lambda e: e.current_requests)
            
            elif strategy == "least_load":
                return min(endpoints, key=lambda e: (
                    e.current_requests / e.max_concurrent,
                    e.response_time
                ))
            
            elif strategy == "performance":
                return min(endpoints, key=lambda e: (
                    -e.success_rate,
                    e.response_time
                ))
            
            elif strategy == "weighted":
                total_weight = sum(e.weight for e in endpoints)
                r = random.uniform(0, total_weight)
                cumulative = 0
                for e in endpoints:
                    cumulative += e.weight
                    if cumulative >= r:
                        return e
                return endpoints[0]
            
            else:
                return endpoints[0]
    
    def dispatch(self, req: DispatchRequest) -> DispatchRequest:
        """分发请求到目标Agent"""
        # 根据策略选择endpoint
        endpoint = self.select_endpoint(req.strategy, req.required_capabilities)
        
        if not endpoint:
            req.status = "failed"
            req.error = "No healthy endpoint available"
            self.db.save_request(req)
            return req
        
        # 检查并发限制
        if endpoint.current_requests >= endpoint.max_concurrent:
            # 尝试下一个
            endpoint = self.select_endpoint("least_connections", req.required_capabilities)
            if not endpoint or endpoint.current_requests >= endpoint.max_concurrent:
                req.status = "pending"
                req.error = "All endpoints at capacity"
                self.db.save_request(req)
                return req
        
        # 分配请求
        req.agent_id = endpoint.id
        req.status = "dispatched"
        req.dispatched_at = datetime.now().isoformat()
        
        # 更新endpoint状态
        endpoint.current_requests += 1
        self.db.save_endpoint(endpoint)
        self.db.save_request(req)
        
        return req
    
    def complete_request(self, request_id: str, success: bool, result: dict = None, error: str = None):
        """完成请求处理"""
        req = self.db.get_request(request_id)
        if not req:
            return
        
        if success:
            req.status = "completed"
            req.completed_at = datetime.now().isoformat()
            req.result = result
        else:
            req.status = "failed"
            req.error = error
            
            # 自动重试
            if req.retry_count < req.max_retries:
                req.retry_count += 1
                req.status = "pending"
                req.agent_id = None
        
        self.db.save_request(req)
        
        # 更新endpoint统计
        if req.agent_id:
            endpoint = self.db.get_endpoint(req.agent_id)
            if endpoint:
                endpoint.current_requests = max(0, endpoint.current_requests - 1)
                response_time = 0
                if req.dispatched_at and req.completed_at:
                    try:
                        dispatched = datetime.fromisoformat(req.dispatched_at)
                        completed = datetime.fromisoformat(req.completed_at)
                        response_time = (completed - dispatched).total_seconds()
                    except:
                        pass
                
                self.db.update_endpoint_stats(endpoint.id, success, response_time)
                self.db.save_endpoint(endpoint)


# ============ 全局实例 ============

db = DispatchDatabase('/root/.openclaw/workspace/ultron/agents/dispatcher_state.db')
dispatcher = RequestDispatcher(db)


# ============ API 端点 ============

@app.route('/')
def index():
    return jsonify({
        "service": "Agent请求分发与负载均衡API",
        "version": "1.0",
        "port": 18132,
        "endpoints": [
            "GET / - 服务信息",
            "GET /health - 健康检查",
            "GET /requests - 所有请求",
            "GET /requests/<id> - 请求详情",
            "POST /dispatch - 分发请求",
            "POST /complete/<id> - 完成请求",
            "GET /endpoints - 所有端点",
            "POST /endpoints - 注册端点",
            "GET /endpoints/<id> - 端点详情",
            "DELETE /endpoints/<id> - 删除端点",
            "GET /stats - 统计信息"
        ]
    })

@app.route('/health')
def health():
    endpoints = db.get_all_endpoints()
    healthy = sum(1 for e in endpoints if e.status == "healthy")
    return jsonify({
        "status": "healthy",
        "total_endpoints": len(endpoints),
        "healthy_endpoints": healthy,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/requests', methods=['GET'])
def list_requests():
    status = request.args.get('status')
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    if status:
        c.execute('SELECT * FROM requests WHERE status = ? ORDER BY created_at DESC LIMIT 100', (status,))
    else:
        c.execute('SELECT * FROM requests ORDER BY created_at DESC LIMIT 100')
    rows = c.fetchall()
    conn.close()
    
    requests = []
    for row in rows:
        req = db._row_to_request(row)
        requests.append({
            "id": req.id,
            "name": req.name,
            "priority": req.priority,
            "status": req.status,
            "agent_id": req.agent_id,
            "created_at": req.created_at,
            "error": req.error
        })
    
    return jsonify(requests)

@app.route('/requests/<request_id>', methods=['GET'])
def get_request(request_id):
    req = db.get_request(request_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404
    
    return jsonify({
        "id": req.id,
        "name": req.name,
        "payload": req.payload,
        "priority": req.priority,
        "strategy": req.strategy,
        "required_capabilities": req.required_capabilities,
        "timeout": req.timeout,
        "retry_count": req.retry_count,
        "max_retries": req.max_retries,
        "status": req.status,
        "agent_id": req.agent_id,
        "created_at": req.created_at,
        "dispatched_at": req.dispatched_at,
        "completed_at": req.completed_at,
        "result": req.result,
        "error": req.error
    })

@app.route('/dispatch', methods=['POST'])
def dispatch_request():
    data = request.json or {}
    
    req = DispatchRequest(
        id=str(uuid.uuid4()),
        name=data.get('name', 'unnamed'),
        payload=data.get('payload', {}),
        priority=data.get('priority', 1),
        strategy=data.get('strategy', 'least_load'),
        required_capabilities=data.get('required_capabilities', []),
        timeout=data.get('timeout', 30),
        max_retries=data.get('max_retries', 3)
    )
    
    result = dispatcher.dispatch(req)
    
    return jsonify({
        "request_id": result.id,
        "status": result.status,
        "agent_id": result.agent_id,
        "error": result.error,
        "message": "Request dispatched successfully" if result.agent_id else "Request queued"
    })

@app.route('/complete/<request_id>', methods=['POST'])
def complete_request(request_id):
    data = request.json or {}
    success = data.get('success', True)
    result = data.get('result')
    error = data.get('error')
    
    dispatcher.complete_request(request_id, success, result, error)
    
    return jsonify({
        "request_id": request_id,
        "status": "completed",
        "message": "Request completed"
    })

@app.route('/endpoints', methods=['GET'])
def list_endpoints():
    endpoints = db.get_all_endpoints()
    return jsonify([{
        "id": e.id,
        "name": e.name,
        "url": e.url,
        "capabilities": e.capabilities,
        "weight": e.weight,
        "status": e.status,
        "current_requests": e.current_requests,
        "max_concurrent": e.max_concurrent,
        "response_time": round(e.response_time, 2),
        "success_rate": round(e.success_rate, 1),
        "circuit_state": e.circuit_state
    } for e in endpoints])

@app.route('/endpoints', methods=['POST'])
def register_endpoint():
    data = request.json or {}
    
    endpoint = AgentEndpoint(
        id=data.get('id', str(uuid.uuid4())),
        name=data.get('name'),
        url=data.get('url'),
        capabilities=data.get('capabilities', []),
        weight=data.get('weight', 100),
        max_concurrent=data.get('max_concurrent', 10)
    )
    
    if not endpoint.name or not endpoint.url:
        return jsonify({"error": "name and url are required"}), 400
    
    db.save_endpoint(endpoint)
    
    return jsonify({
        "endpoint_id": endpoint.id,
        "message": "Endpoint registered successfully"
    })

@app.route('/endpoints/<endpoint_id>', methods=['GET'])
def get_endpoint(endpoint_id):
    endpoint = db.get_endpoint(endpoint_id)
    if not endpoint:
        return jsonify({"error": "Endpoint not found"}), 404
    
    return jsonify({
        "id": endpoint.id,
        "name": endpoint.name,
        "url": endpoint.url,
        "capabilities": endpoint.capabilities,
        "weight": endpoint.weight,
        "status": endpoint.status,
        "current_requests": endpoint.current_requests,
        "max_concurrent": endpoint.max_concurrent,
        "response_time": round(endpoint.response_time, 2),
        "success_rate": round(endpoint.success_rate, 1),
        "circuit_state": endpoint.circuit_state,
        "circuit_failures": endpoint.circuit_failures,
        "last_failure": endpoint.last_failure,
        "registered_at": endpoint.registered_at
    })

@app.route('/endpoints/<endpoint_id>', methods=['DELETE'])
def delete_endpoint(endpoint_id):
    endpoint = db.get_endpoint(endpoint_id)
    if not endpoint:
        return jsonify({"error": "Endpoint not found"}), 404
    
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    c.execute('DELETE FROM endpoints WHERE id = ?', (endpoint_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Endpoint deleted"})

@app.route('/endpoints/<endpoint_id>/status', methods=['PUT'])
def update_endpoint_status(endpoint_id):
    data = request.json or {}
    status = data.get('status')
    
    endpoint = db.get_endpoint(endpoint_id)
    if not endpoint:
        return jsonify({"error": "Endpoint not found"}), 404
    
    endpoint.status = status
    db.save_endpoint(endpoint)
    
    return jsonify({"message": "Status updated", "status": status})

@app.route('/stats', methods=['GET'])
def get_stats():
    endpoints = db.get_all_endpoints()
    healthy = sum(1 for e in endpoints if e.status == "healthy")
    
    conn = sqlite3.connect(db.db_path)
    c = conn.cursor()
    c.execute('SELECT status, COUNT(*) FROM requests GROUP BY status')
    status_counts = dict(c.fetchall())
    c.execute('SELECT COUNT(*) FROM requests')
    total_requests = c.fetchone()[0]
    conn.close()
    
    return jsonify({
        "endpoints": {
            "total": len(endpoints),
            "healthy": healthy,
            "unhealthy": len(endpoints) - healthy
        },
        "requests": {
            "total": total_requests,
            "by_status": status_counts
        },
        "strategies": [s.value for s in RoutingStrategy],
        "timestamp": datetime.now().isoformat()
    })


# ============ 启动 ============

if __name__ == '__main__':
    import random
    
    # 注册一些示例endpoints
    sample_endpoints = [
        AgentEndpoint(id="worker-1", name="Worker-1", url="http://localhost:8001",
                     capabilities=["execute", "compute"], weight=100),
        AgentEndpoint(id="worker-2", name="Worker-2", url="http://localhost:8002",
                     capabilities=["execute", "data"], weight=80),
        AgentEndpoint(id="api-1", name="API-1", url="http://localhost:8003",
                     capabilities=["api", "http"], weight=100),
    ]
    
    for ep in sample_endpoints:
        if not db.get_endpoint(ep.id):
            db.save_endpoint(ep)
    
    print("Starting Agent Dispatcher API on port 18132...")
    app.run(host='0.0.0.0', port=18132, debug=False)