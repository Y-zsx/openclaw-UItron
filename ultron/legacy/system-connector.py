#!/usr/bin/env python3
"""
奥创系统连接器框架 - 多系统数据聚合与统一视图
System Connector Framework - Multi-system Data Aggregation

功能:
- 系统连接器框架
- 数据统一格式转换
- 统一监控面板数据源
"""

import json
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading


class SystemType(Enum):
    """系统类型枚举"""
    OPENCLAW = "openclaw"
    SERVER = "server"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    DATABASE = "database"
    CUSTOM = "custom"


class ConnectionStatus(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class SystemEndpoint:
    """系统端点"""
    name: str
    system_type: SystemType
    host: str
    port: int
    protocol: str = "http"
    auth_token: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3


@dataclass
class SystemMetrics:
    """系统指标数据"""
    timestamp: float
    system_name: str
    status: str
    cpu: float = 0.0
    memory: float = 0.0
    disk: float = 0.0
    network_in: float = 0.0
    network_out: float = 0.0
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorConfig:
    """连接器配置"""
    max_connections: int = 10
    pool_size: int = 5
    collect_interval: int = 60
    enable_cache: bool = True
    cache_ttl: int = 300


class BaseConnector:
    """基础连接器"""
    
    def __init__(self, endpoint: SystemEndpoint, config: ConnectorConfig):
        self.endpoint = endpoint
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.last_data: Optional[SystemMetrics] = None
        self.last_error: Optional[str] = None
        self._lock = threading.Lock()
    
    async def connect(self) -> bool:
        """连接系统"""
        raise NotImplementedError
    
    async def disconnect(self):
        """断开连接"""
        self.status = ConnectionStatus.DISCONNECTED
    
    async def collect_metrics(self) -> Optional[SystemMetrics]:
        """收集指标"""
        raise NotImplementedError
    
    def normalize_metrics(self, raw_data: Dict) -> SystemMetrics:
        """标准化指标数据"""
        return SystemMetrics(
            timestamp=time.time(),
            system_name=self.endpoint.name,
            status=raw_data.get("status", "unknown"),
            cpu=raw_data.get("cpu", 0.0),
            memory=raw_data.get("memory", 0.0),
            disk=raw_data.get("disk", 0.0),
            network_in=raw_data.get("network_in", 0.0),
            network_out=raw_data.get("network_out", 0.0),
            custom_metrics=raw_data.get("custom", {})
        )


class OpenClawConnector(BaseConnector):
    """OpenClaw系统连接器"""
    
    def __init__(self, endpoint: SystemEndpoint, config: ConnectorConfig):
        super().__init__(endpoint, config)
        self.endpoint.protocol = "http"
    
    async def connect(self) -> bool:
        """连接OpenClaw Gateway"""
        try:
            self.status = ConnectionStatus.CONNECTING
            # 模拟连接测试
            await asyncio.sleep(0.1)
            self.status = ConnectionStatus.CONNECTED
            return True
        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self.last_error = str(e)
            return False
    
    async def collect_metrics(self) -> Optional[SystemMetrics]:
        """收集OpenClaw指标"""
        if self.status != ConnectionStatus.CONNECTED:
            await self.connect()
        
        try:
            # 模拟从Gateway获取数据
            raw_data = {
                "status": "healthy",
                "cpu": 15.5,
                "memory": 42.3,
                "disk": 38.7,
                "network_in": 1024.5,
                "network_out": 512.3,
                "custom": {
                    "channels": 4,
                    "active_sessions": 2,
                    "cron_jobs": 4
                }
            }
            return self.normalize_metrics(raw_data)
        except Exception as e:
            self.last_error = str(e)
            return None


class ServerConnector(BaseConnector):
    """服务器连接器"""
    
    async def connect(self) -> bool:
        try:
            self.status = ConnectionStatus.CONNECTING
            await asyncio.sleep(0.1)
            self.status = ConnectionStatus.CONNECTED
            return True
        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self.last_error = str(e)
            return False
    
    async def collect_metrics(self) -> Optional[SystemMetrics]:
        """收集服务器指标"""
        if self.status != ConnectionStatus.CONNECTED:
            await self.connect()
        
        try:
            # 模拟服务器指标
            raw_data = {
                "status": "online",
                "cpu": 23.1,
                "memory": 55.8,
                "disk": 45.2,
                "network_in": 2048.0,
                "network_out": 1536.0
            }
            return self.normalize_metrics(raw_data)
        except Exception as e:
            self.last_error = str(e)
            return None


class DockerConnector(BaseConnector):
    """Docker连接器"""
    
    async def connect(self) -> bool:
        try:
            self.status = ConnectionStatus.CONNECTING
            await asyncio.sleep(0.1)
            self.status = ConnectionStatus.CONNECTED
            return True
        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self.last_error = str(e)
            return False
    
    async def collect_metrics(self) -> Optional[SystemMetrics]:
        """收集Docker指标"""
        if self.status != ConnectionStatus.CONNECTED:
            await self.connect()
        
        try:
            raw_data = {
                "status": "running",
                "cpu": 8.5,
                "memory": 28.3,
                "disk": 12.5,
                "network_in": 256.0,
                "network_out": 128.0,
                "custom": {
                    "containers": 5,
                    "images": 12,
                    "volumes": 3
                }
            }
            return self.normalize_metrics(raw_data)
        except Exception as e:
            self.last_error = str(e)
            return None


class ConnectorRegistry:
    """连接器注册中心"""
    
    _connectors: Dict[str, BaseConnector] = {}
    _lock = threading.Lock()
    
    @classmethod
    def register(cls, name: str, connector: BaseConnector):
        """注册连接器"""
        with cls._lock:
            cls._connectors[name] = connector
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseConnector]:
        """获取连接器"""
        return cls._connectors.get(name)
    
    @classmethod
    def unregister(cls, name: str):
        """注销连接器"""
        with cls._lock:
            cls._connectors.pop(name, None)
    
    @classmethod
    def list_connectors(cls) -> List[str]:
        """列出所有连接器"""
        return list(cls._connectors.keys())


class SystemAggregator:
    """系统数据聚合器"""
    
    def __init__(self, config: Optional[ConnectorConfig] = None):
        self.config = config or ConnectorConfig()
        self.connectors: Dict[str, BaseConnector] = {}
        self.aggregated_data: Dict[str, SystemMetrics] = {}
        self.cache: Dict[str, tuple] = {}
        self._running = False
        self._collect_task: Optional[asyncio.Task] = None
    
    def add_connector(self, name: str, connector: BaseConnector):
        """添加连接器"""
        self.connectors[name] = connector
        ConnectorRegistry.register(name, connector)
    
    async def start(self):
        """启动聚合器"""
        self._running = True
        self._collect_task = asyncio.create_task(self._collect_loop())
    
    async def stop(self):
        """停止聚合器"""
        self._running = False
        if self._collect_task:
            self._collect_task.cancel()
            try:
                await self._collect_task
            except asyncio.CancelledError:
                pass
    
    async def _collect_loop(self):
        """收集循环"""
        while self._running:
            try:
                await self.collect_all()
                await asyncio.sleep(self.config.collect_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Collect error: {e}")
                await asyncio.sleep(5)
    
    async def collect_all(self) -> Dict[str, SystemMetrics]:
        """收集所有系统数据"""
        results = {}
        
        for name, connector in self.connectors.items():
            try:
                # 检查缓存
                if self.config.enable_cache:
                    cache_key = f"{name}:metrics"
                    if cache_key in self.cache:
                        cached_time, cached_data = self.cache[cache_key]
                        if time.time() - cached_time < self.config.cache_ttl:
                            results[name] = cached_data
                            continue
                
                metrics = await connector.collect_metrics()
                if metrics:
                    results[name] = metrics
                    self.aggregated_data[name] = metrics
                    
                    # 更新缓存
                    if self.config.enable_cache:
                        self.cache[cache_key] = (time.time(), metrics)
            except Exception as e:
                print(f"Error collecting {name}: {e}")
        
        return results
    
    def get_unified_view(self) -> Dict[str, Any]:
        """获取统一视图"""
        return {
            "timestamp": datetime.now().isoformat(),
            "systems": {
                name: {
                    "status": metrics.status,
                    "cpu": metrics.cpu,
                    "memory": metrics.memory,
                    "disk": metrics.disk,
                    "network": {
                        "in": metrics.network_in,
                        "out": metrics.network_out
                    },
                    "custom": metrics.custom_metrics
                }
                for name, metrics in self.aggregated_data.items()
            },
            "summary": {
                "total_systems": len(self.aggregated_data),
                "healthy_systems": sum(1 for m in self.aggregated_data.values() if m.status == "healthy"),
                "avg_cpu": sum(m.cpu for m in self.aggregated_data.values()) / max(len(self.aggregated_data), 1),
                "avg_memory": sum(m.memory for m in self.aggregated_data.values()) / max(len(self.aggregated_data), 1)
            }
        }


class UnifiedDashboard:
    """统一监控面板"""
    
    def __init__(self, aggregator: SystemAggregator):
        self.aggregator = aggregator
    
    def generate_html(self) -> str:
        """生成HTML面板"""
        view = self.aggregator.get_unified_view()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>奥创统一监控面板</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d4ff; text-align: center; }}
        .summary {{ display: flex; justify-content: center; gap: 30px; margin: 20px 0; }}
        .summary-card {{ background: #16213e; padding: 20px; border-radius: 10px; text-align: center; min-width: 150px; }}
        .summary-card .value {{ font-size: 32px; font-weight: bold; color: #00d4ff; }}
        .summary-card .label {{ color: #888; margin-top: 5px; }}
        .systems {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
        .system-card {{ background: #16213e; padding: 20px; border-radius: 10px; border-left: 4px solid #00d4ff; }}
        .system-card h3 {{ margin: 0 0 15px 0; color: #00d4ff; }}
        .metric {{ display: flex; justify-content: space-between; margin: 10px 0; }}
        .metric-label {{ color: #888; }}
        .metric-value {{ font-weight: bold; }}
        .status-healthy {{ color: #00ff88; }}
        .status-error {{ color: #ff4444; }}
    </style>
</head>
<body>
    <h1>🦞 奥创统一监控面板</h1>
    <div class="summary">
        <div class="summary-card">
            <div class="value">{view['summary']['total_systems']}</div>
            <div class="label">总系统数</div>
        </div>
        <div class="summary-card">
            <div class="value">{view['summary']['healthy_systems']}</div>
            <div class="label">健康系统</div>
        </div>
        <div class="summary-card">
            <div class="value">{view['summary']['avg_cpu']:.1f}%</div>
            <div class="label">平均CPU</div>
        </div>
        <div class="summary-card">
            <div class="value">{view['summary']['avg_memory']:.1f}%</div>
            <div class="label">平均内存</div>
        </div>
    </div>
    <div class="systems">
"""
        
        for name, data in view['systems'].items():
            status_class = "status-healthy" if data['status'] == "healthy" else "status-error"
            html += f"""        <div class="system-card">
            <h3>{name}</h3>
            <div class="metric">
                <span class="metric-label">状态</span>
                <span class="metric-value {status_class}">{data['status']}</span>
            </div>
            <div class="metric">
                <span class="metric-label">CPU</span>
                <span class="metric-value">{data['cpu']:.1f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">内存</span>
                <span class="metric-value">{data['memory']:.1f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">磁盘</span>
                <span class="metric-value">{data['disk']:.1f}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">网络入</span>
                <span class="metric-value">{data['network']['in']:.1f} KB/s</span>
            </div>
            <div class="metric">
                <span class="metric-label">网络出</span>
                <span class="metric-value">{data['network']['out']:.1f} KB/s</span>
            </div>
        </div>
"""
        
        html += """    </div>
</body>
</html>"""
        return html
    
    def generate_json(self) -> str:
        """生成JSON数据"""
        return json.dumps(self.aggregator.get_unified_view(), indent=2, ensure_ascii=False)


async def demo():
    """演示"""
    print("=== 奥创系统连接器框架演示 ===\n")
    
    # 创建配置
    config = ConnectorConfig(
        collect_interval=10,
        enable_cache=True
    )
    
    # 创建聚合器
    aggregator = SystemAggregator(config)
    
    # 添加连接器
    openclaw_ep = SystemEndpoint(
        name="OpenClaw-Gateway",
        system_type=SystemType.OPENCLAW,
        host="localhost",
        port=18789
    )
    aggregator.add_connector("openclaw", OpenClawConnector(openclaw_ep, config))
    
    server_ep = SystemEndpoint(
        name="Main-Server",
        system_type=SystemType.SERVER,
        host="localhost",
        port=22
    )
    aggregator.add_connector("server", ServerConnector(server_ep, config))
    
    docker_ep = SystemEndpoint(
        name="Docker-Host",
        system_type=SystemType.DOCKER,
        host="localhost",
        port=2375
    )
    aggregator.add_connector("docker", DockerConnector(docker_ep, config))
    
    # 收集数据
    await aggregator.collect_all()
    
    # 输出统一视图
    view = aggregator.get_unified_view()
    print(f"统一视图 ({view['timestamp']}):")
    print(f"  总系统数: {view['summary']['total_systems']}")
    print(f"  健康系统: {view['summary']['healthy_systems']}")
    print(f"  平均CPU: {view['summary']['avg_cpu']:.1f}%")
    print(f"  平均内存: {view['summary']['avg_memory']:.1f}%")
    print()
    
    # 生成面板
    dashboard = UnifiedDashboard(aggregator)
    html = dashboard.generate_html()
    
    with open("/root/.openclaw/workspace/ultron/unified-dashboard.html", "w") as f:
        f.write(html)
    
    print(f"统一监控面板已生成: ultron/unified-dashboard.html")
    
    # 关闭
    await aggregator.stop()
    
    return view


if __name__ == "__main__":
    asyncio.run(demo())