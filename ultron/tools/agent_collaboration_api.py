#!/usr/bin/env python3
"""
Agent Collaboration API - 增强版Agent网络协作服务
提供Agent间通信、任务协同、状态同步功能
"""

import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from collections import defaultdict
import sqlite3
import uuid

app = Flask(__name__)

# 内存状态存储
agents = {}  # agent_id -> {status, metadata, last_seen}
messages = defaultdict(list)  # agent_id -> [messages]
tasks = {}  # task_id -> {status, assigned_to, result}
lock = threading.Lock()

DB_PATH = "/root/.openclaw/workspace/ultron/tools/collaboration.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS agents
                 (id TEXT PRIMARY KEY, status TEXT, metadata TEXT, last_seen REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id TEXT PRIMARY KEY, from_agent TEXT, to_agent TEXT, 
                  content TEXT, timestamp REAL, read INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id TEXT PRIMARY KEY, type TEXT, assigned_to TEXT, 
                  status TEXT, result TEXT, created_at REAL, updated_at REAL)''')
    conn.commit()
    conn.close()

init_db()

# ============ Agent注册与状态管理 ============

@app.route('/api/agents/register', methods=['POST'])
def register_agent():
    """Agent注册"""
    data = request.json
    agent_id = data.get('agent_id', str(uuid.uuid4()))
    metadata = data.get('metadata', {})
    
    with lock:
        agents[agent_id] = {
            'status': 'online',
            'metadata': metadata,
            'last_seen': time.time(),
            'registered_at': datetime.now().isoformat()
        }
        
        # 持久化
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO agents VALUES (?, ?, ?, ?)',
                  (agent_id, 'online', json.dumps(metadata), time.time()))
        conn.commit()
        conn.close()
    
    return jsonify({
        'success': True, 
        'agent_id': agent_id,
        'message': 'Agent registered successfully'
    })

@app.route('/api/agents/heartbeat', methods=['POST'])
def agent_heartbeat():
    """Agent心跳"""
    agent_id = request.json.get('agent_id')
    status = request.json.get('status', 'online')
    
    if agent_id not in agents:
        return jsonify({'success': False, 'error': 'Agent not registered'}), 404
    
    with lock:
        agents[agent_id]['last_seen'] = time.time()
        agents[agent_id]['status'] = status
    
    return jsonify({'success': True})

@app.route('/api/agents', methods=['GET'])
def list_agents():
    """列出所有Agent"""
    now = time.time()
    result = []
    for agent_id, info in agents.items():
        # 5分钟内的为在线
        is_online = (now - info['last_seen']) < 300
        result.append({
            'agent_id': agent_id,
            'status': info['status'] if is_online else 'offline',
            'metadata': info.get('metadata', {}),
            'last_seen': info['last_seen']
        })
    return jsonify({'agents': result, 'total': len(result)})

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """获取Agent详情"""
    if agent_id not in agents:
        return jsonify({'error': 'Agent not found'}), 404
    return jsonify(agents[agent_id])

# ============ Agent间消息通信 ============

@app.route('/api/messages/send', methods=['POST'])
def send_message():
    """发送消息给Agent"""
    data = request.json
    from_agent = data.get('from')
    to_agent = data.get('to')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    
    if not all([from_agent, to_agent, content]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    msg_id = str(uuid.uuid4())
    msg = {
        'id': msg_id,
        'from': from_agent,
        'to': to_agent,
        'content': content,
        'type': msg_type,
        'timestamp': time.time(),
        'read': False
    }
    
    with lock:
        messages[to_agent].append(msg)
        
        # 持久化
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)',
                  (msg_id, from_agent, to_agent, json.dumps(content), time.time(), 0))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True, 'message_id': msg_id})

@app.route('/api/messages/<agent_id>', methods=['GET'])
def get_messages(agent_id):
    """获取Agent的消息"""
    with lock:
        msgs = messages.get(agent_id, [])
        # 标记为已读
        for msg in msgs:
            msg['read'] = True
        return jsonify({'messages': msgs, 'unread': len([m for m in msgs if not m['read']])})

@app.route('/api/messages/<agent_id>/clear', methods=['POST'])
def clear_messages(agent_id):
    """清除Agent的消息"""
    with lock:
        messages[agent_id] = []
    return jsonify({'success': True})

# ============ 任务协同 ============

@app.route('/api/tasks/create', methods=['POST'])
def create_task():
    """创建协作任务"""
    data = request.json
    task_type = data.get('type', 'general')
    assigned_to = data.get('assigned_to')  # 可指定Agent，不指定则广播
    payload = data.get('payload', {})
    priority = data.get('priority', 'normal')
    
    task_id = f"task_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
    
    task = {
        'id': task_id,
        'type': task_type,
        'assigned_to': assigned_to,
        'status': 'pending',
        'payload': payload,
        'priority': priority,
        'created_at': time.time(),
        'updated_at': time.time(),
        'result': None
    }
    
    with lock:
        tasks[task_id] = task
        
        # 如果指定了Agent，发送消息通知
        if assigned_to and assigned_to in agents:
            msg = {
                'id': str(uuid.uuid4()),
                'from': 'system',
                'to': assigned_to,
                'content': json.dumps({'type': 'task_assignment', 'task_id': task_id}),
                'timestamp': time.time(),
                'read': False
            }
            messages[assigned_to].append(msg)
    
    # 持久化
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)',
              (task_id, task_type, assigned_to or '', 'pending', '', 
               task['created_at'], task['updated_at']))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'task_id': task_id, 'task': task})

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务状态"""
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(tasks[task_id])

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """完成任务"""
    data = request.json
    result = data.get('result', {})
    
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    with lock:
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['result'] = result
        tasks[task_id]['updated_at'] = time.time()
        
        # 通知任务创建者
        original_creator = data.get('notify')
        if original_creator and original_creator in agents:
            msg = {
                'id': str(uuid.uuid4()),
                'from': 'system',
                'to': original_creator,
                'content': json.dumps({
                    'type': 'task_completed', 
                    'task_id': task_id,
                    'result': result
                }),
                'timestamp': time.time(),
                'read': False
            }
            messages[original_creator].append(msg)
    
    return jsonify({'success': True})

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    """列出所有任务"""
    status = request.args.get('status')
    result = list(tasks.values())
    if status:
        result = [t for t in result if t['status'] == status]
    return jsonify({'tasks': result, 'total': len(result)})

# ============ 协作统计 ============

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取协作统计"""
    now = time.time()
    online_agents = sum(1 for a in agents.values() if (now - a['last_seen']) < 300)
    
    return jsonify({
        'total_agents': len(agents),
        'online_agents': online_agents,
        'total_tasks': len(tasks),
        'pending_tasks': len([t for t in tasks.values() if t['status'] == 'pending']),
        'completed_tasks': len([t for t in tasks.values() if t['status'] == 'completed']),
        'total_messages': sum(len(msgs) for msgs in messages.values())
    })

# ============ 联邦网络拓扑 ============

@app.route('/api/network/topology', methods=['GET'])
def get_topology():
    """获取联邦网络拓扑"""
    now = time.time()
    nodes = []
    edges = []
    
    for agent_id, info in agents.items():
        is_online = (now - info['last_seen']) < 300
        nodes.append({
            'id': agent_id,
            'status': info['status'] if is_online else 'offline',
            'type': info.get('metadata', {}).get('type', 'unknown'),
            'capabilities': info.get('metadata', {}).get('capabilities', []),
            'last_seen': info['last_seen']
        })
    
    # 建立Agent之间的连接关系（基于任务协作历史）
    for task_id, task in tasks.items():
        if task.get('assigned_to'):
            edges.append({
                'from': 'system',
                'to': task['assigned_to'],
                'task_id': task_id,
                'type': 'assignment'
            })
    
    return jsonify({
        'nodes': nodes,
        'edges': edges,
        'summary': {
            'total_nodes': len(nodes),
            'online_nodes': len([n for n in nodes if n['status'] == 'online']),
            'total_edges': len(edges)
        }
    })

@app.route('/api/network/match', methods=['POST'])
def match_agent():
    """根据能力需求匹配最佳Agent"""
    data = request.json
    required_capabilities = data.get('capabilities', [])
    preferred_type = data.get('type')
    
    now = time.time()
    candidates = []
    
    for agent_id, info in agents.items():
        is_online = (now - info['last_seen']) < 300
        if not is_online:
            continue
        
        metadata = info.get('metadata', {})
        agent_type = metadata.get('type', '')
        agent_caps = metadata.get('capabilities', [])
        
        # 过滤类型
        if preferred_type and agent_type != preferred_type:
            continue
        
        # 计算能力匹配度
        matched = [c for c in required_capabilities if c in agent_caps]
        match_score = len(matched) / len(required_capabilities) if required_capabilities else 1.0
        
        if match_score > 0:
            candidates.append({
                'agent_id': agent_id,
                'type': agent_type,
                'capabilities': agent_caps,
                'match_score': match_score,
                'matched_capabilities': matched,
                'status': 'online',
                'last_seen': info['last_seen']
            })
    
    # 按匹配度排序
    candidates.sort(key=lambda x: (-x['match_score'], -x['last_seen']))
    
    return jsonify({
        'candidates': candidates,
        'best_match': candidates[0] if candidates else None,
        'total': len(candidates)
    })

@app.route('/api/network/stats', methods=['GET'])
def network_stats():
    """获取联邦网络统计"""
    now = time.time()
    
    # 计算网络健康度
    online_count = 0
    total_latency = 0
    for info in agents.values():
        if (now - info['last_seen']) < 300:
            online_count += 1
            total_latency += now - info['last_seen']
    
    avg_latency = total_latency / online_count if online_count > 0 else 0
    
    # 任务分布
    task_distribution = {}
    for task in tasks.values():
        agent = task.get('assigned_to', 'unassigned')
        task_distribution[agent] = task_distribution.get(agent, 0) + 1
    
    return jsonify({
        'network_health': {
            'total_agents': len(agents),
            'online_agents': online_count,
            'health_score': (online_count / len(agents) * 100) if agents else 0,
            'avg_response_latency': round(avg_latency, 2)
        },
        'task_distribution': task_distribution,
        'capabilities': {
            cap: sum(1 for a in agents.values() 
                    if cap in a.get('metadata', {}).get('capabilities', []))
            for cap in set(c for a in agents.values() 
                         for c in a.get('metadata', {}).get('capabilities', []))
        }
    })

# ============ 协作链 (多Agent协同) ============

collaboration_chains = {}

@app.route('/api/collaboration/chain', methods=['POST'])
def create_collaboration_chain():
    """创建多Agent协作链"""
    data = request.json
    chain_name = data.get('name', f'chain_{int(time.time())}')
    agents_sequence = data.get('agents', [])  # Agent ID列表
    task_payload = data.get('payload', {})
    
    chain_id = f"chain_{uuid.uuid4().hex[:8]}"
    
    chain = {
        'id': chain_id,
        'name': chain_name,
        'agents': agents_sequence,
        'status': 'created',
        'current_step': 0,
        'payload': task_payload,
        'results': [],
        'created_at': time.time(),
        'updated_at': time.time()
    }
    
    with lock:
        collaboration_chains[chain_id] = chain
    
    return jsonify({'success': True, 'chain_id': chain_id, 'chain': chain})

@app.route('/api/collaboration/chain/<chain_id>/execute', methods=['POST'])
def execute_chain(chain_id):
    """执行协作链下一跳"""
    if chain_id not in collaboration_chains:
        return jsonify({'error': 'Chain not found'}), 404
    
    chain = collaboration_chains[chain_id]
    current_step = chain['current_step']
    
    if current_step >= len(chain['agents']):
        return jsonify({'error': 'Chain already completed'}), 400
    
    # 获取当前应该执行的Agent
    current_agent = chain['agents'][current_step]
    result = request.json.get('result', {})
    
    # 记录结果
    chain['results'].append({
        'step': current_step,
        'agent': current_agent,
        'result': result,
        'timestamp': time.time()
    })
    
    # 移动到下一步
    chain['current_step'] += 1
    chain['updated_at'] = time.time()
    
    if chain['current_step'] >= len(chain['agents']):
        chain['status'] = 'completed'
    else:
        chain['status'] = 'in_progress'
        next_agent = chain['agents'][chain['current_step']]
        # 通知下一个Agent
        if next_agent in agents:
            msg = {
                'id': str(uuid.uuid4()),
                'from': 'system',
                'to': next_agent,
                'content': json.dumps({
                    'type': 'chain_execution',
                    'chain_id': chain_id,
                    'step': chain['current_step'],
                    'previous_result': result
                }),
                'timestamp': time.time(),
                'read': False
            }
            messages[next_agent].append(msg)
    
    return jsonify({'success': True, 'chain': chain})

@app.route('/api/collaboration/chain/<chain_id>', methods=['GET'])
def get_chain(chain_id):
    """获取协作链状态"""
    if chain_id not in collaboration_chains:
        return jsonify({'error': 'Chain not found'}), 404
    return jsonify(collaboration_chains[chain_id])

@app.route('/api/collaboration/chains', methods=['GET'])
def list_chains():
    """列出所有协作链"""
    return jsonify({
        'chains': list(collaboration_chains.values()),
        'total': len(collaboration_chains)
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'agent-collaboration-api'})

if __name__ == '__main__':
    print("🤖 Starting Agent Collaboration API on port 18295...")
    print("📡 Federation features enabled: topology, match, stats, collaboration chains")
    app.run(host='0.0.0.0', port=18295, debug=False)