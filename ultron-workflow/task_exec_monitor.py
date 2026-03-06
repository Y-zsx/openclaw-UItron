#!/usr/bin/env python3
"""
任务执行监控和日志服务
监控所有任务执行，记录日志，提供API查询
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
import threading

DB_PATH = "/root/.openclaw/workspace/ultron-workflow/task_monitor.db"
LOG_DIR = "/root/.openclaw/workspace/ultron-workflow/logs"
app = Flask(__name__)

# 初始化数据库
def init_db():
    os.makedirs(LOG_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 任务执行记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            task_name TEXT,
            status TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_ms INTEGER,
            error_message TEXT,
            result TEXT,
            triggered_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 任务状态表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_status (
            task_id TEXT PRIMARY KEY,
            task_name TEXT,
            status TEXT NOT NULL,
            last_run TEXT,
            next_run TEXT,
            run_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            avg_duration_ms INTEGER,
            last_error TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 任务统计表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            date TEXT NOT NULL,
            total_runs INTEGER DEFAULT 0,
            success_runs INTEGER DEFAULT 0,
            fail_runs INTEGER DEFAULT 0,
            avg_duration_ms INTEGER,
            UNIQUE(task_id, date)
        )
    ''')
    
    conn.commit()
    conn.close()

# 记录任务开始
def log_task_start(task_id, task_name=None, triggered_by=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    start_time = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO task_executions (task_id, task_name, status, start_time, triggered_by) VALUES (?, ?, ?, ?, ?)",
        (task_id, task_name, "running", start_time, triggered_by)
    )
    
    execution_id = cursor.lastrowid
    
    # 更新任务状态
    cursor.execute(
        "INSERT OR REPLACE INTO task_status (task_id, task_name, status, last_run, updated_at) VALUES (?, ?, ?, ?, ?)",
        (task_id, task_name, "running", start_time, datetime.now().isoformat())
    )
    
    conn.commit()
    conn.close()
    
    return execution_id

# 记录任务结束
def log_task_end(execution_id, status, error_message=None, result=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    end_time = datetime.now().isoformat()
    
    # 获取开始时间计算耗时
    cursor.execute("SELECT start_time, task_id FROM task_executions WHERE id = ?", (execution_id,))
    row = cursor.fetchone()
    
    if row:
        start_time = row[0]
        task_id = row[1]
        
        # 计算耗时
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        
        # 更新执行记录
        cursor.execute(
            "UPDATE task_executions SET status = ?, end_time = ?, duration_ms = ?, error_message = ?, result = ? WHERE id = ?",
            (status, end_time, duration_ms, error_message, result, execution_id)
        )
        
        # 更新任务统计
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        if status == "success":
            cursor.execute('''
                INSERT INTO task_stats (task_id, date, total_runs, success_runs, avg_duration_ms)
                VALUES (?, ?, 1, 1, ?)
                ON CONFLICT(task_id, date) DO UPDATE SET
                    total_runs = total_runs + 1,
                    success_runs = success_runs + 1,
                    avg_duration_ms = (avg_duration_ms * total_runs + ?) / (total_runs + 1)
            ''', (task_id, date_str, duration_ms, duration_ms))
        else:
            cursor.execute('''
                INSERT INTO task_stats (task_id, date, total_runs, fail_runs)
                VALUES (?, ?, 1, 1)
                ON CONFLICT(task_id, date) DO UPDATE SET
                    total_runs = total_runs + 1,
                    fail_runs = fail_runs + 1
            ''', (task_id, date_str))
        
        # 更新任务状态
        cursor.execute(
            "UPDATE task_status SET status = ?, last_run = ?, updated_at = ?, last_error = ? WHERE task_id = ?",
            (status, end_time, datetime.now().isoformat(), error_message, task_id)
        )
        
        # 更新计数
        if status == "success":
            cursor.execute(
                "UPDATE task_status SET success_count = success_count + 1, run_count = run_count + 1, avg_duration_ms = ? WHERE task_id = ?",
                (duration_ms, task_id)
            )
        else:
            cursor.execute(
                "UPDATE task_status SET fail_count = fail_count + 1, run_count = run_count + 1, last_error = ? WHERE task_id = ?",
                (error_message, task_id)
            )
    
    conn.commit()
    conn.close()

# API: 获取所有任务状态
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM task_status ORDER BY last_run DESC")
    tasks = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({"tasks": tasks, "count": len(tasks)})

# API: 获取单个任务详情
@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM task_status WHERE task_id = ?", (task_id,))
    task = dict(cursor.fetchone()) if cursor.fetchone() else None
    
    if task:
        # 获取最近执行记录
        cursor.execute(
            "SELECT * FROM task_executions WHERE task_id = ? ORDER BY start_time DESC LIMIT 20",
            (task_id,)
        )
        executions = [dict(row) for row in cursor.fetchall()]
        task["recent_executions"] = executions
    
    conn.close()
    
    if task:
        return jsonify(task)
    return jsonify({"error": "Task not found"}), 404

# API: 获取执行历史
@app.route('/api/executions', methods=['GET'])
def get_executions():
    limit = request.args.get('limit', 50, type=int)
    task_id = request.args.get('task_id')
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if task_id:
        cursor.execute(
            "SELECT * FROM task_executions WHERE task_id = ? ORDER BY start_time DESC LIMIT ?",
            (task_id, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM task_executions ORDER BY start_time DESC LIMIT ?",
            (limit,)
        )
    
    executions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({"executions": executions, "count": len(executions)})

# API: 获取统计数据
@app.route('/api/stats', methods=['GET'])
def get_stats():
    days = request.args.get('days', 7, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 获取汇总统计
    start_date = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute('''
        SELECT 
            COUNT(*) as total_executions,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) as fail_count,
            AVG(duration_ms) as avg_duration_ms
        FROM task_executions
        WHERE start_time >= ?
    ''', (start_date,))
    
    summary = dict(cursor.fetchone())
    
    # 按任务分组统计
    cursor.execute('''
        SELECT 
            task_id,
            task_name,
            COUNT(*) as total_runs,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_runs,
            SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) as fail_runs,
            AVG(duration_ms) as avg_duration_ms
        FROM task_executions
        WHERE start_time >= ?
        GROUP BY task_id
        ORDER BY total_runs DESC
    ''', (start_date,))
    
    task_stats = [dict(row) for row in cursor.fetchall()]
    
    # 按日期统计
    cursor.execute('''
        SELECT 
            date(start_time) as date,
            COUNT(*) as total_runs,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_runs,
            SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) as fail_runs
        FROM task_executions
        WHERE start_time >= ?
        GROUP BY date(start_time)
        ORDER BY date DESC
    ''', (start_date,))
    
    daily_stats = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        "summary": summary,
        "task_stats": task_stats,
        "daily_stats": daily_stats,
        "period_days": days
    })

# API: 健康检查
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "task_exec_monitor",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    init_db()
    print("Task Exec Monitor starting on port 18219...")
    app.run(host='0.0.0.0', port=18219, debug=False)