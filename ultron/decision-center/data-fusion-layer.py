#!/usr/bin/env python3
"""
多源数据融合系统 - 智能决策中枢核心
Multi-Source Data Fusion Layer

功能：
1. 多源数据接入（API/DB/File/Stream）
2. 数据标准化与转换
3. 统一数据访问接口
4. 实时数据同步
"""

import json
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class DataSourceType(Enum):
    API = "api"
    DATABASE = "database"
    FILE = "file"
    STREAM = "stream"
    MEMORY = "memory"


class DataFormat(Enum):
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    BINARY = "binary"
    TEXT = "text"


@dataclass
class DataSource:
    """数据源配置"""
    name: str
    source_type: DataSourceType
    connection: Dict[str, Any]
    format: DataFormat = DataFormat.JSON
    refresh_interval: int = 60  # 秒
    enabled: bool = True
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataRecord:
    """数据记录"""
    source: str
    timestamp: float
    data: Any
    format: DataFormat
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()
    
    def _compute_checksum(self) -> str:
        content = f"{self.source}:{self.timestamp}:{json.dumps(self.data, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()


class DataTransformer:
    """数据转换器"""
    
    @staticmethod
    def normalize(data: Any, schema: Optional[Dict] = None) -> Dict:
        """数据标准化"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # 键名标准化：转小写，去下划线
                normalized_key = key.lower().replace('_', '')
                result[normalized_key] = DataTransformer.normalize(value, schema)
            return result
        elif isinstance(data, list):
            return [DataTransformer.normalize(item, schema) for item in data]
        elif isinstance(data, str):
            # 尝试解析JSON
            try:
                return json.loads(data)
            except:
                return data
        return data
    
    @staticmethod
    def filter_fields(data: Dict, fields: List[str]) -> Dict:
        """字段过滤"""
        if not fields:
            return data
        return {k: v for k, v in data.items() if k in fields}
    
    @staticmethod
    def enrich(data: Dict, enrichments: Dict[str, Any]) -> Dict:
        """数据富化"""
        result = data.copy()
        result['_enriched'] = True
        result['_enrichments'] = list(enrichments.keys())
        for key, value in enrichments.items():
            result[f'enriched_{key}'] = value
        return result


class DataSourceConnector:
    """数据源连接器基类"""
    
    def __init__(self, config: DataSource):
        self.config = config
        self.connected = False
        self.last_data: Optional[DataRecord] = None
        
    async def connect(self) -> bool:
        raise NotImplementedError
    
    async def disconnect(self):
        self.connected = False
        
    async def fetch(self) -> Optional[DataRecord]:
        raise NotImplementedError
    
    async def subscribe(self, callback):
        """订阅数据更新"""
        raise NotImplementedError


class APIConnector(DataSourceConnector):
    """API数据源连接器"""
    
    def __init__(self, config: DataSource):
        super().__init__(config)
        self.client = None
        
    async def connect(self) -> bool:
        import aiohttp
        try:
            # 简化的连接测试
            self.client = aiohttp.ClientSession()
            self.connected = True
            return True
        except Exception as e:
            print(f"API连接失败: {e}")
            return False
    
    async def fetch(self) -> Optional[DataRecord]:
        if not self.connected:
            await self.connect()
            
        try:
            url = self.config.connection.get('url', '')
            method = self.config.connection.get('method', 'GET')
            headers = self.config.connection.get('headers', {})
            
            async with self.client.request(method, url, headers=headers) as resp:
                data = await resp.json() if resp.status == 200 else None
                
            if data:
                record = DataRecord(
                    source=self.config.name,
                    timestamp=time.time(),
                    data=data,
                    format=self.config.format,
                    metadata={'url': url, 'status': resp.status}
                )
                self.last_data = record
                return record
        except Exception as e:
            print(f"API获取失败: {e}")
        return None
    
    async def subscribe(self, callback):
        """定时拉取"""
        while True:
            data = await self.fetch()
            if data:
                await callback(data)
            await asyncio.sleep(self.config.refresh_interval)


class DatabaseConnector(DataSourceConnector):
    """数据库连接器"""
    
    def __init__(self, config: DataSource):
        super().__init__(config)
        self.pool = None
        
    async def connect(self) -> bool:
        # 简化实现
        self.connected = True
        return True
    
    async def fetch(self) -> Optional[DataRecord]:
        try:
            # 模拟数据库查询
            query = self.config.connection.get('query', 'SELECT * FROM data LIMIT 10')
            data = {'query': query, 'result': [], 'count': 0}
            
            return DataRecord(
                source=self.config.name,
                timestamp=time.time(),
                data=data,
                format=DataFormat.JSON,
                metadata={'query': query}
            )
        except Exception as e:
            print(f"数据库查询失败: {e}")
        return None


class FileConnector(DataSourceConnector):
    """文件数据源连接器"""
    
    def __init__(self, config: DataSource):
        super().__init__(config)
        self.file_watcher = None
        
    async def connect(self) -> bool:
        import os
        path = self.config.connection.get('path', '')
        self.connected = os.path.exists(path)
        return self.connected
    
    async def fetch(self) -> Optional[DataRecord]:
        try:
            path = self.config.connection.get('path', '')
            with open(path, 'r') as f:
                content = f.read()
                
            # 根据格式解析
            if self.config.format == DataFormat.JSON:
                data = json.loads(content)
            elif self.config.format == DataFormat.CSV:
                data = {'csv_content': content.split('\n')[:10]}
            else:
                data = {'content': content[:1000]}
                
            return DataRecord(
                source=self.config.name,
                timestamp=time.time(),
                data=data,
                format=self.config.format,
                metadata={'path': path}
            )
        except Exception as e:
            print(f"文件读取失败: {e}")
        return None
    
    async def subscribe(self, callback):
        """文件监控"""
        import os
        path = self.config.connection.get('path', '')
        last_mtime = 0
        
        while True:
            try:
                if os.path.exists(path):
                    mtime = os.path.getmtime(path)
                    if mtime > last_mtime:
                        last_mtime = mtime
                        data = await self.fetch()
                        if data:
                            await callback(data)
            except:
                pass
            await asyncio.sleep(self.config.refresh_interval)


class StreamConnector(DataSourceConnector):
    """流数据连接器"""
    
    def __init__(self, config: DataSource):
        super().__init__(config)
        self.subscribers: List = []
        
    async def connect(self) -> bool:
        self.connected = True
        return True
    
    async def fetch(self) -> Optional[DataRecord]:
        # 模拟流数据
        data = {
            'stream': self.config.name,
            'event': 'tick',
            'value': time.time(),
            'sequence': int(time.time() * 1000) % 10000
        }
        return DataRecord(
            source=self.config.name,
            timestamp=time.time(),
            data=data,
            format=DataFormat.JSON
        )
    
    async def subscribe(self, callback):
        while True:
            data = await self.fetch()
            if data:
                await callback(data)
            await asyncio.sleep(1)  # 1秒间隔


class DataFusionLayer:
    """数据融合层主类"""
    
    def __init__(self):
        self.sources: Dict[str, DataSource] = {}
        self.connectors: Dict[str, DataSourceConnector] = {}
        self.data_cache: Dict[str, DataRecord] = {}
        self.transformer = DataTransformer()
        self.subscriptions: Dict[str, List[asyncio.Queue]] = {}
        self._running = False
        
    def add_source(self, source: DataSource) -> bool:
        """添加数据源"""
        try:
            self.sources[source.name] = source
            
            # 创建对应连接器
            if source.source_type == DataSourceType.API:
                self.connectors[source.name] = APIConnector(source)
            elif source.source_type == DataSourceType.DATABASE:
                self.connectors[source.name] = DatabaseConnector(source)
            elif source.source_type == DataSourceType.FILE:
                self.connectors[source.name] = FileConnector(source)
            elif source.source_type == DataSourceType.STREAM:
                self.connectors[source.name] = StreamConnector(source)
            else:
                self.connectors[source.name] = DataSourceConnector(source)
                
            return True
        except Exception as e:
            print(f"添加数据源失败: {e}")
            return False
    
    async def connect_source(self, name: str) -> bool:
        """连接数据源"""
        if name not in self.connectors:
            return False
        return await self.connectors[name].connect()
    
    async def connect_all(self) -> Dict[str, bool]:
        """连接所有数据源"""
        results = {}
        for name in self.sources:
            if self.sources[name].enabled:
                results[name] = await self.connect_source(name)
        return results
    
    async def fetch(self, source_name: str, transform: bool = True) -> Optional[DataRecord]:
        """获取单个数据源数据"""
        if source_name not in self.connectors:
            return None
            
        record = await self.connectors[source_name].fetch()
        if record and transform:
            # 数据标准化
            record.data = self.transformer.normalize(record.data)
            
        if record:
            self.data_cache[source_name] = record
            
        return record
    
    async def fetch_all(self, transform: bool = True) -> Dict[str, DataRecord]:
        """获取所有数据源数据"""
        results = {}
        for name in self.sources:
            if self.sources[name].enabled:
                record = await self.fetch(name, transform)
                if record:
                    results[name] = record
        return results
    
    async def query(self, query: Dict) -> List[DataRecord]:
        """查询数据"""
        results = []
        source_filter = query.get('sources', list(self.sources.keys()))
        fields = query.get('fields', [])
        
        for name in source_filter:
            if name in self.data_cache:
                record = self.data_cache[name]
                if fields:
                    record.data = self.transformer.filter_fields(record.data, fields)
                results.append(record)
                
        return results
    
    def subscribe(self, source_name: str) -> asyncio.Queue:
        """订阅数据源更新"""
        if source_name not in self.subscriptions:
            self.subscriptions[source_name] = []
            
        queue = asyncio.Queue()
        self.subscriptions[source_name].append(queue)
        return queue
    
    async def start_monitoring(self):
        """启动监控"""
        self._running = True
        tasks = []
        
        for name, source in self.sources.items():
            if source.enabled and source.source_type in [DataSourceType.STREAM, DataSourceType.API]:
                connector = self.connectors[name]
                queue = self.subscribe(name)
                
                async def callback_wrapper(data, q=queue):
                    await q.put(data)
                    
                task = asyncio.create_task(connector.subscribe(callback_wrapper))
                tasks.append(task)
                
        return tasks
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'total_sources': len(self.sources),
            'enabled_sources': sum(1 for s in self.sources.values() if s.enabled),
            'connected': sum(1 for c in self.connectors.values() if c.connected),
            'cached_sources': len(self.data_cache),
            'running': self._running
        }
    
    def get_data_summary(self) -> Dict:
        """获取数据摘要"""
        summary = {}
        for name, record in self.data_cache.items():
            summary[name] = {
                'timestamp': datetime.fromtimestamp(record.timestamp).isoformat(),
                'format': record.format.value,
                'data_type': type(record.data).__name__,
                'checksum': record.checksum[:8]
            }
        return summary


# 预定义数据源模板
DEFAULT_SOURCES = {
    'system_stats': DataSource(
        name='system_stats',
        source_type=DataSourceType.API,
        connection={'url': 'http://localhost:18789/api/status', 'method': 'GET'},
        format=DataFormat.JSON,
        refresh_interval=30,
        priority=1
    ),
    'gateway_status': DataSource(
        name='gateway_status',
        source_type=DataSourceType.STREAM,
        connection={'type': 'websocket', 'endpoint': 'ws://localhost:18789'},
        format=DataFormat.JSON,
        refresh_interval=5,
        priority=1
    ),
    'config_file': DataSource(
        name='config_file',
        source_type=DataSourceType.FILE,
        connection={'path': '/root/.openclaw/workspace/ultron-workflow/state.json'},
        format=DataFormat.JSON,
        refresh_interval=60,
        priority=2
    )
}


# 演示
if __name__ == '__main__':
    async def demo():
        fusion = DataFusionLayer()
        
        # 添加预定义数据源
        for name, source in DEFAULT_SOURCES.items():
            fusion.add_source(source)
        
        # 连接所有
        print("🔌 连接数据源...")
        results = await fusion.connect_all()
        print(f"连接结果: {results}")
        
        # 获取数据
        print("\n📊 获取所有数据源...")
        all_data = await fusion.fetch_all()
        for name, record in all_data.items():
            print(f"  {name}: {len(str(record.data))} bytes")
        
        # 状态
        print(f"\n📈 状态: {fusion.get_status()}")
        print(f"📋 摘要: {fusion.get_data_summary()}")
        
    asyncio.run(demo())