#!/usr/bin/env python3
"""
Agent自动化部署器 - 第48世
实现Agent的自动化部署、扩缩容、版本管理
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import threading

DEPLOY_STATE_FILE = "/root/.openclaw/workspace/ultron/data/deploy_state.json"
AGENTS_DIR = "/root/.openclaw/workspace/ultron/agents"

class AgentDeployer:
    def __init__(self):
        self.state = self._load_state()
        self.lock = threading.Lock()
    
    def _load_state(self) -> Dict:
        """加载部署状态"""
        os.makedirs(os.path.dirname(DEPLOY_STATE_FILE), exist_ok=True)
        if os.path.exists(DEPLOY_STATE_FILE):
            with open(DEPLOY_STATE_FILE, 'r') as f:
                return json.load(f)
        return {
            "deployments": {},
            "history": [],
            "versions": {},
            "last_update": datetime.now().isoformat()
        }
    
    def _save_state(self):
        """保存部署状态"""
        self.state["last_update"] = datetime.now().isoformat()
        with open(DEPLOY_STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def register_agent(self, name: str, config: Dict) -> Dict:
        """注册新Agent"""
        with self.lock:
            if name in self.state["deployments"]:
                return {"status": "error", "message": f"Agent {name} already exists"}
            
            deployment = {
                "name": name,
                "status": "registered",
                "config": config,
                "created_at": datetime.now().isoformat(),
                "version": "1.0.0",
                "replicas": config.get("replicas", 1),
                "resources": config.get("resources", {"cpu": "100m", "memory": "128Mi"}),
                "health_check": config.get("health_check", {"enabled": True, "interval": 30}),
                "auto_scale": config.get("auto_scale", {"enabled": False, "min_replicas": 1, "max_replicas": 3})
            }
            
            self.state["deployments"][name] = deployment
            self.state["versions"][name] = ["1.0.0"]
            self._save_state()
            
            return {"status": "success", "deployment": deployment}
    
    def deploy_agent(self, name: str, version: Optional[str] = None) -> Dict:
        """部署Agent"""
        with self.lock:
            if name not in self.state["deployments"]:
                return {"status": "error", "message": f"Agent {name} not found"}
            
            deployment = self.state["deployments"][name]
            
            if version and version not in self.state["versions"].get(name, []):
                return {"status": "error", "message": f"Version {version} not found"}
            
            target_version = version or deployment["version"]
            
            # 模拟部署过程
            deployment["status"] = "deploying"
            deployment["deploying_version"] = target_version
            deployment["deployed_at"] = datetime.now().isoformat()
            self._save_state()
            
            # 执行部署
            success = self._execute_deploy(name, target_version)
            
            if success:
                deployment["status"] = "running"
                deployment["version"] = target_version
                deployment["last_deploy"] = datetime.now().isoformat()
                if target_version not in self.state["versions"][name]:
                    self.state["versions"][name].append(target_version)
            else:
                deployment["status"] = "failed"
            
            self._save_state()
            return {"status": "success" if success else "failed", "deployment": deployment}
    
    def _execute_deploy(self, name: str, version: str) -> bool:
        """执行实际部署"""
        # 检查agents目录
        agent_script = f"{AGENTS_DIR}/{name}.py"
        if not os.path.exists(agent_script):
            # 创建默认agent脚本
            self._create_default_agent(name, version)
        
        time.sleep(0.5)  # 模拟部署时间
        return True
    
    def _create_default_agent(self, name: str, version: str):
        """创建默认Agent脚本"""
        agent_dir = Path(AGENTS_DIR)
        agent_dir.mkdir(exist_ok=True)
        
        script_content = f'''#!/usr/bin/env python3
"""
Auto-generated Agent: {name}
Version: {version}
"""

def main():
    print(f"Agent {name} v{version} running...")

if __name__ == "__main__":
    main()
'''
        with open(f"{AGENTS_DIR}/{name}.py", 'w') as f:
            f.write(script_content)
    
    def scale_agent(self, name: str, replicas: int) -> Dict:
        """扩缩容"""
        with self.lock:
            if name not in self.state["deployments"]:
                return {"status": "error", "message": f"Agent {name} not found"}
            
            deployment = self.state["deployments"][name]
            old_replicas = deployment.get("replicas", 1)
            deployment["replicas"] = replicas
            deployment["scaled_at"] = datetime.now().isoformat()
            
            self.state["history"].append({
                "action": "scale",
                "agent": name,
                "old_replicas": old_replicas,
                "new_replicas": replicas,
                "timestamp": datetime.now().isoformat()
            })
            
            self._save_state()
            return {"status": "success", "old_replicas": old_replicas, "new_replicas": replicas}
    
    def stop_agent(self, name: str) -> Dict:
        """停止Agent"""
        with self.lock:
            if name not in self.state["deployments"]:
                return {"status": "error", "message": f"Agent {name} not found"}
            
            deployment = self.state["deployments"][name]
            deployment["status"] = "stopped"
            deployment["stopped_at"] = datetime.now().isoformat()
            
            self._save_state()
            return {"status": "success", "deployment": deployment}
    
    def delete_agent(self, name: str) -> Dict:
        """删除Agent"""
        with self.lock:
            if name not in self.state["deployments"]:
                return {"status": "error", "message": f"Agent {name} not found"}
            
            del self.state["deployments"][name]
            self._save_state()
            return {"status": "success", "message": f"Agent {name} deleted"}
    
    def get_deployment(self, name: str) -> Dict:
        """获取部署状态"""
        return self.state["deployments"].get(name, {})
    
    def list_deployments(self, status: Optional[str] = None) -> List[Dict]:
        """列出所有部署"""
        deployments = list(self.state["deployments"].values())
        if status:
            deployments = [d for d in deployments if d["status"] == status]
        return deployments
    
    def get_versions(self, name: str) -> List[str]:
        """获取Agent版本历史"""
        return self.state["versions"].get(name, [])
    
    def rollback(self, name: str, version: Optional[str] = None) -> Dict:
        """回滚Agent版本"""
        with self.lock:
            if name not in self.state["deployments"]:
                return {"status": "error", "message": f"Agent {name} not found"}
            
            versions = self.state["versions"].get(name, [])
            if len(versions) < 2:
                return {"status": "error", "message": "No previous version to rollback"}
            
            target_version = version or versions[-2]
            return self.deploy_agent(name, target_version)
    
    def get_health(self, name: str) -> Dict:
        """获取Agent健康状态"""
        if name not in self.state["deployments"]:
            return {"status": "error", "message": f"Agent {name} not found"}
        
        deployment = self.state["deployments"][name]
        status = deployment.get("status", "unknown")
        
        health = {
            "name": name,
            "status": status,
            "healthy": status == "running",
            "version": deployment.get("version", "unknown"),
            "replicas": deployment.get("replicas", 1),
            "uptime": deployment.get("deployed_at", "")
        }
        
        return health

# Flask API
from flask import Flask, request, jsonify

app = Flask(__name__)
deployer = AgentDeployer()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "agent-deployer"})

@app.route('/api/deployments', methods=['GET'])
def list_deployments():
    status = request.args.get('status')
    return jsonify(deployer.list_deployments(status))

@app.route('/api/deployments', methods=['POST'])
def create_deployment():
    data = request.json
    name = data.get('name')
    config = data.get('config', {})
    return jsonify(deployer.register_agent(name, config))

@app.route('/api/deployments/<name>', methods=['GET'])
def get_deployment(name):
    return jsonify(deployer.get_deployment(name))

@app.route('/api/deployments/<name>/deploy', methods=['POST'])
def deploy(name):
    version = request.json.get('version') if request.json else None
    return jsonify(deployer.deploy_agent(name, version))

@app.route('/api/deployments/<name>/scale', methods=['POST'])
def scale(name):
    replicas = request.json.get('replicas', 1)
    return jsonify(deployer.scale_agent(name, replicas))

@app.route('/api/deployments/<name>/stop', methods=['POST'])
def stop(name):
    return jsonify(deployer.stop_agent(name))

@app.route('/api/deployments/<name>', methods=['DELETE'])
def delete(name):
    return jsonify(deployer.delete_agent(name))

@app.route('/api/deployments/<name>/versions', methods=['GET'])
def versions(name):
    return jsonify(deployer.get_versions(name))

@app.route('/api/deployments/<name>/rollback', methods=['POST'])
def rollback(name):
    version = request.json.get('version') if request.json else None
    return jsonify(deployer.rollback(name, version))

@app.route('/api/deployments/<name>/health', methods=['GET'])
def agent_health(name):
    return jsonify(deployer.get_health(name))

if __name__ == '__main__':
    print("🚀 Agent Deployer starting on port 8096...")
    app.run(host='0.0.0.0', port=8096, debug=False)