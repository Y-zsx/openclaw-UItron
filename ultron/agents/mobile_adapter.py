#!/usr/bin/env python3
"""
移动端适配与API增强中间件
功能:
- 响应式JSON响应优化
- API版本控制
- 压缩支持
- 分页支持
- 速率限制响应头
- 缓存控制
"""

from flask import Flask, jsonify, request, make_response
import json
import gzip
import time
from functools import wraps

app = Flask(__name__)

# API版本配置
API_VERSIONS = {
    'v1': '2024-01-01',
    'v2': '2025-06-01'
}
CURRENT_VERSION = 'v2'

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

if __name__ == '__main__':
    print(f"🚀 Mobile Adapter API启动 - 版本: {CURRENT_VERSION}")
    print(f"支持的版本: {list(API_VERSIONS.keys())}")
    app.run(host='0.0.0.0', port=18233, debug=False)