#!/usr/bin/env python3
"""
Agent Collaboration Hub - 多智能体协作中心
聚合所有协作状态，提供统一的协作视图
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

COLLAB_DB = "/root/.openclaw/workspace/ultron/tools/collaboration.db"

def init_db():
    """初始化协作数据库"""
    conn = sqlite3.connect(COLLAB_DB)
    c = conn.cursor()
    
    # Agent状态表
    c.execute('''CREATE TABLE IF NOT EXISTS agent_status (
        agent_id TEXT PRIMARY KEY,
        name TEXT,
        status TEXT,
        capabilities TEXT,
        load REAL,
        last_seen REAL,
        metadata TEXT
    )''')
    
    # 协作关系表
    c.execute('''CREATE TABLE IF NOT EXISTS collaboration_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_agent TEXT,
        target_agent TEXT,
        link_type TEXT,
        strength REAL,
        last_interaction REAL,
        interaction_count INTEGER
    )''')
    
    # 消息交换表
    c.execute('''CREATE TABLE IF NOT EXISTS message_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        source_agent TEXT,
        target_agent TEXT,
        message_type TEXT,
        content TEXT,
        success INTEGER
    )''')
    
    # 任务协调表
    c.execute('''CREATE TABLE IF NOT EXISTS task_coordination (
        task_id TEXT PRIMARY KEY,
        task_type TEXT,
        assigned_agents TEXT,
        status TEXT,
        progress REAL,
        created_at REAL,
        updated_at REAL
    )''')
    
    conn.commit()
    return conn

def register_agent(agent_id: str, name: str, capabilities: List[str], metadata: dict = None):
    """注册智能体"""
    conn = init_db()
    c = conn.cursor()
    
    c.execute('''INSERT OR REPLACE INTO agent_status 
        (agent_id, name, status, capabilities, load, last_seen, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (agent_id, name, "active", json.dumps(capabilities), 0.0, time.time(), 
         json.dumps(metadata or {})))
    
    conn.commit()
    conn.close()
    return {"status": "registered", "agent_id": agent_id}

def update_agent_status(agent_id: str, status: str = None, load: float = None):
    """更新智能体状态"""
    conn = init_db()
    c = conn.cursor()
    
    updates = []
    params = []
    
    if status:
        updates.append("status = ?")
        params.append(status)
    if load is not None:
        updates.append("load = ?")
        params.append(load)
    
    updates.append("last_seen = ?")
    params.append(time.time())
    params.append(agent_id)
    
    c.execute(f"UPDATE agent_status SET {', '.join(updates)} WHERE agent_id = ?", params)
    conn.commit()
    conn.close()
    return {"status": "updated", "agent_id": agent_id}

def establish_link(source: str, target: str, link_type: str, strength: float = 0.5):
    """建立协作链接"""
    conn = init_db()
    c = conn.cursor()
    
    c.execute('''INSERT OR REPLACE INTO collaboration_links 
        (source_agent, target_agent, link_type, strength, last_interaction, interaction_count)
        VALUES (?, ?, ?, ?, ?, 1)''',
        (source, target, link_type, strength, time.time()))
    
    conn.commit()
    conn.close()
    return {"status": "linked", "source": source, "target": target}

def record_message(source: str, target: str, msg_type: str, content: str, success: bool = True):
    """记录消息交换"""
    conn = init_db()
    c = conn.cursor()
    
    c.execute('''INSERT INTO message_log 
        (timestamp, source_agent, target_agent, message_type, content, success)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (time.time(), source, target, msg_type, content, 1 if success else 0))
    
    # 更新交互计数
    c.execute('''UPDATE collaboration_links 
        SET last_interaction = ?, interaction_count = interaction_count + 1
        WHERE source_agent = ? AND target_agent = ?''',
        (time.time(), source, target))
    
    conn.commit()
    conn.close()
    return {"status": "recorded"}

def coordinate_task(task_id: str, task_type: str, agents: List[str]):
    """任务协调"""
    conn = init_db()
    c = conn.cursor()
    
    c.execute('''INSERT OR REPLACE INTO task_coordination 
        (task_id, task_type, assigned_agents, status, progress, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (task_id, task_type, json.dumps(agents), "pending", 0.0, time.time(), time.time()))
    
    conn.commit()
    conn.close()
    return {"status": "coordinated", "task_id": task_id}

def get_collaboration_status() -> Dict:
    """获取协作状态总览"""
    conn = init_db()
    c = conn.cursor()
    
    # Agent数量
    c.execute("SELECT COUNT(*) FROM agent_status WHERE status = 'active'")
    active_agents = c.fetchone()[0]
    
    # 协作链接数
    c.execute("SELECT COUNT(*) FROM collaboration_links")
    link_count = c.fetchone()[0]
    
    # 最近消息数
    recent = time.time() - 3600
    c.execute("SELECT COUNT(*) FROM message_log WHERE timestamp > ?", (recent,))
    recent_messages = c.fetchone()[0]
    
    # 活跃任务
    c.execute("SELECT COUNT(*) FROM task_coordination WHERE status != 'completed'")
    active_tasks = c.fetchone()[0]
    
    conn.close()
    
    return {
        "active_agents": active_agents,
        "collaboration_links": link_count,
        "recent_messages_1h": recent_messages,
        "active_tasks": active_tasks,
        "timestamp": datetime.now().isoformat()
    }

def get_agent_network() -> List[Dict]:
    """获取Agent网络拓扑"""
    conn = init_db()
    c = conn.cursor()
    
    # 获取所有agent
    c.execute("SELECT agent_id, name, status, load, last_seen FROM agent_status")
    agents = []
    for row in c.fetchall():
        agents.append({
            "id": row[0],
            "name": row[1],
            "status": row[2],
            "load": row[3],
            "last_seen": row[4]
        })
    
    # 获取协作关系
    c.execute("SELECT source_agent, target_agent, link_type, strength, interaction_count FROM collaboration_links")
    links = []
    for row in c.fetchall():
        links.append({
            "source": row[0],
            "target": row[1],
            "type": row[2],
            "strength": row[3],
            "interactions": row[4]
        })
    
    conn.close()
    
    return {"nodes": agents, "links": links}

def get_task_board() -> List[Dict]:
    """获取任务看板"""
    conn = init_db()
    c = conn.cursor()
    
    c.execute('''SELECT task_id, task_type, assigned_agents, status, progress, created_at, updated_at
        FROM task_coordination ORDER BY updated_at DESC LIMIT 20''')
    
    tasks = []
    for row in c.fetchall():
        tasks.append({
            "task_id": row[0],
            "type": row[1],
            "agents": json.loads(row[2]),
            "status": row[3],
            "progress": row[4],
            "created": row[5],
            "updated": row[6]
        })
    
    conn.close()
    return tasks

def get_communication_stats() -> Dict:
    """获取通信统计"""
    conn = init_db()
    c = conn.cursor()
    
    # 总消息数
    c.execute("SELECT COUNT(*) FROM message_log")
    total = c.fetchone()[0]
    
    # 成功率
    c.execute("SELECT COUNT(*) FROM message_log WHERE success = 1")
    success = c.fetchone()[0]
    
    # 按类型统计
    c.execute("SELECT message_type, COUNT(*) FROM message_log GROUP BY message_type")
    by_type = {row[0]: row[1] for row in c.fetchall()}
    
    # 按Agent统计
    c.execute('''SELECT source_agent, COUNT(*) FROM message_log 
        GROUP BY source_agent ORDER BY COUNT(*) DESC LIMIT 10''')
    by_agent = {row[0]: row[1] for row in c.fetchall()}
    
    conn.close()
    
    return {
        "total_messages": total,
        "success_rate": success / total if total > 0 else 0,
        "by_type": by_type,
        "top_talkers": by_agent
    }

def cleanup_old_records(days: int = 7):
    """清理旧记录"""
    conn = init_db()
    c = conn.cursor()
    
    cutoff = time.time() - (days * 86400)
    
    c.execute("DELETE FROM message_log WHERE timestamp < ?", (cutoff,))
    deleted = c.rowcount
    
    conn.commit()
    conn.close()
    
    return {"deleted_records": deleted}

# API Server
def run_server(port: int = 18900):
    """运行协作中心API服务器"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse
    
    init_db()
    
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            
            if path == "/status":
                self.send_json(get_collaboration_status())
            elif path == "/network":
                self.send_json(get_agent_network())
            elif path == "/tasks":
                self.send_json(get_task_board())
            elif path == "/stats":
                self.send_json(get_communication_stats())
            else:
                self.send_error(404)
        
        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body) if length > 0 else {}
            
            path = urllib.parse.urlparse(self.path).path
            
            if path == "/register":
                result = register_agent(data.get("agent_id"), data.get("name"), 
                                       data.get("capabilities", []), data.get("metadata"))
                self.send_json(result)
            elif path == "/update":
                result = update_agent_status(data.get("agent_id"), 
                                            data.get("status"), data.get("load"))
                self.send_json(result)
            elif path == "/link":
                result = establish_link(data.get("source"), data.get("target"),
                                       data.get("type", "collaboration"), 
                                       data.get("strength", 0.5))
                self.send_json(result)
            elif path == "/message":
                result = record_message(data.get("source"), data.get("target"),
                                       data.get("type", "message"), 
                                       data.get("content", ""),
                                       data.get("success", True))
                self.send_json(result)
            elif path == "/coordinate":
                result = coordinate_task(data.get("task_id"), data.get("type"),
                                        data.get("agents", []))
                self.send_json(result)
            else:
                self.send_error(404)
        
        def send_json(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
    
    print(f"Agent Collaboration Hub running on port {port}")
    server = HTTPServer(("", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "server":
            run_server()
        elif sys.argv[1] == "status":
            print(json.dumps(get_collaboration_status(), indent=2))
        elif sys.argv[1] == "network":
            print(json.dumps(get_agent_network(), indent=2))
        elif sys.argv[1] == "tasks":
            print(json.dumps(get_task_board(), indent=2))
        elif sys.argv[1] == "stats":
            print(json.dumps(get_communication_stats(), indent=2))
        elif sys.argv[1] == "cleanup":
            print(json.dumps(cleanup_old_records(), indent=2))
    else:
        # 注册一些默认agents
        register_agent("ultron-core", "奥创核心", ["reasoning", "execution", "monitoring"])
        register_agent("health-agent", "健康检查Agent", ["healthcheck", "alerting"])
        register_agent("task-agent", "任务Agent", ["scheduling", "execution"])
        register_agent("log-agent", "日志Agent", ["aggregation", "analysis"])
        establish_link("ultron-core", "health-agent", "monitoring")
        establish_link("ultron-core", "task-agent", "delegation")
        establish_link("ultron-core", "log-agent", "monitoring")
        establish_link("health-agent", "log-agent", "correlation")
        print("Collaboration Hub initialized")
        print(json.dumps(get_collaboration_status(), indent=2))