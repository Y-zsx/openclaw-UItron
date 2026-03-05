#!/usr/bin/env python3
"""
Agent健康检测与自动故障恢复服务
端口: 18099
功能:
- 健康检查: 定期检查Agent存活状态
- 自动恢复: Agent故障时自动尝试恢复
- 故障转移: 自动将任务转移到健康Agent
- 告警机制: 异常状态时触发告警
"""
import sys
import os
import json
import time
import threading
import asyncio
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from typing import Dict, List, Optional

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENTS_DIR)

from agent_monitor import get_monitor
from agent_auto_repair import AgentAutoRepair
from agent_lifecycle_manager import AgentLifecycleManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('HealthRecovery')

app = Flask(__name__)

# 全局组件
lifecycle = AgentLifecycleManager()
auto_repair = AgentAutoRepair(lifecycle)
monitor = get_monitor()

# 健康检测配置
HEALTH_CHECK_INTERVAL = 30  # 秒
RECOVERY_ENABLED = True


class HealthRecoveryService:
    """健康检测与恢复服务"""
    
    def __init__(self):
        self.running = False
        self.check_thread = None
        self.recovery_thread = None
        self.alerts = []
        self.recovery_history = []
        
    def start(self):
        """启动服务"""
        self.running = True
        auto_repair.start()
        
        # 启动健康检测线程
        self.check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.check_thread.start()
        
        # 启动自动恢复线程
        self.recovery_thread = threading.Thread(target=self._recovery_loop, daemon=True)
        self.recovery_thread.start()
        
        logger.info("✅ 健康检测与自动故障恢复服务已启动")
        
    def stop(self):
        """停止服务"""
        self.running = False
        auto_repair.stop()
        logger.info("🛑 健康检测与自动故障恢复服务已停止")
        
    def _health_check_loop(self):
        """健康检测循环"""
        while self.running:
            try:
                self._perform_health_check()
            except Exception as e:
                logger.error(f"健康检查错误: {e}")
            time.sleep(HEALTH_CHECK_INTERVAL)
            
    def _recovery_loop(self):
        """自动恢复循环"""
        while self.running:
            try:
                self._perform_auto_recovery()
            except Exception as e:
                logger.error(f"自动恢复错误: {e}")
            time.sleep(HEALTH_CHECK_INTERVAL)
            
    def _perform_health_check(self):
        """执行健康检查"""
        agents = monitor.get_all_agents()
        current_time = datetime.now()
        
        for agent in agents:
            agent_id = agent.get('agent_id')
            last_seen = agent.get('last_seen')
            
            if last_seen:
                last_seen_time = datetime.fromisoformat(last_seen)
                idle_seconds = (current_time - last_seen_time).total_seconds()
                
                # 检查是否长时间无活动
                if idle_seconds > 300:  # 5分钟无活动
                    alert = {
                        "agent_id": agent_id,
                        "type": "agent_idle",
                        "level": "warning",
                        "message": f"Agent空闲时间过长: {int(idle_seconds)}s",
                        "timestamp": current_time.isoformat()
                    }
                    self.alerts.append(alert)
                    
                # 检查是否离线
                if agent.get('status') == 'offline':
                    alert = {
                        "agent_id": agent_id,
                        "type": "agent_offline",
                        "level": "critical",
                        "message": f"Agent已离线: {agent_id}",
                        "timestamp": current_time.isoformat()
                    }
                    self.alerts.append(alert)
                    
    def _perform_auto_recovery(self):
        """执行自动恢复"""
        if not RECOVERY_ENABLED:
            return
            
        # 检查告警并进行自动恢复
        for alert in self.alerts[-10:]:
            if alert['level'] in ['critical', 'error']:
                agent_id = alert['agent_id']
                
                # 尝试自动恢复
                result = auto_repair.force_repair(agent_id)
                if result:
                    recovery_record = {
                        "agent_id": agent_id,
                        "alert": alert,
                        "result": "success",
                        "timestamp": datetime.now().isoformat()
                    }
                    self.recovery_history.append(recovery_record)
                    
    def get_health_status(self) -> Dict:
        """获取健康状态"""
        agents = monitor.get_all_agents()
        
        healthy_count = 0
        unhealthy_count = 0
        
        for agent in agents:
            status = agent.get('status')
            if status in ['online', 'busy']:
                healthy_count += 1
            else:
                unhealthy_count += 1
                
        return {
            "total_agents": len(agents),
            "healthy_agents": healthy_count,
            "unhealthy_agents": unhealthy_count,
            "health_percentage": (healthy_count / len(agents) * 100) if agents else 0,
            "recovery_enabled": RECOVERY_ENABLED,
            "auto_repair_status": auto_repair.get_repair_stats(),
            "alerts_count": len(self.alerts),
            "recovery_count": len(self.recovery_history),
            "timestamp": datetime.now().isoformat()
        }
        
    def get_alerts(self) -> List[Dict]:
        """获取告警列表"""
        return self.alerts[-50:]
        
    def get_recovery_history(self) -> List[Dict]:
        """获取恢复历史"""
        return self.recovery_history[-50:]


# 全局服务实例
service = HealthRecoveryService()


# ==================== API端点 ====================

@app.route('/health')
def health():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "service": "health-recovery",
        "port": 18099,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/health/status')
def health_status():
    """获取健康状态"""
    return jsonify(service.get_health_status())


@app.route('/api/health/agents')
def health_agents():
    """获取所有Agent的健康状态"""
    agents = monitor.get_all_agents()
    
    health_agents = []
    for agent in agents:
        agent_id = agent.get('agent_id')
        
        # 获取最近的告警
        agent_alerts = [a for a in service.alerts if a.get('agent_id') == agent_id]
        
        health_agents.append({
            "agent_id": agent_id,
            "agent_name": agent.get('agent_name'),
            "status": agent.get('status'),
            "last_seen": agent.get('last_seen'),
            "cpu_usage": agent.get('cpu_usage'),
            "memory_usage": agent.get('memory_usage'),
            "health_score": 100 if agent.get('status') in ['online', 'busy'] else 0,
            "alerts_count": len(agent_alerts),
            "recent_alerts": agent_alerts[-3:]
        })
        
    return jsonify({
        "total": len(health_agents),
        "agents": health_agents
    })


@app.route('/api/health/agents/<agent_id>')
def health_agent(agent_id):
    """获取指定Agent的健康状态"""
    agents = monitor.get_all_agents()
    agent = next((a for a in agents if a.get('agent_id') == agent_id), None)
    
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
        
    agent_alerts = [a for a in service.alerts if a.get('agent_id') == agent_id]
    
    return jsonify({
        "agent_id": agent_id,
        "agent_name": agent.get('agent_name'),
        "status": agent.get('status'),
        "last_seen": agent.get('last_seen'),
        "cpu_usage": agent.get('cpu_usage'),
        "memory_usage": agent.get('memory_usage'),
        "health_score": 100 if agent.get('status') in ['online', 'busy'] else 0,
        "alerts": agent_alerts,
        "recovery_history": [r for r in service.recovery_history if r.get('agent_id') == agent_id]
    })


@app.route('/api/recovery/alerts')
def recovery_alerts():
    """获取告警列表"""
    return jsonify({
        "total": len(service.alerts),
        "alerts": service.get_alerts()
    })


@app.route('/api/recovery/history')
def recovery_history():
    """获取恢复历史"""
    return jsonify({
        "total": len(service.recovery_history),
        "history": service.get_recovery_history()
    })


@app.route('/api/recovery/repair', methods=['POST'])
def recovery_repair():
    """手动触发修复"""
    data = request.get_json()
    agent_id = data.get('agent_id')
    
    if not agent_id:
        return jsonify({"error": "agent_id is required"}), 400
        
    result = auto_repair.force_repair(agent_id)
    
    return jsonify({
        "agent_id": agent_id,
        "success": result,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/recovery/stats')
def recovery_stats():
    """获取恢复统计"""
    return jsonify(auto_repair.get_repair_stats())


if __name__ == "__main__":
    # 启动服务
    service.start()
    
    # 启动Flask API
    app.run(host='0.0.0.0', port=18101, debug=False)