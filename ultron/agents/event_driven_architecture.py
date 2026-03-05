#!/usr/bin/env python3
"""
多智能体协作网络 - 事件驱动架构
Event-Driven Architecture for Multi-Agent Collaboration
"""

import time
import uuid
import threading
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Callable, Optional
from enum import Enum
import queue

class EventType(Enum):
    """事件类型"""
    AGENT_REGISTERED = "agent.registered"
    AGENT_UNREGISTERED = "agent.unregistered"
    AGENT_HEARTBEAT = "agent.heartbeat"
    TASK_SUBMITTED = "task.submitted"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_PROGRESS = "task.progress"
    MESSAGE_SENT = "message.sent"
    MESSAGE_RECEIVED = "message.received"
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_STEP = "workflow.step"

class Event:
    """事件"""
    
    def __init__(self, event_type: EventType, source: str, data: dict = None,
                 correlation_id: str = None):
        self.event_id = f"evt-{uuid.uuid4().hex[:12]}"
        self.event_type = event_type
        self.source = source
        self.data = data or {}
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.timestamp = datetime.now()
        self.metadata = {}
    
    def to_dict(self) -> dict:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'source': self.source,
            'data': self.data,
            'correlation_id': self.correlation_id,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }

class EventSubscriber:
    """事件订阅者"""
    
    def __init__(self, name: str, callback: Callable, event_types: List[EventType],
                 filter_func: Callable = None):
        self.name = name
        self.callback = callback
        self.event_types = event_types
        self.filter_func = filter_func
        self.received_count = 0
    
    def handle(self, event: Event) -> bool:
        """处理事件"""
        # 应用过滤器
        if self.filter_func and not self.filter_func(event):
            return False
        
        try:
            self.callback(event)
            self.received_count += 1
            return True
        except Exception as e:
            print(f"❌ Subscriber {self.name} error: {e}")
            return False

class EventBus:
    """事件总线"""
    
    def __init__(self, async_mode: bool = True):
        self.async_mode = async_mode
        self._subscribers: Dict[EventType, List[EventSubscriber]] = defaultdict(list)
        self._event_queue = queue.Queue()
        self._running = False
        self._dispatcher_thread = None
        self._lock = threading.RLock()
        
        # 事件历史
        self._event_history: List[Event] = []
        self._max_history = 1000
        
        # 统计
        self._stats = {
            'total_published': 0,
            'total_delivered': 0,
            'by_type': defaultdict(int)
        }
    
    def subscribe(self, subscriber: EventSubscriber):
        """订阅事件"""
        with self._lock:
            for event_type in subscriber.event_types:
                self._subscribers[event_type].append(subscriber)
            print(f"✅ 订阅者 '{subscriber.name}' 订阅: {[e.value for e in subscriber.event_types]}")
    
    def unsubscribe(self, subscriber_name: str):
        """取消订阅"""
        with self._lock:
            for event_type in self._subscribers:
                self._subscribers[event_type] = [
                    s for s in self._subscribers[event_type] if s.name != subscriber_name
                ]
    
    def publish(self, event: Event):
        """发布事件"""
        with self._lock:
            self._stats['total_published'] += 1
            self._stats['by_type'][event.event_type.value] += 1
            self._event_history.append(event)
            
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]
        
        if self.async_mode:
            self._event_queue.put(event)
        else:
            self._dispatch_event(event)
    
    def _dispatch_event(self, event: Event):
        """分发事件"""
        with self._lock:
            subscribers = list(self._subscribers.get(event.event_type, []))
            # 也发送给通配符订阅者
            subscribers.extend(self._subscribers.get('*', []))
        
        for subscriber in subscribers:
            if subscriber.handle(event):
                with self._lock:
                    self._stats['total_delivered'] += 1
    
    def start(self):
        """启动事件处理"""
        if self._running:
            return
        
        self._running = True
        self._dispatcher_thread = threading.Thread(target=self._dispatch_loop,
                                                   daemon=True)
        self._dispatcher_thread.start()
        print("🚀 事件总线已启动")
    
    def stop(self):
        """停止事件处理"""
        self._running = False
        if self._dispatcher_thread:
            self._dispatcher_thread.join(timeout=5)
        print("🛑 事件总线已停止")
    
    def _dispatch_loop(self):
        """分发循环"""
        while self._running:
            try:
                event = self._event_queue.get(timeout=1)
                self._dispatch_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 事件处理错误: {e}")
    
    def get_history(self, event_type: EventType = None,
                   limit: int = 100) -> List[dict]:
        """获取事件历史"""
        with self._lock:
            if event_type:
                events = [e for e in self._event_history if e.event_type == event_type]
            else:
                events = self._event_history[-limit:]
            return [e.to_dict() for e in reversed(events[-limit:])]
    
    def get_stats(self) -> dict:
        """获取统计"""
        with self._lock:
            stats = self._stats.copy()
            stats['by_type'] = dict(stats['by_type'])
            stats['queue_size'] = self._event_queue.qsize()
            return stats
    
    def clear_history(self):
        """清除历史"""
        with self._lock:
            self._event_history.clear()


class WorkflowEngine:
    """工作流引擎 (基于事件驱动)"""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._workflows: Dict[str, dict] = {}
        self._active_workflows: Dict[str, dict] = {}
        self._lock = threading.RLock()
        
        # 订阅工作流事件
        self._setup_subscriptions()
    
    def _setup_subscriptions(self):
        """设置订阅"""
        self.event_bus.subscribe(EventSubscriber(
            'workflow_engine',
            self._handle_event,
            [EventType.TASK_COMPLETED, EventType.TASK_FAILED]
        ))
    
    def define_workflow(self, workflow_id: str, steps: List[dict]):
        """定义工作流"""
        self._workflows[workflow_id] = {
            'steps': steps,
            'current_step': 0
        }
        print(f"✅ 定义工作流: {workflow_id} ({len(steps)} 步骤)")
    
    def start_workflow(self, workflow_id: str, initial_data: dict) -> str:
        """启动工作流"""
        if workflow_id not in self._workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        instance_id = f"wf-{uuid.uuid4().hex[:8]}"
        
        with self._lock:
            self._active_workflows[instance_id] = {
                'workflow_id': workflow_id,
                'data': initial_data,
                'current_step': 0,
                'status': 'running',
                'started_at': datetime.now()
            }
        
        # 发布工作流开始事件
        self.event_bus.publish(Event(
            EventType.WORKFLOW_STARTED,
            'workflow_engine',
            {'instance_id': instance_id, 'workflow_id': workflow_id}
        ))
        
        # 执行第一步
        self._execute_step(instance_id)
        
        return instance_id
    
    def _execute_step(self, instance_id: str):
        """执行步骤"""
        with self._lock:
            if instance_id not in self._active_workflows:
                return
            
            workflow = self._active_workflows[instance_id]
            workflow_def = self._workflows[workflow['workflow_id']]
            steps = workflow_def['steps']
            current = workflow['current_step']
        
        if current < len(steps):
            step = steps[current]
            self.event_bus.publish(Event(
                EventType.WORKFLOW_STEP,
                'workflow_engine',
                {
                    'instance_id': instance_id,
                    'step': current,
                    'action': step.get('action')
                }
            ))
    
    def _handle_event(self, event: Event):
        """处理事件"""
        if event.event_type == EventType.TASK_COMPLETED:
            # 继续工作流
            pass
    
    def get_status(self, instance_id: str) -> Optional[dict]:
        """获取工作流状态"""
        with self._lock:
            return self._active_workflows.get(instance_id)


# 测试
if __name__ == '__main__':
    print("🔧 事件驱动架构测试")
    print("="*50)
    
    # 创建事件总线
    bus = EventBus(async_mode=True)
    bus.start()
    
    # 创建订阅者
    def task_logger(event: Event):
        print(f"  📝 任务日志: {event.data}")
    
    def alert_handler(event: Event):
        print(f"  ⚠️ 告警: {event.event_type.value} from {event.source}")
    
    bus.subscribe(EventSubscriber('task_logger', task_logger, 
                                  [EventType.TASK_SUBMITTED, EventType.TASK_COMPLETED]))
    bus.subscribe(EventSubscriber('alert_handler', alert_handler,
                                  [EventType.SYSTEM_ERROR, EventType.SYSTEM_WARNING]))
    
    # 发布事件
    print("\n📡 发布事件:")
    bus.publish(Event(EventType.TASK_SUBMITTED, 'test_source', 
                     {'task_id': 'task-001', 'type': 'compute'}))
    bus.publish(Event(EventType.TASK_COMPLETED, 'agent-001',
                     {'task_id': 'task-001', 'result': 'success'}))
    bus.publish(Event(EventType.SYSTEM_WARNING, 'monitor',
                     {'message': 'High memory usage'}))
    
    # 等待异步处理
    time.sleep(0.5)
    
    print("\n📊 统计:")
    stats = bus.get_stats()
    print(json.dumps(stats, indent=2))
    
    # 工作流测试
    print("\n🔄 工作流测试:")
    engine = WorkflowEngine(bus)
    engine.define_workflow('test_wf', [
        {'action': 'init', 'type': 'setup'},
        {'action': 'process', 'type': 'compute'},
        {'action': 'finalize', 'type': 'cleanup'}
    ])
    
    wf_id = engine.start_workflow('test_wf', {'user': 'test'})
    print(f"  启动工作流: {wf_id}")
    
    bus.stop()
    print("\n✅ 事件驱动架构测试完成")