#!/usr/bin/env python3
"""
Agent生命周期自动化管理 API
端口: 18130
"""

import json
import time
import random
import logging
import os
from datetime import datetime, timedelta
from aiohttp import web
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LIFECYCLE_STATE_FILE = "/root/.openclaw/workspace/ultron/data/agent_lifecycle_state.json"

class AgentState(Enum):
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    STOPPED = "stopped"
    FAILED = "failed"

class LifecycleManager:
    def __init__(self):
        self.agents = {}
        self.check_interval = 30
        self.stats = {"checks": 0, "failovers": 0, "recoveries": 0, "restarts": 0}
        self.load_state()
        
    def load_state(self):
        if os.path.exists(LIFECYCLE_STATE_FILE):
            try:
                with open(LIFECYCLE_STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.agents = data.get('agents', {})
                    self.stats = data.get('stats', self.stats)
            except:
                pass
    
    def save_state(self):
        os.makedirs(os.path.dirname(LIFECYCLE_STATE_FILE), exist_ok=True)
        with open(LIFECYCLE_STATE_FILE, 'w') as f:
            json.dump({
                'agents': self.agents,
                'stats': self.stats,
                'updated': datetime.now().isoformat()
            }, f, indent=2)
    
    def register_agent(self, agent_id, capabilities, endpoint=None):
        self.agents[agent_id] = {
            'capabilities': capabilities,
            'endpoint': endpoint,
            'state': AgentState.RUNNING.value,
            'health_score': 100.0,
            'failures': 0,
            'last_check': time.time(),
            'registered': datetime.now().isoformat(),
            'uptime': 0,
            'consecutive_failures': 0
        }
        self.save_state()
        return {'status': 'registered', 'agent_id': agent_id}
    
    def update_health(self, agent_id, health_score):
        if agent_id not in self.agents:
            return {'error': 'Agent not found'}
        
        agent = self.agents[agent_id]
        agent['health_score'] = health_score
        agent['last_check'] = time.time()
        
        # 状态评估
        if health_score >= 70:
            agent['state'] = AgentState.RUNNING.value
            agent['consecutive_failures'] = 0
        elif health_score >= 50:
            agent['state'] = AgentState.DEGRADED.value
        else:
            agent['state'] = AgentState.UNHEALTHY.value
            agent['consecutive_failures'] += 1
            
            if agent['consecutive_failures'] >= 3:
                agent['state'] = AgentState.FAILED.value
                self.stats['failovers'] += 1
        
        self.stats['checks'] += 1
        self.save_state()
        return {'status': 'updated', 'state': agent['state']}
    
    def get_agent_status(self, agent_id):
        if agent_id not in self.agents:
            return {'error': 'Agent not found'}
        return self.agents[agent_id]
    
    def list_agents(self):
        return {
            'agents': self.agents,
            'stats': self.stats,
            'total': len(self.agents)
        }
    
    def trigger_recovery(self, agent_id):
        if agent_id not in self.agents:
            return {'error': 'Agent not found'}
        
        agent = self.agents[agent_id]
        agent['state'] = AgentState.RECOVERING.value
        self.stats['recoveries'] += 1
        self.save_state()
        
        # 模拟恢复操作
        time.sleep(0.5)
        agent['state'] = AgentState.RUNNING.value
        agent['health_score'] = 90.0
        agent['consecutive_failures'] = 0
        self.save_state()
        
        return {'status': 'recovered', 'agent_id': agent_id}
    
    def remove_agent(self, agent_id):
        if agent_id in self.agents:
            del self.agents[agent_id]
            self.save_state()
            return {'status': 'removed', 'agent_id': agent_id}
        return {'error': 'Agent not found'}

# 全局管理器
manager = LifecycleManager()

# API路由
async def health(request):
    return web.json_response({
        'status': 'ok',
        'service': 'agent-lifecycle-manager',
        'port': 18130,
        'timestamp': datetime.now().isoformat()
    })

async def register_agent(request):
    data = await request.json()
    agent_id = data.get('agent_id')
    capabilities = data.get('capabilities', [])
    endpoint = data.get('endpoint')
    
    if not agent_id:
        return web.json_response({'error': 'agent_id required'}, status=400)
    
    result = manager.register_agent(agent_id, capabilities, endpoint)
    return web.json_response(result)

async def update_health(request):
    data = await request.json()
    agent_id = data.get('agent_id')
    health_score = data.get('health_score', 100.0)
    
    if not agent_id:
        return web.json_response({'error': 'agent_id required'}, status=400)
    
    result = manager.update_health(agent_id, health_score)
    return web.json_response(result)

async def get_status(request):
    agent_id = request.match_info.get('agent_id')
    if agent_id:
        result = manager.get_agent_status(agent_id)
        if 'error' in result:
            return web.json_response(result, status=404)
        return web.json_response(result)
    else:
        return web.json_response(manager.list_agents())

async def recovery(request):
    agent_id = request.match_info.get('agent_id')
    result = manager.trigger_recovery(agent_id)
    if 'error' in result:
        return web.json_response(result, status=404)
    return web.json_response(result)

async def remove_agent(request):
    agent_id = request.match_info.get('agent_id')
    result = manager.remove_agent(agent_id)
    if 'error' in result:
        return web.json_response(result, status=404)
    return web.json_response(result)

async def stats(request):
    return web.json_response(manager.stats)

def main():
    app = web.Application()
    app.router.add_get('/health', health)
    app.router.add_post('/agents/register', register_agent)
    app.router.add_post('/agents/health', update_health)
    app.router.add_get('/agents', get_status)
    app.router.add_get('/agents/{agent_id}', get_status)
    app.router.add_post('/agents/{agent_id}/recovery', recovery)
    app.router.add_delete('/agents/{agent_id}', remove_agent)
    app.router.add_get('/stats', stats)
    
    logger.info("Agent生命周期管理 API 启动 - 端口 18130")
    web.run_app(app, host='0.0.0.0', port=18130)

if __name__ == '__main__':
    main()