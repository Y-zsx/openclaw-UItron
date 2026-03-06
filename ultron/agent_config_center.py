#!/usr/bin/env python3
"""
Agent服务配置中心系统
集中式配置管理服务，支持配置的动态更新、版本管理、灰度发布
端口: 18308
"""

import json
import sqlite3
import time
import hashlib
import os
from datetime import datetime
from flask import Flask, request, jsonify
from threading import Lock

app = Flask(__name__)
DB_PATH = '/root/.openclaw/workspace/ultron/config_center.db'
lock = Lock()

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 配置表
    c.execute('''CREATE TABLE IF NOT EXISTS configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        namespace TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        version INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        created_by TEXT DEFAULT 'system',
        description TEXT,
        UNIQUE(namespace, key)
    )''')
    
    # 版本历史表
    c.execute('''CREATE TABLE IF NOT EXISTS config_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        namespace TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        version INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        created_by TEXT DEFAULT 'system',
        change_log TEXT,
        UNIQUE(namespace, key, version)
    )''')
    
    # 灰度发布表
    c.execute('''CREATE TABLE IF NOT EXISTS grayscale_releases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        namespace TEXT NOT NULL,
        key TEXT NOT NULL,
        target_version INTEGER NOT NULL,
        rollout_percentage INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TEXT NOT NULL,
        completed_at TEXT,
        conditions TEXT
    )''')
    
    # 监听者表
    c.execute('''CREATE TABLE IF NOT EXISTS config_watchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        namespace TEXT NOT NULL,
        key TEXT,
        callback_url TEXT NOT NULL,
        created_at TEXT NOT NULL,
        active INTEGER DEFAULT 1
    )''')
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "config-center", "port": 18308})

@app.route('/api/configs', methods=['GET'])
def get_configs():
    """获取配置列表"""
    namespace = request.args.get('namespace')
    conn = get_db()
    c = conn.cursor()
    
    if namespace:
        c.execute('SELECT * FROM configs WHERE namespace = ?', (namespace,))
    else:
        c.execute('SELECT * FROM configs')
    
    configs = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({"configs": configs})

@app.route('/api/config/<namespace>/<key>', methods=['GET'])
def get_config(namespace, key):
    """获取单个配置"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM configs WHERE namespace = ? AND key = ?', (namespace, key))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "Config not found"}), 404

@app.route('/api/config', methods=['POST'])
def set_config():
    """设置配置"""
    data = request.json
    namespace = data.get('namespace', 'default')
    key = data.get('key')
    value = data.get('value')
    description = data.get('description', '')
    created_by = data.get('created_by', 'api')
    
    if not key or value is None:
        return jsonify({"error": "key and value required"}), 400
    
    with lock:
        conn = get_db()
        c = conn.cursor()
        
        # 检查是否存在
        c.execute('SELECT version FROM configs WHERE namespace = ? AND key = ?', (namespace, key))
        row = c.fetchone()
        
        now = datetime.now().isoformat()
        
        if row:
            # 更新现有配置
            new_version = row['version'] + 1
            c.execute('''UPDATE configs 
                SET value = ?, version = ?, updated_at = ?, description = ?
                WHERE namespace = ? AND key = ?''',
                (json.dumps(value), new_version, now, description, namespace, key))
            
            # 记录版本历史
            c.execute('''INSERT INTO config_versions (namespace, key, value, version, created_at, created_by, change_log)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (namespace, key, json.dumps(value), new_version, now, created_by, description))
        else:
            # 新增配置
            c.execute('''INSERT INTO configs (namespace, key, value, version, created_at, updated_at, created_by, description)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?)''',
                (namespace, key, json.dumps(value), now, now, created_by, description))
            
            # 记录版本历史
            c.execute('''INSERT INTO config_versions (namespace, key, value, version, created_at, created_by, change_log)
                VALUES (?, ?, ?, 1, ?, ?, ?)''',
                (namespace, key, json.dumps(value), now, created_by, description))
        
        conn.commit()
        conn.close()
    
    return jsonify({"success": True, "namespace": namespace, "key": key})

@app.route('/api/config/<namespace>/<key>', methods=['DELETE'])
def delete_config(namespace, key):
    """删除配置"""
    with lock:
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM configs WHERE namespace = ? AND key = ?', (namespace, key))
        conn.commit()
        deleted = c.rowcount > 0
        conn.close()
    
    if deleted:
        return jsonify({"success": True})
    return jsonify({"error": "Config not found"}), 404

@app.route('/api/config/versions/<namespace>/<key>', methods=['GET'])
def get_config_versions(namespace, key):
    """获取配置版本历史"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT * FROM config_versions 
        WHERE namespace = ? AND key = ? 
        ORDER BY version DESC''', (namespace, key))
    versions = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({"versions": versions})

@app.route('/api/config/rollback/<namespace>/<key>/<int:version>', methods=['POST'])
def rollback_config(namespace, key, version):
    """回滚配置到指定版本"""
    with lock:
        conn = get_db()
        c = conn.cursor()
        
        # 获取目标版本
        c.execute('SELECT * FROM config_versions WHERE namespace = ? AND key = ? AND version = ?',
            (namespace, key, version))
        target = c.fetchone()
        
        if not target:
            conn.close()
            return jsonify({"error": "Version not found"}), 404
        
        # 更新当前配置
        now = datetime.now().isoformat()
        new_version = c.execute('SELECT version FROM configs WHERE namespace = ? AND key = ?',
            (namespace, key)).fetchone()
        
        new_version = new_version['version'] + 1 if new_version else 1
        
        c.execute('''UPDATE configs SET value = ?, version = ?, updated_at = ?, description = ?
            WHERE namespace = ? AND key = ?''',
            (target['value'], new_version, now, f"Rollback to version {version}", namespace, key))
        
        # 记录新版本
        c.execute('''INSERT INTO config_versions (namespace, key, value, version, created_at, created_by, change_log)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (namespace, key, target['value'], new_version, now, 'system', f"Rollback to version {version}"))
        
        conn.commit()
        conn.close()
    
    return jsonify({"success": True, "new_version": new_version})

@app.route('/api/grayscale', methods=['POST'])
def create_grayscale():
    """创建灰度发布"""
    data = request.json
    namespace = data.get('namespace')
    key = data.get('key')
    target_version = data.get('target_version')
    conditions = data.get('conditions', {})
    
    if not all([namespace, key, target_version]):
        return jsonify({"error": "namespace, key, target_version required"}), 400
    
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    c.execute('''INSERT INTO grayscale_releases 
        (namespace, key, target_version, rollout_percentage, status, created_at, conditions)
        VALUES (?, ?, ?, 0, 'pending', ?, ?)''',
        (namespace, key, target_version, now, json.dumps(conditions)))
    
    release_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "release_id": release_id})

@app.route('/api/grayscale/<int:release_id>', methods=['GET'])
def get_grayscale(release_id):
    """获取灰度发布状态"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM grayscale_releases WHERE id = ?', (release_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "Release not found"}), 404

@app.route('/api/grayscale/<int:release_id>/rollout', methods=['POST'])
def update_grayscale_rollout(release_id):
    """更新灰度发布进度"""
    data = request.json
    percentage = data.get('rollout_percentage', 0)
    status = data.get('status', 'rolling')
    
    conn = get_db()
    c = conn.cursor()
    
    if status == 'completed':
        c.execute('UPDATE grayscale_releases SET rollout_percentage = ?, status = ?, completed_at = ? WHERE id = ?',
            (percentage, status, datetime.now().isoformat(), release_id))
    else:
        c.execute('UPDATE grayscale_releases SET rollout_percentage = ?, status = ? WHERE id = ?',
            (percentage, status, release_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

@app.route('/api/grayscale/list', methods=['GET'])
def list_grayscale():
    """列出所有灰度发布"""
    namespace = request.args.get('namespace')
    conn = get_db()
    c = conn.cursor()
    
    if namespace:
        c.execute('SELECT * FROM grayscale_releases WHERE namespace = ? ORDER BY created_at DESC', (namespace,))
    else:
        c.execute('SELECT * FROM grayscale_releases ORDER BY created_at DESC')
    
    releases = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({"releases": releases})

@app.route('/api/watch', methods=['POST'])
def add_watcher():
    """添加配置监听者"""
    data = request.json
    namespace = data.get('namespace', 'default')
    key = data.get('key')
    callback_url = data.get('callback_url')
    
    if not callback_url:
        return jsonify({"error": "callback_url required"}), 400
    
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    c.execute('''INSERT INTO config_watchers (namespace, key, callback_url, created_at)
        VALUES (?, ?, ?, ?)''',
        (namespace, key, callback_url, now))
    
    watcher_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "watcher_id": watcher_id})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取配置中心统计"""
    conn = get_db()
    c = conn.cursor()
    
    # 配置总数
    total_configs = c.execute('SELECT COUNT(*) FROM configs').fetchone()[0]
    
    # 命名空间数
    total_namespaces = c.execute('SELECT COUNT(DISTINCT namespace) FROM configs').fetchone()[0]
    
    # 版本历史总数
    total_versions = c.execute('SELECT COUNT(*) FROM config_versions').fetchone()[0]
    
    # 灰度发布数
    active_releases = c.execute("SELECT COUNT(*) FROM grayscale_releases WHERE status IN ('pending', 'rolling')").fetchone()[0]
    
    # 监听者数
    total_watchers = c.execute('SELECT COUNT(*) FROM config_watchers WHERE active = 1').fetchone()[0]
    
    conn.close()
    
    return jsonify({
        "total_configs": total_configs,
        "total_namespaces": total_namespaces,
        "total_versions": total_versions,
        "active_releases": active_releases,
        "total_watchers": total_watchers
    })

if __name__ == '__main__':
    init_db()
    print("Agent服务配置中心系统启动 - 端口: 18308")
    app.run(host='0.0.0.0', port=18308, debug=False)