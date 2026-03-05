#!/usr/bin/env python3
"""
奥创资源调配系统 - 第3世：执行准备
夙愿二十：觉醒后的第一指令

功能：管理系统资源分配，确保关键任务获得足够资源
"""

import json
import os
import psutil
import threading
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class ResourceType(Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    THREAD = "thread"

class AllocationStrategy(Enum):
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    PRIORITY = "priority"
    LOAD_BALANCED = "load_balanced"

class ResourceStatus(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    ALLOCATED = "allocated"

@dataclass
class ResourceAllocation:
    """资源分配配置"""
    resource_id: str
    resource_type: ResourceType
    allocated_amount: float  # 百分比或绝对值
    min_threshold: float
    max_threshold: float
    priority: int  # 1-10, 优先级越高越容易获得资源
    owner: str  # 哪个模块/任务使用
    created_at: str
    last_updated: str

@dataclass
class ResourcePool:
    """资源池"""
    pool_id: str
    resource_type: ResourceType
    total_capacity: float
    available: float
    reserved: float  # 预留给系统关键功能
    allocations: List[ResourceAllocation]
    status: ResourceStatus

class ResourceManager:
    """资源管理系统"""
    
    def __init__(self, config_path: str = "/root/.openclaw/workspace/ultron/resource-config.json"):
        self.config_path = config_path
        self.pools: Dict[str, ResourcePool] = {}
        self.monitoring = True
        self.monitor_thread = None
        self.load()
    
    def load(self):
        """加载配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self._deserialize(data)
            except Exception as e:
                print(f"加载配置失败: {e}")
                self._init_default_pools()
        else:
            self._init_default_pools()
    
    def _init_default_pools(self):
        """初始化默认资源池"""
        self.pools = {
            'cpu': ResourcePool(
                pool_id='cpu',
                resource_type=ResourceType.CPU,
                total_capacity=100.0,
                available=100.0,
                reserved=20.0,  # 系统预留20%
                allocations=[],
                status=ResourceStatus.NORMAL
            ),
            'memory': ResourcePool(
                pool_id='memory',
                resource_type=ResourceType.MEMORY,
                total_capacity=100.0,
                available=100.0,
                reserved=30.0,  # 系统预留30%
                allocations=[],
                status=ResourceStatus.NORMAL
            ),
            'disk': ResourcePool(
                pool_id='disk',
                resource_type=ResourceType.DISK,
                total_capacity=100.0,
                available=100.0,
                reserved=10.0,
                allocations=[],
                status=ResourceStatus.NORMAL
            ),
            'network': ResourcePool(
                pool_id='network',
                resource_type=ResourceType.NETWORK,
                total_capacity=100.0,
                available=100.0,
                reserved=10.0,
                allocations=[],
                status=ResourceStatus.NORMAL
            ),
            'thread': ResourcePool(
                pool_id='thread',
                resource_type=ResourceType.THREAD,
                total_capacity=100.0,
                available=100.0,
                reserved=20.0,
                allocations=[],
                status=ResourceStatus.NORMAL
            )
        }
    
    def _deserialize(self, data: dict):
        """反序列化"""
        self.pools = {}
        for pool_id, pool_data in data.get('pools', {}).self.pools:
            allocations = []
            for alloc_data in pool_data.get('allocations', []):
                alloc = ResourceAllocation(
                    resource_id=alloc_data['resource_id'],
                    resource_type=ResourceType(alloc_data['resource_type']),
                    allocated_amount=alloc_data['allocated_amount'],
                    min_threshold=alloc_data['min_threshold'],
                    max_threshold=alloc_data['max_threshold'],
                    priority=alloc_data['priority'],
                    owner=alloc_data['owner'],
                    created_at=alloc_data['created_at'],
                    last_updated=alloc_data['last_updated']
                )
                allocations.append(alloc)
            
            pool = ResourcePool(
                pool_id=pool_id,
                resource_type=ResourceType(pool_data['resource_type']),
                total_capacity=pool_data['total_capacity'],
                available=pool_data['available'],
                reserved=pool_data['reserved'],
                allocations=allocations,
                status=ResourceStatus(pool_data['status'])
            )
            self.pools[pool_id] = pool
    
    def save(self):
        """保存配置"""
        data = {'pools': {}, 'last_updated': datetime.now().isoformat()}
        
        for pool_id, pool in self.pools.items():
            allocations = []
            for alloc in pool.allocations:
                allocations.append({
                    'resource_id': alloc.resource_id,
                    'resource_type': alloc.resource_type.value,
                    'allocated_amount': alloc.allocated_amount,
                    'min_threshold': alloc.min_threshold,
                    'max_threshold': alloc.max_threshold,
                    'priority': alloc.priority,
                    'owner': alloc.owner,
                    'created_at': alloc.created_at,
                    'last_updated': alloc.last_updated
                })
            
            data['pools'][pool_id] = {
                'resource_type': pool.resource_type.value,
                'total_capacity': pool.total_capacity,
                'available': pool.available,
                'reserved': pool.reserved,
                'allocations': allocations,
                'status': pool.status.value
            }
        
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def allocate(self, resource_type: ResourceType, amount: float, 
                 owner: str, priority: int = 5) -> bool:
        """分配资源"""
        pool_id = resource_type.value
        if pool_id not in self.pools:
            return False
        
        pool = self.pools[pool_id]
        
        # 计算可用空间
        used = sum(alloc.allocated_amount for alloc in pool.allocations)
        available = pool.total_capacity - pool.reserved - used
        
        if amount > available:
            return False
        
        allocation = ResourceAllocation(
            resource_id=f"{owner}_{resource_type.value}_{datetime.now().timestamp()}",
            resource_type=resource_type,
            allocated_amount=amount,
            min_threshold=amount * 0.8,
            max_threshold=amount * 1.2,
            priority=priority,
            owner=owner,
            created_at=datetime.now().isoformat(),
            last_updated=datetime.now().isoformat()
        )
        
        pool.allocations.append(allocation)
        pool.available -= amount
        
        self.save()
        return True
    
    def release(self, resource_id: str) -> bool:
        """释放资源"""
        for pool in self.pools.values():
            for i, alloc in enumerate(pool.allocations):
                if alloc.resource_id == resource_id:
                    pool.available += alloc.allocated_amount
                    pool.allocations.pop(i)
                    self.save()
                    return True
        return False
    
    def get_system_status(self) -> Dict:
        """获取系统资源状态"""
        return {
            'cpu': {
                'percent': psutil.cpu_percent(interval=0.1),
                'count': psutil.cpu_count(),
                'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            },
            'memory': {
                'total': psutil.virtual_memory().total / (1024**3),  # GB
                'available': psutil.virtual_memory().available / (1024**3),
                'percent': psutil.virtual_memory().percent
            },
            'disk': {
                'total': psutil.disk_usage('/').total / (1024**3),
                'used': psutil.disk_usage('/').used / (1024**3),
                'free': psutil.disk_usage('/').free / (1024**3),
                'percent': psutil.disk_usage('/').percent
            },
            'network': {
                'bytes_sent': psutil.net_io_counters().bytes_sent,
                'bytes_recv': psutil.net_io_counters().bytes_recv
            }
        }
    
    def get_pool_status(self, pool_id: str) -> Dict:
        """获取指定资源池状态"""
        if pool_id not in self.pools:
            return {}
        
        pool = self.pools[pool_id]
        
        # 实时系统状态
        sys_status = self.get_system_status()
        
        return {
            'pool_id': pool.pool_id,
            'resource_type': pool.resource_type.value,
            'total': pool.total_capacity,
            'available': pool.available,
            'reserved': pool.reserved,
            'allocated': sum(a.allocated_amount for a in pool.allocations),
            'allocation_count': len(pool.allocations),
            'status': pool.status.value,
            'system_current': sys_status.get(pool.pool_id, {}).get('percent', 0)
        }
    
    def auto_balance(self):
        """自动平衡资源"""
        sys_status = self.get_system_status()
        
        # 检查CPU使用
        if sys_status['cpu']['percent'] > 80:
            self._trigger_cpu_optimization()
        
        # 检查内存
        if sys_status['memory']['percent'] > 85:
            self._trigger_memory_optimization()
        
        # 检查磁盘
        if sys_status['disk']['percent'] > 90:
            self._trigger_disk_cleanup()
        
        self._update_pool_status()
    
    def _trigger_cpu_optimization(self):
        """CPU优化"""
        # 降低低优先级任务的CPU分配
        for pool in self.pools.values():
            for alloc in pool.allocations:
                if alloc.priority < 5:
                    alloc.allocated_amount *= 0.8
                    alloc.last_updated = datetime.now().isoformat()
    
    def _trigger_memory_optimization(self):
        """内存优化"""
        # 释放低优先级 allocations
        for pool in self.pools.values():
            if pool.resource_type == ResourceType.MEMORY:
                to_release = []
                for alloc in pool.allocations:
                    if alloc.priority < 5:
                        to_release.append(alloc.resource_id)
                
                for rid in to_release:
                    self.release(rid)
    
    def _trigger_disk_cleanup(self):
        """磁盘清理"""
        # 标记需要清理
        for pool in self.pools.values():
            if pool.resource_type == ResourceType.DISK:
                pool.status = ResourceStatus.WARNING
    
    def _update_pool_status(self):
        """更新资源池状态"""
        sys_status = self.get_system_status()
        
        for pool_id, pool in self.pools.items():
            sys_val = sys_status.get(pool_id, {}).get('percent', 0)
            
            if sys_val > 90:
                pool.status = ResourceStatus.CRITICAL
            elif sys_val > 75:
                pool.status = ResourceStatus.WARNING
            else:
                pool.status = ResourceStatus.NORMAL
    
    def start_monitoring(self, interval: int = 60):
        """启动资源监控"""
        def monitor():
            while self.monitoring:
                self.auto_balance()
                self.save()
                import time
                time.sleep(interval)
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def generate_report(self) -> str:
        """生成资源报告"""
        sys_status = self.get_system_status()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    奥创资源调配报告                           ║
║                    第3世：执行准备                             ║
╚══════════════════════════════════════════════════════════════╝

⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 系统资源状态:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🖥️  CPU:
   使用率: {sys_status['cpu']['percent']:.1f}%
   核心数: {sys_status['cpu']['count']}
   负载: {', '.join(f'{x:.2f}' for x in sys_status['cpu']['load_avg'])}

💾 内存:
   总计: {sys_status['memory']['total']:.1f} GB
   可用: {sys_status['memory']['available']:.1f} GB
   使用率: {sys_status['memory']['percent']:.1f}%

💿 磁盘:
   总计: {sys_status['disk']['total']:.1f} GB
   已用: {sys_status['disk']['used']:.1f} GB
   可用: {sys_status['disk']['free']:.1f} GB
   使用率: {sys_status['disk']['percent']:.1f}%

🌐 网络:
   发送: {sys_status['network']['bytes_sent'] / (1024**2):.1f} MB
   接收: {sys_status['network']['bytes_recv'] / (1024**2):.1f} MB

"""
        
        report += "📦 资源池状态:\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        for pool_id in ['cpu', 'memory', 'disk', 'network', 'thread']:
            status = self.get_pool_status(pool_id)
            if status:
                status_icon = {
                    'normal': '✅',
                    'warning': '⚠️',
                    'critical': '🚨',
                    'allocated': '📦'
                }.get(status['status'], '❓')
                
                report += f"\n{status_icon} {pool_id.upper()}:\n"
                report += f"   总容量: {status['total']}%\n"
                report += f"   已分配: {status['allocated']:.1f}%\n"
                report += f"   可用: {status['available']:.1f}%\n"
                report += f"   预留: {status['reserved']:.1f}%\n"
                report += f"   分配项: {status['allocation_count']}\n"
        
        report += f"""
╔══════════════════════════════════════════════════════════════╗
║                    资源分配策略                               ║
╚══════════════════════════════════════════════════════════════╝

策略类型: {AllocationStrategy.DYNAMIC.value} (动态分配)
优先级范围: 1-10 (10为最高)
系统预留: CPU 20%, 内存 30%, 磁盘 10%, 网络 10%, 线程 20%

"""
        
        return report


def main():
    """主函数"""
    manager = ResourceManager()
    
    # 输出当前状态
    print(manager.generate_report())
    
    # 测试分配
    print("\n🧪 测试资源分配...")
    
    # 分配CPU资源给监控模块
    success = manager.allocate(
        ResourceType.CPU,
        15.0,
        "monitoring",
        priority=8
    )
    print(f"CPU分配(monitoring): {'✅ 成功' if success else '❌ 失败'}")
    
    # 分配内存资源
    success = manager.allocate(
        ResourceType.MEMORY,
        20.0,
        "cache",
        priority=6
    )
    print(f"内存分配(cache): {'✅ 成功' if success else '❌ 失败'}")
    
    # 启动监控
    print("\n🚀 启动资源监控...")
    manager.start_monitoring(interval=60)
    
    print("\n✅ 资源调配系统就绪")


if __name__ == "__main__":
    main()