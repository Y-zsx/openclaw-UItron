#!/usr/bin/env python3
"""
移动端适配与API增强中间件 v2.0
功能:
- 响应式JSON响应优化
- API版本控制
- 压缩支持
- 分页支持
- 速率限制响应头
- 缓存控制
- GraphQL风格查询
- 离线同步支持
- ETags与条件请求
- 批量操作API
- 连接状态管理
"""

from flask import Flask, jsonify, request, make_response
import json
import gzip
import time
import hashlib
import uuid
from functools import wraps
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

app = Flask(__name__)

# API版本配置
API_VERSIONS = {
    'v1': '2024-01-01',
    'v2': '2025-06-01',
    'v3': '2026-03-06'  # 新增v3
}
CURRENT_VERSION = 'v3'

# ========== 数据模型 ==========

@dataclass
class SyncToken:
    """离线同步令牌"""
    token: str
    timestamp: float
    checkpoint: str
    
@dataclass
class BatchOperation:
    """批量操作请求"""
    operations: List[Dict]
    atomic: bool = False  # 是否原子操作

class MobileAdapter:
    """移动端适配器"""
    
    def __init__(self):
        self.compression_min_size = 1024  # 最小压缩大小
        self.default_page_size = 20
        self.max_page_size = 100
        
    def compress_response(self, data):
        """响应压缩"""
        if isinstance(data, dict):
            json_str = json.dumps(data, ensure_ascii=False)
            if len(json_str) > self.compression_min_size:
                return json_str
        return None
        
    def format_response(self, data, meta=None):
        """标准化响应格式"""
        response = {
            'success': True,
            'data': data,
            'timestamp': int(time.time())
        }
        
        if meta:
            response['meta'] = meta
            
        # 移动端友好: 扁平化结构
        if request.headers.get('X-Mobile-Client'):
            response['mobile_optimized'] = True
            
        return response
    
    def format_error(self, code, message, details=None):
        """增强错误响应"""
        error = {
            'success': False,
            'error': {
                'code': code,
                'message': message,
                'timestamp': int(time.time())
            }
        }
        if details:
            error['error']['details'] = details
        return error
    
    def add_pagination(self, items, page=1, page_size=None):
        """分页支持"""
        if page_size is None:
            page_size = self.default_page_size
        page_size = min(page_size, self.max_page_size)
        
        start = (page - 1) * page_size
        end = start + page_size
        paginated = items[start:end]
        
        return {
            'items': paginated,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': len(items),
                'total_pages': (len(items) + page_size - 1) // page_size,
                'has_next': end < len(items),
                'has_prev': page > 1
            }
        }

def rate_limit_headers(limit=100, remaining=99, reset=None):
    """添加速率限制响应头"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            response = f(*args, **kwargs)
            if isinstance(response, dict):
                response_obj = make_response(jsonify(response))
            else:
                response_obj = response
                
            response_obj.headers['X-RateLimit-Limit'] = str(limit)
            response_obj.headers['X-RateLimit-Remaining'] = str(remaining)
            if reset:
                response_obj.headers['X-RateLimit-Reset'] = str(reset)
            return response_obj
        return wrapped
    return decorator

def cache_control(max_age=300, stale_while_revalidate=60):
    """缓存控制"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            response = f(*args, **kwargs)
            if isinstance(response, dict):
                response_obj = make_response(jsonify(response))
            else:
                response_obj = response
                
            response_obj.headers['Cache-Control'] = f'max-age={max_age}, stale-while-revalidate={stale_while_revalidate}'
            response_obj.headers['X-Cache-Status'] = 'MISS'
            return response_obj
        return wrapped
    return decorator

def api_version_header(f):
    """API版本支持"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        version = request.headers.get('X-API-Version', CURRENT_VERSION)
        if version not in API_VERSIONS:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNSUPPORTED_VERSION',
                    'message': f'不支持的API版本: {version}',
                    'supported_versions': list(API_VERSIONS.keys())
                }
            }), 400
            
        response = f(*args, **kwargs)
        
        if isinstance(response, dict):
            response_obj = make_response(jsonify(response))
            response_obj.headers['X-API-Version'] = version
            response_obj.headers['X-API-Deprecated'] = 'false'
            
            # 提示旧版本即将弃用
            if version == 'v1':
                response_obj.headers['X-API-Deprecation'] = 'v1将于2025-12-31弃用，请迁移到v2'
                
            return response_obj
        return response
    return wrapped

# 移动端检测
def is_mobile_client():
    """检测移动端客户端"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_indicators = ['android', 'iphone', 'ipad', 'mobile', 'ios']
    return any(indicator in user_agent for indicator in mobile_indicators)

@app.route('/health')
@cache_control(max_age=60)
def health():
    """健康检查端点"""
    return MobileAdapter().format_response({
        'status': 'ok',
        'version': CURRENT_VERSION,
        'mobile_adapter': 'active'
    })

@app.route('/api/v2/agents')
@api_version_header
@rate_limit_headers(limit=100, remaining=99)
@cache_control(max_age=30)
def list_agents():
    """列出Agent列表 - 移动端优化"""
    # 示例数据
    agents = [
        {'id': 'agent-1', 'name': 'coordinator', 'status': 'active'},
        {'id': 'agent-2', 'name': 'executor', 'status': 'active'},
        {'id': 'agent-3', 'name': 'monitor', 'status': 'idle'}
    ]
    
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    
    adapter = MobileAdapter()
    result = adapter.add_pagination(agents, page, page_size)
    
    meta = {
        'api_version': CURRENT_VERSION,
        'response_time_ms': 0
    }
    
    return adapter.format_response(result, meta)

@app.route('/api/v2/agents/<agent_id>')
@api_version_header
@rate_limit_headers(limit=100, remaining=99)
@cache_control(max_age=60)
def get_agent(agent_id):
    """获取Agent详情"""
    adapter = MobileAdapter()
    
    if not agent_id:
        return adapter.format_error('INVALID_REQUEST', 'Agent ID required'), 400
    
    # 示例数据
    agent_data = {
        'id': agent_id,
        'name': f'agent-{agent_id}',
        'status': 'active',
        'capabilities': ['task_execution', 'health_check'],
        'last_heartbeat': int(time.time()) - 30
    }
    
    return adapter.format_response(agent_data)

@app.route('/api/v2/tasks', methods=['POST'])
@api_version_header
@rate_limit_headers(limit=50, remaining=49)
def create_task():
    """创建任务"""
    data = request.get_json()
    
    if not data or 'task_type' not in data:
        return MobileAdapter().format_error(
            'INVALID_REQUEST', 
            'task_type is required',
            {'received_keys': list(data.keys()) if data else []}
        ), 400
    
    task_id = f"task-{int(time.time())}"
    
    return MobileAdapter().format_response({
        'task_id': task_id,
        'status': 'queued',
        'created_at': int(time.time())
    }), 201


# ========== v3 新增功能 ==========

# 内存存储（生产环境应使用数据库）
sync_tokens: Dict[str, SyncToken] = {}


def generate_etag(data: Any) -> str:
    """生成ETag"""
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(content.encode()).hexdigest()


def check_etag(response_data: Dict) -> tuple:
    """检查ETag并返回响应"""
    etag = generate_etag(response_data)
    if_none_match = request.headers.get('If-None-Match')
    
    if if_none_match and if_none_match == etag:
        return None, 304  # Not Modified
    
    return etag, None


@app.route('/api/v3/query', methods=['POST'])
@api_version_header
def graphql_query():
    """GraphQL风格查询接口
    
    支持查询字段:
    - agents: 列出Agents
    - tasks: 列出Tasks
    - stats: 统计信息
    
    请求体格式:
    {
        "query": "{ agents { id status } }",
        "variables": {}
    }
    """
    data = request.get_json() or {}
    query = data.get('query', '')
    variables = data.get('variables', {})
    
    adapter = MobileAdapter()
    result = {}
    
    # 简单解析 (生产环境使用graphql-core)
    if 'agents' in query:
        agents = [
            {'id': 'agent-1', 'name': 'coordinator', 'status': 'active', 'health': 95},
            {'id': 'agent-2', 'name': 'executor', 'status': 'active', 'health': 88},
            {'id': 'agent-3', 'name': 'monitor', 'status': 'idle', 'health': 100}
        ]
        
        # 字段过滤
        if 'id' in query and 'status' not in query:
            agents = [{'id': a['id']} for a in agents]
        
        result['agents'] = agents
    
    if 'tasks' in query:
        tasks = [
            {'id': 'task-1', 'type': 'health_check', 'status': 'completed'},
            {'id': 'task-2', 'type': 'execution', 'status': 'running'}
        ]
        result['tasks'] = tasks
    
    if 'stats' in query:
        result['stats'] = {
            'total_agents': 3,
            'active_agents': 2,
            'total_tasks': 156,
            'completed_tasks': 150,
            'uptime_seconds': 86400
        }
    
    # 生成ETag
    etag, not_modified = check_etag(result)
    
    response = adapter.format_response(result)
    response_obj = make_response(jsonify(response))
    
    if etag:
        response_obj.headers['ETag'] = etag
    
    if not_modified:
        return '', 304
    
    return response_obj


@app.route('/api/v3/batch', methods=['POST'])
@api_version_header
@rate_limit_headers(limit=20, remaining=19)
def batch_operations():
    """批量操作接口
    
    请求体格式:
    {
        "operations": [
            {"method": "GET", "path": "/api/v2/agents"},
            {"method": "POST", "path": "/api/v2/tasks", "body": {"task_type": "test"}}
        ],
        "atomic": false  // 是否全部成功才提交
    }
    """
    data = request.get_json() or {}
    operations = data.get('operations', [])
    atomic = data.get('atomic', False)
    
    if not operations:
        return MobileAdapter().format_error('INVALID_REQUEST', 'operations is required'), 400
    
    if len(operations) > 50:
        return MobileAdapter().format_error('INVALID_REQUEST', '最多支持50个操作'), 400
    
    results = []
    all_success = True
    
    for i, op in enumerate(operations):
        method = op.get('method', 'GET').upper()
        path = op.get('path', '')
        
        # 简化实现 - 实际应根据path调用对应处理
        if '/agents' in path and method == 'GET':
            results.append({
                'index': i,
                'status': 200,
                'data': {'agents': [{'id': 'agent-1'}, {'id': 'agent-2'}]}
            })
        elif '/tasks' in path and method == 'POST':
            task_id = f"task-{int(time.time())}-{i}"
            results.append({
                'index': i,
                'status': 201,
                'data': {'task_id': task_id, 'status': 'queued'}
            })
        else:
            results.append({
                'index': i,
                'status': 404,
                'error': 'Not found'
            })
            if atomic:
                all_success = False
                break
    
    return MobileAdapter().format_response({
        'results': results,
        'atomic': atomic,
        'all_success': all_success
    })


@app.route('/api/v3/sync/token', methods=['POST'])
@api_version_header
def get_sync_token():
    """获取离线同步令牌"""
    client_id = request.headers.get('X-Client-ID', str(uuid.uuid4()))
    checkpoint = request.json.get('checkpoint', '0') if request.is_json else '0'
    
    token = SyncToken(
        token=str(uuid.uuid4()),
        timestamp=time.time(),
        checkpoint=checkpoint
    )
    
    sync_tokens[client_id] = token
    
    return MobileAdapter().format_response({
        'sync_token': token.token,
        'issued_at': int(token.timestamp),
        'expires_in': 3600  # 1小时有效期
    })


@app.route('/api/v3/sync/changes', methods=['GET'])
@api_version_header
@cache_control(max_age=0)  # 不缓存
def get_changes():
    """获取增量变更（离线同步用）"""
    sync_token = request.headers.get('X-Sync-Token')
    since = request.args.get('since', '0')
    
    if not sync_token or sync_token not in [t.token for t in sync_tokens.values()]:
        return MobileAdapter().format_error('INVALID_TOKEN', '无效的同步令牌'), 401
    
    # 返回模拟的增量变更
    changes = {
        'agents': [
            {'id': 'agent-new', 'action': 'added', 'data': {'name': 'new-agent'}}
        ],
        'tasks': [
            {'id': 'task-100', 'action': 'updated', 'data': {'status': 'completed'}}
        ],
        'deleted': []
    }
    
    return MobileAdapter().format_response({
        'changes': changes,
        'sync_timestamp': int(time.time()),
        'has_more': False
    })


@app.route('/api/v3/connection', methods=['POST'])
@api_version_header
def register_connection():
    """注册移动端连接（用于推送）"""
    client_id = request.headers.get('X-Client-ID', str(uuid.uuid4()))
    data = request.get_json() or {}
    connection_type = data.get('type', 'websocket')
    
    return MobileAdapter().format_response({
        'client_id': client_id,
        'connection_registered': True,
        'push_endpoint': f'/api/v3/push/{client_id}',
        'heartbeat_interval': 30
    })


@app.route('/api/v3/connection/<client_id>/ping', methods=['POST'])
@api_version_header
def connection_ping(client_id):
    """连接心跳"""
    return MobileAdapter().format_response({
        'status': 'alive',
        'latency_ms': 15,
        'server_time': int(time.time())
    })


if __name__ == '__main__':
    print(f"🚀 Mobile Adapter API启动 - 版本: {CURRENT_VERSION}")
    print(f"支持的版本: {list(API_VERSIONS.keys())}")
    app.run(host='0.0.0.0', port=18233, debug=False)