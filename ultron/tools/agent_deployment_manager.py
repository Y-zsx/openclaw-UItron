#!/usr/bin/env python3
"""
Agent自动化部署与编排系统
功能：
- 部署配置管理 (YAML/JSON)
- 部署流水线 (build -> test -> deploy)
- 滚动更新与回滚
- 版本管理
- 部署状态跟踪
端口: 18145
"""

import json
import os
import sys
import subprocess
import time
import uuid
import threading
import shutil
import hashlib
import tarfile
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
import traceback

# 配置
PORT = 18145
DEPLOY_BASE = Path("/root/.openclaw/workspace/ultron-data/deployments")
DEPLOY_CONFIG_DIR = DEPLOY_BASE / "configs"
DEPLOY_VERSIONS_DIR = DEPLOY_BASE / "versions"
DEPLOY_LOGS_DIR = DEPLOY_BASE / "logs"
DEPLOY_BACKUPS_DIR = DEPLOY_BASE / "backups"

for d in [DEPLOY_BASE, DEPLOY_CONFIG_DIR, DEPLOY_VERSIONS_DIR, DEPLOY_LOGS_DIR, DEPLOY_BACKUPS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

class DeploymentConfig:
    """部署配置"""
    def __init__(self, config_id=None):
        self.config_id = config_id or str(uuid.uuid4())[:12]
        self.name = ""
        self.agent_type = ""
        self.image = ""
        self.command = []
        self.env = {}
        self.resources = {
            "cpu": "100m",
            "memory": "128Mi",
            "disk": "500Mi"
        }
        self.health_check = {
            "enabled": True,
            "path": "/health",
            "port": 8000,
            "interval": 30,
            "timeout": 10,
            "retries": 3
        }
        self.replicas = 1
        self.strategy = "RollingUpdate"  # RollingUpdate, BlueGreen, Canary
        self.canary_percentage = 0
        self.rollback_enabled = True
        self.max_rollback_versions = 5
        self.autoscale = {
            "enabled": False,
            "min_replicas": 1,
            "max_replicas": 3,
            "target_cpu_percent": 70
        }
        self.dependencies = []
        self.volumes = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "config_id": self.config_id,
            "name": self.name,
            "agent_type": self.agent_type,
            "image": self.image,
            "command": self.command,
            "env": self.env,
            "resources": self.resources,
            "health_check": self.health_check,
            "replicas": self.replicas,
            "strategy": self.strategy,
            "canary_percentage": self.canary_percentage,
            "rollback_enabled": self.rollback_enabled,
            "max_rollback_versions": self.max_rollback_versions,
            "autoscale": self.autoscale,
            "dependencies": self.dependencies,
            "volumes": self.volumes,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data):
        config = cls(data.get("config_id"))
        config.name = data.get("name", "")
        config.agent_type = data.get("agent_type", "")
        config.image = data.get("image", "")
        config.command = data.get("command", [])
        config.env = data.get("env", {})
        config.resources = data.get("resources", {"cpu": "100m", "memory": "128Mi", "disk": "500Mi"})
        config.health_check = data.get("health_check", {"enabled": True, "path": "/health", "port": 8000, "interval": 30, "timeout": 10, "retries": 3})
        config.replicas = data.get("replicas", 1)
        config.strategy = data.get("strategy", "RollingUpdate")
        config.canary_percentage = data.get("canary_percentage", 0)
        config.rollback_enabled = data.get("rollback_enabled", True)
        config.max_rollback_versions = data.get("max_rollback_versions", 5)
        config.autoscale = data.get("autoscale", {"enabled": False, "min_replicas": 1, "max_replicas": 3, "target_cpu_percent": 70})
        config.dependencies = data.get("dependencies", [])
        config.volumes = data.get("volumes", [])
        config.created_at = data.get("created_at", datetime.now().isoformat())
        config.updated_at = data.get("updated_at", datetime.now().isoformat())
        return config


class DeploymentVersion:
    """部署版本"""
    def __init__(self, version_id=None):
        self.version_id = version_id or str(uuid.uuid4())[:12]
        self.config_id = ""
        self.version = "1.0.0"
        self.build_id = ""
        self.manifest = {}  # 部署清单
        self.checksum = ""
        self.size = 0
        self.status = "pending"  # pending, building, testing, deploying, deployed, failed, rolled_back
        self.build_log = ""
        self.test_results = {}
        self.deployed_at = None
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "version_id": self.version_id,
            "config_id": self.config_id,
            "version": self.version,
            "build_id": self.build_id,
            "manifest": self.manifest,
            "checksum": self.checksum,
            "size": self.size,
            "status": self.status,
            "build_log": self.build_log,
            "test_results": self.test_results,
            "deployed_at": self.deployed_at,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data):
        ver = cls(data.get("version_id"))
        ver.config_id = data.get("config_id", "")
        ver.version = data.get("version", "1.0.0")
        ver.build_id = data.get("build_id", "")
        ver.manifest = data.get("manifest", {})
        ver.checksum = data.get("checksum", "")
        ver.size = data.get("size", 0)
        ver.status = data.get("status", "pending")
        ver.build_log = data.get("build_log", "")
        ver.test_results = data.get("test_results", {})
        ver.deployed_at = data.get("deployed_at")
        ver.created_at = data.get("created_at", datetime.now().isoformat())
        return ver


class DeploymentManager:
    """部署管理器"""
    def __init__(self):
        self.configs = {}  # config_id -> DeploymentConfig
        self.versions = {}  # version_id -> DeploymentVersion
        self.deployments = {}  # config_id -> current deployment status
        self.deployment_history = []  # 部署历史
        self.lock = threading.Lock()
        
        self._load_configs()
        self._load_versions()
    
    def _load_configs(self):
        """加载配置文件"""
        for f in DEPLOY_CONFIG_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                config = DeploymentConfig.from_dict(data)
                self.configs[config.config_id] = config
            except Exception as e:
                print(f"Failed to load config {f}: {e}")
    
    def _save_config(self, config):
        """保存配置文件"""
        f = DEPLOY_CONFIG_DIR / f"{config.config_id}.json"
        f.write_text(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
    
    def _load_versions(self):
        """加载版本文件"""
        for f in DEPLOY_VERSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                ver = DeploymentVersion.from_dict(data)
                self.versions[ver.version_id] = ver
            except Exception as e:
                print(f"Failed to load version {f}: {e}")
    
    def _save_version(self, ver):
        """保存版本文件"""
        f = DEPLOY_VERSIONS_DIR / f"{ver.version_id}.json"
        f.write_text(json.dumps(ver.to_dict(), indent=2, ensure_ascii=False))
    
    def create_config(self, name, agent_type, image, command=None, env=None, **kwargs):
        """创建部署配置"""
        config = DeploymentConfig()
        config.name = name
        config.agent_type = agent_type
        config.image = image
        config.command = command or []
        config.env = env or {}
        
        for k, v in kwargs.items():
            if hasattr(config, k):
                setattr(config, k, v)
        
        with self.lock:
            self.configs[config.config_id] = config
            self._save_config(config)
        
        return config
    
    def update_config(self, config_id, **updates):
        """更新部署配置"""
        with self.lock:
            if config_id not in self.configs:
                return None
            
            config = self.configs[config_id]
            for k, v in updates.items():
                if hasattr(config, k):
                    setattr(config, k, v)
            config.updated_at = datetime.now().isoformat()
            self._save_config(config)
        
        return config
    
    def delete_config(self, config_id):
        """删除部署配置"""
        with self.lock:
            if config_id in self.configs:
                del self.configs[config_id]
                f = DEPLOY_CONFIG_DIR / f"{config_id}.json"
                if f.exists():
                    f.unlink()
                return True
            return False
    
    def get_config(self, config_id):
        return self.configs.get(config_id)
    
    def list_configs(self):
        return list(self.configs.values())
    
    def build_version(self, config_id, version=None, manifest=None):
        """构建版本"""
        config = self.get_config(config_id)
        if not config:
            return None
        
        ver = DeploymentVersion()
        ver.config_id = config_id
        ver.version = version or self._generate_version(config_id)
        ver.build_id = str(uuid.uuid4())[:12]
        ver.manifest = manifest or {
            "image": config.image,
            "command": config.command,
            "env": config.env,
            "resources": config.resources,
            "health_check": config.health_check,
            "replicas": config.replicas,
            "strategy": config.strategy
        }
        
        # 计算checksum
        manifest_str = json.dumps(ver.manifest, sort_keys=True)
        ver.checksum = hashlib.sha256(manifest_str.encode()).hexdigest()[:16]
        
        ver.status = "building"
        
        with self.lock:
            self.versions[ver.version_id] = ver
            self._save_version(ver)
        
        # 执行构建
        self._execute_build(ver)
        
        return ver
    
    def _generate_version(self, config_id):
        """生成版本号"""
        existing = [v.version for v in self.versions.values() if v.config_id == config_id]
        if not existing:
            return "1.0.0"
        
        latest = max(existing, key=lambda x: [int(n) for n in x.split('.')])
        parts = latest.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        return '.'.join(parts)
    
    def _execute_build(self, ver):
        """执行构建"""
        config = self.get_config(ver.config_id)
        if not config:
            ver.status = "failed"
            ver.build_log = "Config not found"
            self._save_version(ver)
            return
        
        build_log = []
        build_log.append(f"[{datetime.now().isoformat()}] Starting build {ver.build_id}")
        
        try:
            # 模拟构建过程
            build_log.append(f"[{datetime.now().isoformat()}] Pulling image: {config.image}")
            time.sleep(0.5)
            
            build_log.append(f"[{datetime.now().isoformat()}] Preparing deployment package")
            time.sleep(0.3)
            
            # 创建部署包
            pkg_path = DEPLOY_VERSIONS_DIR / f"{ver.version_id}.tar.gz"
            ver.size = 0
            
            build_log.append(f"[{datetime.now().isoformat()}] Build completed successfully")
            ver.status = "testing"
            ver.build_log = '\n'.join(build_log)
            
            # 运行测试
            self._run_tests(ver, build_log)
            
        except Exception as e:
            build_log.append(f"[{datetime.now().isoformat()}] Build failed: {str(e)}")
            ver.status = "failed"
            ver.build_log = '\n'.join(build_log)
        
        self._save_version(ver)
    
    def _run_tests(self, ver, build_log):
        """运行测试"""
        build_log.append(f"[{datetime.now().isoformat()}] Running tests...")
        
        # 模拟测试
        time.sleep(0.5)
        
        ver.test_results = {
            "passed": True,
            "tests": [
                {"name": "config_validation", "status": "passed"},
                {"name": "health_check", "status": "passed"},
                {"name": "resource_limits", "status": "passed"}
            ]
        }
        
        if ver.test_results["passed"]:
            ver.status = "deployed"
            ver.deployed_at = datetime.now().isoformat()
            build_log.append(f"[{datetime.now().isoformat()}] All tests passed")
        else:
            ver.status = "failed"
            build_log.append(f"[{datetime.now().isoformat()}] Tests failed")
        
        ver.build_log = '\n'.join(build_log)
    
    def deploy_version(self, version_id, strategy=None):
        """部署版本"""
        ver = self.versions.get(version_id)
        if not ver:
            return None
        
        config = self.get_config(ver.config_id)
        if not config:
            return None
        
        strategy = strategy or config.strategy
        
        # 更新状态
        ver.status = "deploying"
        self._save_version(ver)
        
        with self.lock:
            # 记录部署历史
            self.deployment_history.append({
                "version_id": version_id,
                "config_id": ver.config_id,
                "version": ver.version,
                "strategy": strategy,
                "deployed_at": datetime.now().isoformat(),
                "status": "deploying"
            })
        
        # 执行部署策略
        if strategy == "RollingUpdate":
            success = self._deploy_rolling(ver, config)
        elif strategy == "BlueGreen":
            success = self._deploy_blue_green(ver, config)
        elif strategy == "Canary":
            success = self._deploy_canary(ver, config)
        else:
            success = self._deploy_rolling(ver, config)
        
        if success:
            ver.status = "deployed"
            ver.deployed_at = datetime.now().isoformat()
            
            # 更新当前部署
            self.deployments[ver.config_id] = {
                "version_id": version_id,
                "version": ver.version,
                "deployed_at": ver.deployed_at,
                "status": "running"
            }
        else:
            ver.status = "failed"
        
        self._save_version(ver)
        return ver
    
    def _deploy_rolling(self, ver, config):
        """滚动更新"""
        # 模拟滚动更新
        time.sleep(0.5)
        
        # 检查依赖
        for dep in config.dependencies:
            dep_deploy = self.deployments.get(dep)
            if not dep_deploy or dep_deploy.get("status") != "running":
                return False
        
        return True
    
    def _deploy_blue_green(self, ver, config):
        """蓝绿部署"""
        time.sleep(0.5)
        return True
    
    def _deploy_canary(self, ver, config):
        """金丝雀部署"""
        time.sleep(0.3)
        return True
    
    def rollback(self, config_id, target_version=None):
        """回滚"""
        config = self.get_config(config_id)
        if not config or not config.rollback_enabled:
            return None
        
        current = self.deployments.get(config_id)
        if not current:
            return None
        
        # 找到可回滚的版本
        candidates = [v for v in self.versions.values() 
                      if v.config_id == config_id and v.status == "deployed"]
        
        if not candidates:
            return None
        
        if target_version:
            target = next((v for v in candidates if v.version == target_version), None)
        else:
            # 回滚到上一个版本
            candidates.sort(key=lambda x: x.created_at, reverse=True)
            target = candidates[1] if len(candidates) > 1 else candidates[0]
        
        if target:
            target.status = "rolling_back"
            self._save_version(target)
            
            # 执行回滚
            time.sleep(0.3)
            
            target.status = "deployed"
            target.deployed_at = datetime.now().isoformat()
            self._save_version(target)
            
            self.deployments[config_id] = {
                "version_id": target.version_id,
                "version": target.version,
                "deployed_at": target.deployed_at,
                "status": "running",
                "rolled_back": True
            }
            
            return target
        
        return None
    
    def get_version(self, version_id):
        return self.versions.get(version_id)
    
    def list_versions(self, config_id=None):
        versions = list(self.versions.values())
        if config_id:
            versions = [v for v in versions if v.config_id == config_id]
        return sorted(versions, key=lambda x: x.created_at, reverse=True)
    
    def get_deployment_status(self, config_id):
        return self.deployments.get(config_id)
    
    def get_deployment_history(self, config_id=None, limit=50):
        history = self.deployment_history
        if config_id:
            history = [h for h in history if h.get("config_id") == config_id]
        return history[-limit:]


# HTTP Handler
class DeploymentHandler(BaseHTTPRequestHandler):
    manager = DeploymentManager()
    
    def log_message(self, format, *args):
        pass
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == "/" or path == "/health":
            self.send_json({"status": "ok", "service": "deployment-manager", "port": PORT})
        
        elif path == "/configs":
            configs = self.manager.list_configs()
            self.send_json({"configs": [c.to_dict() for c in configs]})
        
        elif path.startswith("/config/"):
            config_id = path.split("/")[-1]
            config = self.manager.get_config(config_id)
            if config:
                self.send_json(config.to_dict())
            else:
                self.send_json({"error": "Config not found"}, 404)
        
        elif path == "/versions":
            config_id = params.get("config_id", [None])[0]
            versions = self.manager.list_versions(config_id)
            self.send_json({"versions": [v.to_dict() for v in versions]})
        
        elif path.startswith("/version/"):
            version_id = path.split("/")[-1]
            version = self.manager.get_version(version_id)
            if version:
                self.send_json(version.to_dict())
            else:
                self.send_json({"error": "Version not found"}, 404)
        
        elif path == "/deployments":
            status = {cid: s for cid, s in self.manager.deployments.items()}
            self.send_json({"deployments": status})
        
        elif path.startswith("/deployment/"):
            config_id = path.split("/")[-1]
            status = self.manager.get_deployment_status(config_id)
            if status:
                self.send_json(status)
            else:
                self.send_json({"error": "Deployment not found"}, 404)
        
        elif path == "/history":
            config_id = params.get("config_id", [None])[0]
            limit = int(params.get("limit", [50])[0])
            history = self.manager.get_deployment_history(config_id, limit)
            self.send_json({"history": history})
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == "/configs":
            config = self.manager.create_config(
                name=data.get("name", "unnamed"),
                agent_type=data.get("agent_type", ""),
                image=data.get("image", ""),
                command=data.get("command", []),
                env=data.get("env", {}),
                **{k: v for k, v in data.items() 
                   if k not in ["name", "agent_type", "image", "command", "env"]}
            )
            self.send_json({"config": config.to_dict(), "config_id": config.config_id})
        
        elif path.startswith("/config/"):
            config_id = path.split("/")[-1]
            if config_id == "delete":
                # 删除配置
                config_id = data.get("config_id")
                if config_id:
                    success = self.manager.delete_config(config_id)
                    self.send_json({"success": success})
                else:
                    self.send_json({"error": "config_id required"}, 400)
            else:
                config = self.manager.update_config(config_id, **data)
                if config:
                    self.send_json(config.to_dict())
                else:
                    self.send_json({"error": "Config not found"}, 404)
        
        elif path == "/build":
            version = self.manager.build_version(
                config_id=data.get("config_id"),
                version=data.get("version"),
                manifest=data.get("manifest")
            )
            if version:
                self.send_json(version.to_dict())
            else:
                self.send_json({"error": "Config not found"}, 404)
        
        elif path == "/deploy":
            version = self.manager.deploy_version(
                version_id=data.get("version_id"),
                strategy=data.get("strategy")
            )
            if version:
                self.send_json(version.to_dict())
            else:
                self.send_json({"error": "Version not found"}, 404)
        
        elif path == "/rollback":
            version = self.manager.rollback(
                config_id=data.get("config_id"),
                target_version=data.get("version")
            )
            if version:
                self.send_json(version.to_dict())
            else:
                self.send_json({"error": "Rollback not possible"}, 400)
        
        else:
            self.send_json({"error": "Not found"}, 404)


def main():
    server = HTTPServer(('0.0.0.0', PORT), DeploymentHandler)
    print(f"Agent Deployment Manager running on port {PORT}")
    sys.stdout.flush()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()