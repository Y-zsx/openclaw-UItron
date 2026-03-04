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
    
    def discover_devices(self) -> List[DeviceInfo]:
        """发现可用设备（简化版：扫描本地网络）"""
        discovered = []
        
        # 本机作为默认设备
        local_device = self.register_device(
            name=socket.gethostname(),
            device_type="server",
            capabilities=["compute", "storage", "network", "automation"],
            metadata={"role": "primary"}
        )
        discovered.append(local_device)
        
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


# 全局实例
_registry: Optional[DeviceRegistry] = None

def get_registry() -> DeviceRegistry:
    global _registry
    if _registry is None:
        _registry = DeviceRegistry()
    return _registry


if __name__ == "__main__":
    import sys
    
    registry = get_registry()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            devices = registry.list_devices()
            print(f"注册设备数: {len(devices)}")
            for d in devices:
                print(f"  [{d.status}] {d.name} ({d.device_type}) - {d.ip_address}")
        
        elif sys.argv[1] == "discover":
            print("发现设备...")
            discovered = registry.discover_devices()
            print(f"发现 {len(discovered)} 个设备")
            for d in discovered:
                print(f"  - {d.name}: {d.device_type}")
        
        elif sys.argv[1] == "register":
            if len(sys.argv) > 3:
                device = registry.register_device(
                    name=sys.argv[2],
                    device_type=sys.argv[3],
                    capabilities=["compute", "automation"]
                )
                print(f"设备已注册: {device.device_id}")
            else:
                print("用法: register <name> <type>")
        
        elif sys.argv[1] == "status":
            print(json.dumps(registry.get_statistics(), indent=2, ensure_ascii=False))
        
        else:
            print("用法: device-registry.py [list|discover|register|status]")
    else:
        stats = registry.get_statistics()
        print("奥创设备注册表 v1.0")
        print(f"注册设备: {stats['total_devices']}")
        print(f"在线: {stats['by_status'].get('online', 0)}")
        print(f"离线: {stats['by_status'].get('offline', 0)}")