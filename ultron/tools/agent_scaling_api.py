#!/usr/bin/env python3
"""
Agent资源调度与自动扩缩容API服务 - 第68世
功能：
- Agent资源使用监控
- 自动扩缩容策略
- 资源调度优化
- 弹性伸缩API
"""

import json
import time
import threading
import psutil
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

PORT = 18131

# 扩缩容策略类型
class ScalingStrategy(Enum):
    HORIZONTAL = "horizontal"      # 水平扩缩容（增加/减少实例）
    VERTICAL = "vertical"          # 垂直扩缩容（增加/减少资源）
    PREDICTIVE = "predictive"      # 预测性扩缩容
    REACTIVE = "reactive"          # 响应式扩缩容

# 扩缩容动作
class ScalingAction(Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"

@dataclass
class AgentMetrics:
    """Agent资源指标"""
    agent_id: str
    cpu_percent: float
    memory_percent: float
    request_count: int
    response_time_ms: float
    error_rate: float
    timestamp: str

@dataclass
class ScalingRule:
    """扩缩容规则"""
    rule_id: str
    agent_type: str
    min_instances: int
    max_instances: int
    scale_up_threshold: float  # CPU/内存阈值
    scale_down_threshold: float
    cooldown_seconds: int
    target_metrics: List[str]

@dataclass
class ScalingDecision:
    """扩缩容决策"""
    decision_id: str
    agent_type: str
    action: str
    current_instances: int
    target_instances: int
    reason: str
    timestamp: str

class AgentScalingManager:
    """Agent资源调度与扩缩容管理器"""
    
    def __init__(self):
        self.agents: Dict[str, Dict] = {}
        self.scaling_rules: Dict[str, ScalingRule] = {}
        self.scaling_history: List[ScalingDecision] = []
        self.cooldowns: Dict[str, float] = {}
        self.metrics_history: Dict[str, List[AgentMetrics]] = {}
        self.lock = threading.Lock()
        
        self._init_default_rules()
        self._init_demo_agents()
        self._start_monitoring()
    
    def _init_default_rules(self):
        """初始化默认扩缩容规则"""
        rules = [
            ScalingRule(
                rule_id="worker_scale",
                agent_type="worker",
                min_instances=1,
                max_instances=10,
                scale_up_threshold=70.0,
                scale_down_threshold=20.0,
                cooldown_seconds=60,
                target_metrics=["cpu_percent", "memory_percent"]
            ),
            ScalingRule(
                rule_id="api_scale", 
                agent_type="api",
                min_instances=1,
                max_instances=5,
                scale_up_threshold=75.0,
                scale_down_threshold=25.0,
                cooldown_seconds=120,
                target_metrics=["cpu_percent", "request_count"]
            ),
            ScalingRule(
                rule_id="monitor_scale",
                agent_type="monitor",
                min_instances=1,
                max_instances=3,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                cooldown_seconds=180,
                target_metrics=["cpu_percent", "memory_percent"]
            )
        ]
        for rule in rules:
            self.scaling_rules[rule.agent_type] = rule
    
    def _init_demo_agents(self):
        """初始化演示Agent"""
        self.agents = {
            "worker-1": {"type": "worker", "instances": 2, "status": "active", "cpu": 45.0, "memory": 50.0},
            "worker-2": {"type": "worker", "instances": 2, "status": "active", "cpu": 60.0, "memory": 55.0},
            "api-1": {"type": "api", "instances": 1, "status": "active", "cpu": 35.0, "memory": 40.0},
            "monitor-1": {"type": "monitor", "instances": 1, "status": "active", "cpu": 25.0, "memory": 30.0},
            "ultron-core": {"type": "core", "instances": 1, "status": "active", "cpu": 20.0, "memory": 35.0},
        }
    
    def _start_monitoring(self):
        """启动监控"""
        def monitor_loop():
            while True:
                self._collect_metrics()
                time.sleep(10)
        
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
    
    def _collect_metrics(self):
        """收集系统指标"""
        with self.lock:
            # 更新系统资源使用
            system_cpu = psutil.cpu_percent(interval=0.1)
            system_memory = psutil.virtual_memory().percent
            
            # 模拟Agent指标更新
            for agent_id, agent in self.agents.items():
                if agent["status"] == "active":
                    # 模拟负载变化
                    agent["cpu"] = min(100, max(5, agent["cpu"] + (hash(agent_id) % 21 - 10)))
                    agent["memory"] = min(100, max(10, agent["memory"] + (hash(agent_id + str(time.time())) % 15 - 7)))
    
    def register_agent(self, agent_id: str, agent_type: str, initial_instances: int = 1) -> Dict:
        """注册Agent"""
        with self.lock:
            self.agents[agent_id] = {
                "type": agent_type,
                "instances": initial_instances,
                "status": "active",
                "cpu": 10.0,
                "memory": 20.0,
                "registered_at": datetime.now().isoformat()
            }
            
            if agent_type not in self.scaling_rules:
                # 创建默认规则
                self.scaling_rules[agent_type] = ScalingRule(
                    rule_id=f"{agent_type}_scale",
                    agent_type=agent_type,
                    min_instances=1,
                    max_instances=5,
                    scale_up_threshold=70.0,
                    scale_down_threshold=20.0,
                    cooldown_seconds=60,
                    target_metrics=["cpu_percent"]
                )
            
            return {"status": "registered", "agent_id": agent_id, "type": agent_type}
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """获取Agent状态"""
        return self.agents.get(agent_id)
    
    def get_all_agents(self) -> Dict:
        """获取所有Agent"""
        return self.agents
    
    def get_scaling_decisions(self) -> List[Dict]:
        """获取扩缩容决策"""
        decisions = []
        for decision in self.scaling_history[-20:]:
            decisions.append(asdict(decision))
        return decisions
    
    def evaluate_scaling(self, agent_id: str) -> ScalingDecision:
        """评估并执行扩缩容"""
        with self.lock:
            if agent_id not in self.agents:
                return None
            
            agent = self.agents[agent_id]
            agent_type = agent["type"]
            
            if agent_type not in self.scaling_rules:
                return None
            
            rule = self.scaling_rules[agent_type]
            current_time = time.time()
            
            # 检查冷却时间
            last_action = self.cooldowns.get(agent_id, 0)
            if current_time - last_action < rule.cooldown_seconds:
                return None
            
            cpu = agent["cpu"]
            memory = agent["memory"]
            current_instances = agent["instances"]
            
            # 评估决策
            action = ScalingAction.MAINTAIN
            target_instances = current_instances
            
            if cpu > rule.scale_up_threshold or memory > rule.scale_up_threshold:
                action = ScalingAction.SCALE_UP
                target_instances = min(current_instances + 1, rule.max_instances)
                reason = f"资源使用率过高 (CPU:{cpu:.1f}%, MEM:{memory:.1f}%)"
            elif cpu < rule.scale_down_threshold and memory < rule.scale_down_threshold and current_instances > rule.min_instances:
                action = ScalingAction.SCALE_DOWN
                target_instances = max(current_instances - 1, rule.min_instances)
                reason = f"资源使用率过低 (CPU:{cpu:.1f}%, MEM:{memory:.1f}%)"
            else:
                reason = f"资源使用率正常 (CPU:{cpu:.1f}%, MEM:{memory:.1f}%)"
            
            # 执行扩缩容
            if target_instances != current_instances:
                agent["instances"] = target_instances
                self.cooldowns[agent_id] = current_time
            
            decision = ScalingDecision(
                decision_id=f"dec_{int(current_time * 1000)}",
                agent_type=agent_type,
                action=action.value,
                current_instances=current_instances,
                target_instances=target_instances,
                reason=reason,
                timestamp=datetime.now().isoformat()
            )
            
            self.scaling_history.append(decision)
            
            return decision
    
    def evaluate_all_agents(self) -> List[Dict]:
        """评估所有Agent并返回决策"""
        decisions = []
        for agent_id in self.agents:
            decision = self.evaluate_scaling(agent_id)
            if decision:
                decisions.append(asdict(decision))
        return decisions
    
    def get_resource_metrics(self) -> Dict:
        """获取资源指标"""
        return {
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "timestamp": datetime.now().isoformat()
            },
            "agents": self.agents,
            "rules": {k: asdict(v) for k, v in self.scaling_rules.items()}
        }
    
    def update_scaling_rule(self, agent_type: str, 
                           min_instances: Optional[int] = None,
                           max_instances: Optional[int] = None,
                           scale_up_threshold: Optional[float] = None,
                           scale_down_threshold: Optional[float] = None) -> Dict:
        """更新扩缩容规则"""
        if agent_type not in self.scaling_rules:
            return {"error": "规则不存在"}
        
        rule = self.scaling_rules[agent_type]
        if min_instances is not None:
            rule.min_instances = min_instances
        if max_instances is not None:
            rule.max_instances = max_instances
        if scale_up_threshold is not None:
            rule.scale_up_threshold = scale_up_threshold
        if scale_down_threshold is not None:
            rule.scale_down_threshold = scale_down_threshold
        
        return {"status": "updated", "rule": asdict(rule)}

# 全局管理器
manager = AgentScalingManager()

class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def send_json(self, data: Dict, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        path = urlparse(self.path).path
        query = urlparse(self.path).query
        
        if path == '/':
            self.send_json({
                "service": "Agent资源调度与自动扩缩容API",
                "version": "1.0",
                "port": PORT,
                "endpoints": [
                    "GET / - 服务信息",
                    "GET /agents - 所有Agent状态",
                    "GET /agents/{id} - 单个Agent状态",
                    "POST /agents - 注册Agent",
                    "GET /decisions - 扩缩容决策历史",
                    "POST /evaluate/{id} - 评估单个Agent",
                    "POST /evaluate/all - 评估所有Agent",
                    "GET /metrics - 资源指标",
                    "PUT /rules/{type} - 更新扩缩容规则"
                ]
            })
        
        elif path == '/agents':
            self.send_json(manager.get_all_agents())
        
        elif path.startswith('/agents/'):
            agent_id = path.split('/')[-1]
            agent = manager.get_agent_status(agent_id)
            if agent:
                self.send_json(agent)
            else:
                self.send_json({"error": "Agent不存在"}, 404)
        
        elif path == '/decisions':
            self.send_json(manager.get_scaling_decisions())
        
        elif path == '/metrics':
            self.send_json(manager.get_resource_metrics())
        
        elif path.startswith('/evaluate/'):
            if path == '/evaluate/all':
                decisions = manager.evaluate_all_agents()
                self.send_json({"decisions": decisions})
            else:
                agent_id = path.split('/')[-1]
                decision = manager.evaluate_scaling(agent_id)
                if decision:
                    self.send_json(asdict(decision))
                else:
                    self.send_json({"error": "Agent不存在或处于冷却期"}, 404)
        
        elif path.startswith('/rules/'):
            agent_type = path.split('/')[-1]
            if agent_type in manager.scaling_rules:
                self.send_json(asdict(manager.scaling_rules[agent_type]))
            else:
                self.send_json({"error": "规则不存在"}, 404)
        
        else:
            self.send_json({"error": "Not Found"}, 404)
    
    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == '/agents':
            agent_id = data.get('agent_id')
            agent_type = data.get('type', 'worker')
            instances = data.get('instances', 1)
            
            if not agent_id:
                self.send_json({"error": "缺少agent_id"}, 400)
                return
            
            result = manager.register_agent(agent_id, agent_type, instances)
            self.send_json(result)
        
        elif path == '/evaluate/all':
            decisions = manager.evaluate_all_agents()
            self.send_json({"decisions": decisions, "count": len(decisions)})
        
        else:
            self.send_json({"error": "Not Found"}, 404)
    
    def do_PUT():
        path = urlparse(self.path).path
        
        if path.startswith('/rules/'):
            agent_type = path.split('/')[-1]
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
            data = json.loads(body)
            
            result = manager.update_scaling_rule(
                agent_type,
                data.get('min_instances'),
                data.get('max_instances'),
                data.get('scale_up_threshold'),
                data.get('scale_down_threshold')
            )
            self.send_json(result)
        else:
            self.send_json({"error": "Not Found"}, 404)

def main():
    server = HTTPServer(('0.0.0.0', PORT), APIHandler)
    print(f"🚀 Agent资源调度与自动扩缩容API - 端口{PORT}")
    print(f"📊 服务已启动")
    
    # 注册已有Agent
    for agent_id in ["worker-1", "worker-2", "api-1", "monitor-1", "ultron-core"]:
        manager.register_agent(agent_id, manager.agents[agent_id]["type"], manager.agents[agent_id]["instances"])
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")

if __name__ == '__main__':
    main()