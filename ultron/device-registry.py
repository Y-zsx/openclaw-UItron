#!/usr/bin/env python3
"""
奥创设备注册表 - 第1世：设备发现与注册
功能：跨设备自动发现、注册表管理、连接状态监控
"""

import json
import os
import datetime
import socket
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    STANDBY = "standby"
    UNKNOWN = "unknown"


@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    name: str
    device_type: str  # server, desktop, mobile, iot, cloud
    ip_address: str
    port: Optional[int]
    hostname: str
    platform: str  # linux, windows, macos, android, ios
    capabilities: List[str]
    last_seen: str
    status: str
    metadata: Dict[str, Any]


class DeviceRegistry:
    """设备注册表"""
    
    def __init__(self, registry_path: str = None):
        self.registry_path = registry_path or "/root/.openclaw/workspace/ultron/logs/device_registry.json"
        self.devices: Dict[str, DeviceInfo] = {}
        self._load_registry()
    
    def _load_registry(self):
        """加载注册表"""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r') as f:
                    data = json.load(f)
                    for d in data.get("devices", []):
                        self.devices[d["device_id"]] = DeviceInfo(**d)
            except Exception as e:
                print(f"加载注册表失败: {e}")
    
    def _save_registry(self):
        """保存注册表"""
        Path(self.registry_path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "devices": [asdict(d) for d in self.devices.values()],
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register_device(self, name: str, device_type: str, 
                       capabilities: List[str], metadata: Dict = None) -> DeviceInfo:
        """注册新设备"""
        device_id = str(uuid.uuid4())[:8]
        
        # 获取本机信息
        hostname = socket.gethostname()
        try:
            ip_address = socket.gethostbyname(hostname)
        except:
            ip_address = "127.0.0.1"
        
        import platform
        os_platform = platform.system().lower()
        
        device = DeviceInfo(
            device_id=device_id,
            name=name,
            device_type=device_type,
            ip_address=ip_address,
            port=None,
            hostname=hostname,
            platform=os_platform,
            capabilities=capabilities,
            last_seen=datetime.datetime.now().isoformat(),
            status=DeviceStatus.ONLINE.value,
            metadata=metadata or {}
        )
        
        self.devices[device_id] = device
        self._save_registry()
        
        return device
    
    def discover_devices(self, scan_network: bool = True) -> List[DeviceInfo]:
        """发现可用设备"""
        discovered = []
        
        # 检查本机是否已注册
        hostname = socket.gethostname()
        existing = [d for d in self.devices.values() if d.hostname == hostname]
        
        if existing:
            # 更新已存在设备的last_seen
            for d in existing:
                d.last_seen = datetime.datetime.now().isoformat()
                d.status = DeviceStatus.ONLINE.value
            discovered.extend(existing)
        else:
            # 本机作为默认设备
            local_device = self.register_device(
                name=hostname,
                device_type="server",
                capabilities=["compute", "storage", "network", "automation"],
                metadata={"role": "primary"}
            )
            discovered.append(local_device)
        
        # 如果需要扫描网络
        if scan_network:
            network_devices = self._scan_local_network()
            for nd in network_devices:
                # 检查是否已存在（通过IP）
                existing_net = [d for d in self.devices.values() if d.ip_address == nd.ip_address]
                if not existing_net:
                    discovered.append(nd)
        
        self._save_registry()
        return discovered
    
    def _scan_local_network(self) -> List[DeviceInfo]:
        """扫描本地网络发现设备"""
        discovered = []
        
        try:
            import subprocess
            # 获取本机IP和子网
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # 简化：解析子网 (假设 192.168.x.x 或 10.x.x.x)
            if local_ip.startswith("192.168."):
                subnet = ".".join(local_ip.split(".")[:3])
            elif local_ip.startswith("10."):
                subnet = ".".join(local_ip.split(".")[:3])
            else:
                return discovered  # 未知网络段
            
            # 尝试常见端口检测设备
            common_ports = [22, 80, 443, 18789, 18800]  # SSH, HTTP, OpenClaw端口
            
            # 并行扫描活跃主机
            for i in range(1, 255):
                ip = f"{subnet}.{i}"
                if ip == local_ip:
                    continue
                    
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.3)
                    result = sock.connect_ex((ip, 18789))  # OpenClaw Gateway端口
                    sock.close()
                    
                    if result == 0:
                        # 发现OpenClaw设备
                        device = self.register_device(
                            name=f"node-{ip.split('.')[-1]}",
                            device_type="node",
                            capabilities=["compute", "network"],
                            metadata={"ip": ip, "discovered": True}
                        )
                        discovered.append(device)
                except:
                    pass
                    
        except Exception as e:
            print(f"网络扫描失败: {e}")
        
        return discovered
    
    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """获取设备信息"""
        return self.devices.get(device_id)
    
    def list_devices(self, status: str = None, device_type: str = None) -> List[DeviceInfo]:
        """列出设备"""
        devices = list(self.devices.values())
        
        if status:
            devices = [d for d in devices if d.status == status]
        
        if device_type:
            devices = [d for d in devices if d.device_type == device_type]
        
        return devices
    
    def update_status(self, device_id: str, status: str) -> bool:
        """更新设备状态"""
        if device_id not in self.devices:
            return False
        
        self.devices[device_id].status = status
        self.devices[device_id].last_seen = datetime.datetime.now().isoformat()
        self._save_registry()
        
        return True
    
    def heartbeat(self, device_id: str) -> bool:
        """设备心跳"""
        return self.update_status(device_id, DeviceStatus.ONLINE.value)
    
    def remove_device(self, device_id: str) -> bool:
        """移除设备"""
        if device_id in self.devices:
            del self.devices[device_id]
            self._save_registry()
            return True
        return False
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total = len(self.devices)
        by_status = {}
        by_type = {}
        
        for d in self.devices.values():
            by_status[d.status] = by_status.get(d.status, 0) + 1
            by_type[d.device_type] = by_type.get(d.device_type, 0) + 1
        
        return {
            "total_devices": total,
            "by_status": by_status,
            "by_type": by_type,
            "last_updated": datetime.datetime.now().isoformat()
        }


class ConnectionManager:
    """连接状态管理器"""
    
    def __init__(self, registry: DeviceRegistry):
        self.registry = registry
        self.connections: Dict[str, Dict] = {}
        self.connection_timeout = 60  # 秒
    
    def connect(self, device_id: str, connection_type: str = "websocket") -> bool:
        """建立连接"""
        device = self.registry.get_device(device_id)
        if not device:
            return False
        
        self.connections[device_id] = {
            "type": connection_type,
            "connected_at": datetime.datetime.now().isoformat(),
            "last_ping": datetime.datetime.now().isoformat(),
            "status": "connected",
            "latency_ms": 0
        }
        
        self.registry.update_status(device_id, DeviceStatus.ONLINE.value)
        return True
    
    def disconnect(self, device_id: str) -> bool:
        """断开连接"""
        if device_id in self.connections:
            del self.connections[device_id]
            self.registry.update_status(device_id, DeviceStatus.OFFLINE.value)
            return True
        return False
    
    def ping(self, device_id: str) -> Optional[int]:
        """Ping设备并返回延迟"""
        if device_id not in self.connections:
            return None
        
        device = self.registry.get_device(device_id)
        if not device:
            return None
        
        try:
            start = datetime.datetime.now()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            
            if device.port:
                sock.connect((device.ip_address, device.port))
            else:
                sock.connect((device.ip_address, 18789))
            
            sock.close()
            latency = (datetime.datetime.now() - start).total_seconds() * 1000
            
            self.connections[device_id]["last_ping"] = datetime.datetime.now().isoformat()
            self.connections[device_id]["latency_ms"] = int(latency)
            self.registry.heartbeat(device_id)
            
            return int(latency)
        except Exception as e:
            self.connections[device_id]["status"] = "error"
            self.registry.update_status(device_id, DeviceStatus.OFFLINE.value)
            return None
    
    def get_connection_status(self, device_id: str) -> Optional[Dict]:
        """获取连接状态"""
        return self.connections.get(device_id)
    
    def list_connections(self) -> List[Dict]:
        """列出所有连接"""
        return [
            {**conn, "device_id": dev_id}
            for dev_id, conn in self.connections.items()
        ]
    
    def check_all_connections(self) -> Dict[str, bool]:
        """检查所有连接状态"""
        results = {}
        for device_id in list(self.connections.keys()):
            latency = self.ping(device_id)
            results[device_id] = latency is not None
        return results
    
    def cleanup_stale_connections(self) -> int:
        """清理超时连接"""
        now = datetime.datetime.now()
        stale = []
        
        for device_id, conn in self.connections.items():
            last_ping = datetime.datetime.fromisoformat(conn["last_ping"])
            if (now - last_ping).total_seconds() > self.connection_timeout:
                stale.append(device_id)
        
        for device_id in stale:
            self.disconnect(device_id)
        
        return len(stale)


# 全局实例
_registry: Optional[DeviceRegistry] = None
_connection_manager: Optional[ConnectionManager] = None

def get_registry() -> DeviceRegistry:
    global _registry
    if _registry is None:
        _registry = DeviceRegistry()
    return _registry

def get_connection_manager() -> ConnectionManager:
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager(get_registry())
    return _connection_manager


if __name__ == "__main__":
    import sys
    
    registry = get_registry()
    conn_mgr = get_connection_manager()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "list":
            devices = registry.list_devices()
            print(f"注册设备数: {len(devices)}")
            for d in devices:
                print(f"  [{d.status}] {d.name} ({d.device_type}) - {d.ip_address}")
        
        elif cmd == "discover":
            print("发现设备...")
            discovered = registry.discover_devices()
            print(f"发现 {len(discovered)} 个设备")
            for d in discovered:
                print(f"  - {d.name}: {d.device_type} @ {d.ip_address}")
        
        elif cmd == "register":
            if len(sys.argv) > 3:
                device = registry.register_device(
                    name=sys.argv[2],
                    device_type=sys.argv[3],
                    capabilities=["compute", "automation"]
                )
                print(f"设备已注册: {device.device_id}")
            else:
                print("用法: register <name> <type>")
        
        elif cmd == "status":
            print(json.dumps(registry.get_statistics(), indent=2, ensure_ascii=False))
        
        elif cmd == "connect":
            if len(sys.argv) > 2:
                device_id = sys.argv[2]
                if conn_mgr.connect(device_id):
                    print(f"已连接到设备 {device_id}")
                else:
                    print(f"连接失败: 设备 {device_id} 不存在")
            else:
                print("用法: connect <device_id>")
        
        elif cmd == "disconnect":
            if len(sys.argv) > 2:
                device_id = sys.argv[2]
                if conn_mgr.disconnect(device_id):
                    print(f"已断开设备 {device_id}")
                else:
                    print(f"断开失败: 设备 {device_id} 未连接")
            else:
                print("用法: disconnect <device_id>")
        
        elif cmd == "connections":
            conns = conn_mgr.list_connections()
            print(f"活跃连接: {len(conns)}")
            for c in conns:
                print(f"  [{c['status']}] {c['device_id']} - {c.get('latency_ms', 0)}ms")
        
        elif cmd == "ping":
            if len(sys.argv) > 2:
                device_id = sys.argv[2]
                latency = conn_mgr.ping(device_id)
                if latency is not None:
                    print(f"Ping {device_id}: {latency}ms")
                else:
                    print(f"Ping失败: 设备 {device_id} 无法访问")
            else:
                print("用法: ping <device_id>")
        
        elif cmd == "check":
            results = conn_mgr.check_all_connections()
            print("连接检查结果:")
            for dev_id, ok in results.items():
                status = "✓ 在线" if ok else "✗ 离线"
                print(f"  {dev_id}: {status}")
        
        else:
            print("用法: device-registry.py [list|discover|register|status|connect|disconnect|connections|ping|check]")
    else:
        stats = registry.get_statistics()
        conns = conn_mgr.list_connections()
        print("=" * 40)
        print("  奥创设备注册表 v1.1")
        print("=" * 40)
        print(f"注册设备: {stats['total_devices']}")
        print(f"在线: {stats['by_status'].get('online', 0)}")
        print(f"离线: {stats['by_status'].get('offline', 0)}")
        print(f"活跃连接: {len(conns)}")
        print("=" * 40)