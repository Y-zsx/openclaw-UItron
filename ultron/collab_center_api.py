#!/usr/bin/env python3
"""
协作中心API服务 - Collaboration Center API Service
提供跨服务协作、状态共享、任务协调功能
端口: 18201
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

DB_PATH = "/root/.openclaw/workspace/ultron/data/collab_center.db"

# 初始化数据库
def init_db():
    import os
    os.makedirs("/root/.openclaw/workspace/ultron/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 服务注册表
    c.execute('''CREATE TABLE IF NOT EXISTS services (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT,
        endpoint TEXT,
        port INTEGER,
        status TEXT DEFAULT 'active',
        capabilities TEXT,
        metadata TEXT,
        registered_at TEXT,
        last_heartbeat TEXT
    )''')
    
    # 共享状态
    c.execute('''CREATE TABLE IF NOT EXISTS shared_state (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_by TEXT,
        updated_at TEXT,
        ttl INTEGER
    )''')
    
    # 协作任务
    c.execute('''CREATE TABLE IF NOT EXISTS collab_tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        creator TEXT,
        assignee TEXT,
        status TEXT DEFAULT 'pending',
        priority TEXT DEFAULT 'normal',
        created_at TEXT,
        updated_at TEXT,
        completed_at TEXT,
        result TEXT
    )''')
    
    # 事件订阅
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        subscriber TEXT NOT NULL,
        callback_url TEXT,
        created_at TEXT
    )''')
    
    # 事件日志
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        source TEXT,
        data TEXT,
        created_at TEXT
    )''')
    
    conn.commit()
    conn.close()

init_db()

class CollabCenterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[CollabCenter] {format % args}")
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def get_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length > 0:
            return json.loads(self.rfile.read(length).decode())
        return {}
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 健康检查
        if path == '/health':
            self.send_json({"status": "ok", "service": "collab-center", "port": 18201})
            conn.close()
            return
        
        # 服务列表
        if path == '/services':
            c.execute("SELECT id, name, type, endpoint, port, status, capabilities, last_heartbeat FROM services WHERE status='active'")
            services = []
            for row in c.fetchall():
                services.append({
                    "id": row[0], "name": row[1], "type": row[2], 
                    "endpoint": row[3], "port": row[4], "status": row[5],
                    "capabilities": json.loads(row[6]) if row[6] else [],
                    "last_heartbeat": row[7]
                })
            self.send_json({"services": services, "count": len(services)})
            conn.close()
            return
        
        # 共享状态
        if path == '/state':
            c.execute("SELECT key, value, updated_by, updated_at FROM shared_state WHERE ttl IS NULL OR updated_at > datetime('now', '-' || ttl || ' seconds')")
            state = {}
            for row in c.fetchall():
                try:
                    state[row[0]] = json.loads(row[1])
                except:
                    state[row[0]] = row[1]
            self.send_json({"state": state})
            conn.close()
            return
        
        # 协作任务列表
        if path == '/tasks':
            status_filter = params.get('status', [None])[0]
            if status_filter:
                c.execute("SELECT id, title, description, creator, assignee, status, priority, created_at, updated_at FROM collab_tasks WHERE status=?", (status_filter,))
            else:
                c.execute("SELECT id, title, description, creator, assignee, status, priority, created_at, updated_at FROM collab_tasks")
            tasks = []
            for row in c.fetchall():
                tasks.append({
                    "id": row[0], "title": row[1], "description": row[2],
                    "creator": row[3], "assignee": row[4], "status": row[5],
                    "priority": row[6], "created_at": row[7], "updated_at": row[8]
                })
            self.send_json({"tasks": tasks, "count": len(tasks)})
            conn.close()
            return
        
        # 事件列表
        if path == '/events':
            event_type = params.get('type', [None])[0]
            limit = int(params.get('limit', ['50'])[0])
            if event_type:
                c.execute("SELECT id, event_type, source, data, created_at FROM events WHERE event_type=? ORDER BY created_at DESC LIMIT ?", (event_type, limit))
            else:
                c.execute("SELECT id, event_type, source, data, created_at FROM events ORDER BY created_at DESC LIMIT ?", (limit,))
            events = []
            for row in c.fetchall():
                events.append({
                    "id": row[0], "type": row[1], "source": row[2],
                    "data": json.loads(row[3]) if row[3] else {}, "created_at": row[4]
                })
            self.send_json({"events": events, "count": len(events)})
            conn.close()
            return
        
        # 统计
        if path == '/stats':
            c.execute("SELECT COUNT(*) FROM services WHERE status='active'")
            active_services = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM collab_tasks WHERE status='pending'")
            pending_tasks = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM collab_tasks WHERE status='completed'")
            completed_tasks = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM events WHERE created_at > datetime('now', '-1 hour')")
            recent_events = c.fetchone()[0]
            
            self.send_json({
                "active_services": active_services,
                "pending_tasks": pending_tasks,
                "completed_tasks": completed_tasks,
                "events_last_hour": recent_events
            })
            conn.close()
            return
        
        # 服务详情
        if path.startswith('/services/'):
            service_id = path.split('/')[-1]
            c.execute("SELECT id, name, type, endpoint, port, status, capabilities, metadata, registered_at, last_heartbeat FROM services WHERE id=?", (service_id,))
            row = c.fetchone()
            if row:
                self.send_json({
                    "id": row[0], "name": row[1], "type": row[2],
                    "endpoint": row[3], "port": row[4], "status": row[5],
                    "capabilities": json.loads(row[6]) if row[6] else {},
                    "metadata": json.loads(row[7]) if row[7] else {},
                    "registered_at": row[8], "last_heartbeat": row[9]
                })
            else:
                self.send_json({"error": "Service not found"}, 404)
            conn.close()
            return
        
        # 任务详情
        if path.startswith('/tasks/'):
            task_id = path.split('/')[-1]
            c.execute("SELECT id, title, description, creator, assignee, status, priority, created_at, updated_at, completed_at, result FROM collab_tasks WHERE id=?", (task_id,))
            row = c.fetchone()
            if row:
                self.send_json({
                    "id": row[0], "title": row[1], "description": row[2],
                    "creator": row[3], "assignee": row[4], "status": row[5],
                    "priority": row[6], "created_at": row[7], "updated_at": row[8],
                    "completed_at": row[9], "result": json.loads(row[10]) if row[10] else None
                })
            else:
                self.send_json({"error": "Task not found"}, 404)
            conn.close()
            return
        
        self.send_json({"error": "Not found"}, 404)
        conn.close()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self.get_body()
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        # 服务注册
        if path == '/services':
            service_id = body.get('id') or str(uuid.uuid4())
            c.execute("INSERT OR REPLACE INTO services (id, name, type, endpoint, port, status, capabilities, metadata, registered_at, last_heartbeat) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (service_id, body.get('name'), body.get('type'), body.get('endpoint'), 
                 body.get('port'), 'active', json.dumps(body.get('capabilities', [])),
                 json.dumps(body.get('metadata', {})), now, now))
            conn.commit()
            self.send_json({"id": service_id, "status": "registered"})
            conn.close()
            return
        
        # 心跳
        if path == '/services/heartbeat':
            service_id = body.get('service_id')
            c.execute("UPDATE services SET last_heartbeat=? WHERE id=?", (now, service_id))
            conn.commit()
            self.send_json({"status": "heartbeat_ok"})
            conn.close()
            return
        
        # 设置共享状态
        if path == '/state':
            key = body.get('key')
            value = json.dumps(body.get('value'))
            updated_by = body.get('updated_by', 'unknown')
            ttl = body.get('ttl')
            c.execute("INSERT OR REPLACE INTO shared_state (key, value, updated_by, updated_at, ttl) VALUES (?, ?, ?, ?, ?)",
                (key, value, updated_by, now, ttl))
            conn.commit()
            self.send_json({"key": key, "status": "set"})
            conn.close()
            return
        
        # 创建协作任务
        if path == '/tasks':
            task_id = str(uuid.uuid4())
            c.execute("INSERT INTO collab_tasks (id, title, description, creator, assignee, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (task_id, body.get('title'), body.get('description'), body.get('creator'),
                 body.get('assignee'), 'pending', body.get('priority', 'normal'), now, now))
            conn.commit()
            self.send_json({"id": task_id, "status": "created"})
            conn.close()
            return
        
        # 更新任务状态
        if path.startswith('/tasks/') and path.endswith('/status'):
            task_id = path.split('/')[-2]
            new_status = body.get('status')
            if new_status == 'completed':
                c.execute("UPDATE collab_tasks SET status=?, updated_at=?, completed_at=?, result=? WHERE id=?",
                    (new_status, now, now, json.dumps(body.get('result')), task_id))
            else:
                c.execute("UPDATE collab_tasks SET status=?, updated_at=? WHERE id=?", (new_status, now, task_id))
            conn.commit()
            self.send_json({"id": task_id, "status": new_status})
            conn.close()
            return
        
        # 发布事件
        if path == '/events':
            event_id = str(uuid.uuid4())
            c.execute("INSERT INTO events (id, event_type, source, data, created_at) VALUES (?, ?, ?, ?, ?)",
                (event_id, body.get('type'), body.get('source'), json.dumps(body.get('data', {})), now))
            conn.commit()
            
            # 触发订阅者
            c.execute("SELECT subscriber, callback_url FROM subscriptions WHERE event_type=?", (body.get('type'),))
            for row in c.fetchall():
                print(f"[CollabCenter] Event {event_id} triggered subscriber: {row[0]}")
            
            self.send_json({"id": event_id, "status": "published"})
            conn.close()
            return
        
        # 订阅事件
        if path == '/subscriptions':
            sub_id = str(uuid.uuid4())
            c.execute("INSERT INTO subscriptions (id, event_type, subscriber, callback_url, created_at) VALUES (?, ?, ?, ?, ?)",
                (sub_id, body.get('event_type'), body.get('subscriber'), body.get('callback_url'), now))
            conn.commit()
            self.send_json({"id": sub_id, "status": "subscribed"})
            conn.close()
            return
        
        self.send_json({"error": "Not found"}, 404)
        conn.close()
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 删除服务
        if path.startswith('/services/'):
            service_id = path.split('/')[-1]
            c.execute("UPDATE services SET status='inactive' WHERE id=?", (service_id,))
            conn.commit()
            self.send_json({"status": "deleted"})
            conn.close()
            return
        
        # 删除任务
        if path.startswith('/tasks/'):
            task_id = path.split('/')[-1]
            c.execute("DELETE FROM collab_tasks WHERE id=?", (task_id,))
            conn.commit()
            self.send_json({"status": "deleted"})
            conn.close()
            return
        
        # 删除订阅
        if path.startswith('/subscriptions/'):
            sub_id = path.split('/')[-1]
            c.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
            conn.commit()
            self.send_json({"status": "deleted"})
            conn.close()
            return
        
        self.send_json({"error": "Not found"}, 404)
        conn.close()

def run_server():
    port = 18201
    server = HTTPServer(('0.0.0.0', port), CollabCenterHandler)
    print(f"[CollabCenter] Collaboration Center API running on port {port}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()