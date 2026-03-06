#!/usr/bin/env python3
"""
Decision Templates Library
决策自动化增强 - 决策模板库

提供可重用的智能决策模板
"""

from flask import Flask, request, jsonify
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_PATH = "/root/.openclaw/workspace/ultron/decision_engine/decision_templates.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS templates
                (id INTEGER PRIMARY KEY, name TEXT UNIQUE, category TEXT,
                 description TEXT, conditions TEXT, actions TEXT,
                 priority INTEGER DEFAULT 5, enabled INTEGER DEFAULT 1,
                 usage_count INTEGER DEFAULT 0, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS executions
                (id INTEGER PRIMARY KEY, template_id INTEGER, input_data TEXT,
                 output TEXT, result TEXT, executed_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

# 内置决策模板
BUILTIN_TEMPLATES = [
    {
        "name": "high_cpu_auto_scale",
        "category": "performance",
        "description": "CPU高负载时自动扩容或优化",
        "conditions": {
            "metric": "cpu",
            "operator": ">",
            "threshold": 80,
            "duration": 60
        },
        "actions": [
            {"type": "notify", "message": "CPU使用率过高", "level": "warning"},
            {"type": "shell", "command": "sync; echo 3 > /proc/sys/vm/drop_caches", "description": "清理缓存"}
        ],
        "priority": 8
    },
    {
        "name": "high_memory_cleanup",
        "category": "performance", 
        "description": "内存高负载时自动清理",
        "conditions": {
            "metric": "memory",
            "operator": ">",
            "threshold": 85,
            "duration": 60
        },
        "actions": [
            {"type": "notify", "message": "内存使用率过高", "level": "warning"},
            {"type": "shell", "command": "pkill -9 -f python3.*idle", "description": "清理空闲进程"}
        ],
        "priority": 9
    },
    {
        "name": "disk_full_alert",
        "category": "storage",
        "description": "磁盘空间不足告警",
        "conditions": {
            "metric": "disk",
            "operator": ">",
            "threshold": 90,
            "duration": 30
        },
        "actions": [
            {"type": "notify", "message": "磁盘空间不足", "level": "critical"},
            {"type": "shell", "command": "find /tmp -type f -mtime +7 -delete 2>/dev/null", "description": "清理临时文件"}
        ],
        "priority": 10
    },
    {
        "name": "service_health_check",
        "category": "health",
        "description": "服务健康检查与自动恢复",
        "conditions": {
            "metric": "service",
            "operator": "==",
            "value": "down"
        },
        "actions": [
            {"type": "notify", "message": "服务不可用", "level": "critical"},
            {"type": "script", "name": "restart_service", "description": "尝试重启服务"}
        ],
        "priority": 10
    },
    {
        "name": "predictive_cpu_warning",
        "category": "predictive",
        "description": "预测性CPU告警",
        "conditions": {
            "metric": "cpu_predicted",
            "operator": ">",
            "threshold": 80,
            "confidence": 60
        },
        "actions": [
            {"type": "notify", "message": "预测CPU即将过高", "level": "info"},
            {"type": "preventive", "action": "clear_cache", "description": "预防性清理"}
        ],
        "priority": 7
    },
    {
        "name": "auto_report_daily",
        "category": "scheduled",
        "description": "每日自动报告生成",
        "conditions": {
            "type": "schedule",
            "cron": "0 9 * * *"
        },
        "actions": [
            {"type": "script", "name": "generate_daily_report", "description": "生成日报"}
        ],
        "priority": 5
    }
]

def ensure_builtin_templates():
    """确保内置模板存在"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for t in BUILTIN_TEMPLATES:
        try:
            c.execute('''INSERT OR IGNORE INTO templates 
                        (name, category, description, conditions, actions, priority, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (t["name"], t["category"], t["description"],
                      json.dumps(t["conditions"]), json.dumps(t["actions"]),
                      t["priority"], datetime.now().isoformat()))
        except:
            pass
    conn.commit()
    conn.close()

ensure_builtin_templates()

# API端点
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"service": "decision-templates", "status": "ok"})

@app.route('/api/templates', methods=['GET'])
def list_templates():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM templates ORDER BY priority DESC")
    rows = c.fetchall()
    conn.close()
    
    templates = []
    for r in rows:
        templates.append({
            "id": r[0], "name": r[1], "category": r[2], "description": r[3],
            "conditions": json.loads(r[4]), "actions": json.loads(r[5]),
            "priority": r[6], "enabled": bool(r[7]), "usage_count": r[8], "created_at": r[9]
        })
    return jsonify(templates)

@app.route('/api/templates/<name>', methods=['GET'])
def get_template(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM templates WHERE name = ?", (name,))
    r = c.fetchone()
    conn.close()
    
    if not r:
        return jsonify({"error": "Template not found"}), 404
    
    return jsonify({
        "id": r[0], "name": r[1], "category": r[2], "description": r[3],
        "conditions": json.loads(r[4]), "actions": json.loads(r[5]),
        "priority": r[6], "enabled": bool(r[7]), "usage_count": r[8]
    })

@app.route('/api/templates', methods=['POST'])
def create_template():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO templates (name, category, description, conditions, actions, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
             (data["name"], data.get("category", "custom"), data.get("description", ""),
              json.dumps(data.get("conditions", {})), json.dumps(data.get("actions", [])),
              data.get("priority", 5), datetime.now().isoformat()))
    conn.commit()
    template_id = c.lastrowid
    conn.close()
    return jsonify({"id": template_id, "status": "created"})

@app.route('/api/templates/<name>/execute', methods=['POST'])
def execute_template(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM templates WHERE name = ? AND enabled = 1", (name,))
    r = c.fetchone()
    
    if not r:
        conn.close()
        return jsonify({"error": "Template not found or disabled"}), 404
    
    # 增加使用计数
    c.execute("UPDATE templates SET usage_count = usage_count + 1 WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    
    template = {
        "name": r[1], "conditions": json.loads(r[4]), "actions": json.loads(r[5])
    }
    
    # 执行动作
    results = []
    for action in template["actions"]:
        result = {"action": action.get("type"), "description": action.get("description", "")}
        try:
            if action.get("type") == "shell":
                import subprocess
                output = subprocess.run(action["command"], shell=True, capture_output=True, timeout=30)
                result["output"] = output.stdout.decode()[:200]
                result["success"] = output.returncode == 0
            elif action.get("type") == "notify":
                result["success"] = True
            else:
                result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        results.append(result)
    
    # 记录执行
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO executions (template_id, input_data, output, result, executed_at)
                VALUES (?, ?, ?, ?, ?)''',
             (r[0], json.dumps(request.json if request.json else {}),
              json.dumps(results), "completed", datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return jsonify({"template": name, "results": results})

@app.route('/api/templates/<name>/enable', methods=['POST'])
def enable_template(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE templates SET enabled = 1 WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    return jsonify({"status": "enabled"})

@app.route('/api/templates/<name>/disable', methods=['POST'])
def disable_template(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE templates SET enabled = 0 WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    return jsonify({"status": "disabled"})

@app.route('/api/categories', methods=['GET'])
def list_categories():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT category, COUNT(*) FROM templates GROUP BY category")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"category": r[0], "count": r[1]} for r in rows])

@app.route('/api/stats', methods=['GET'])
def stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM templates")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM templates WHERE enabled = 1")
    enabled = c.fetchone()[0]
    c.execute("SELECT SUM(usage_count) FROM templates")
    usage = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM executions WHERE executed_at > datetime('now', '-1 day')")
    today_executions = c.fetchone()[0]
    conn.close()
    return jsonify({
        "total_templates": total,
        "enabled_templates": enabled,
        "total_usages": usage,
        "today_executions": today_executions
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18261, debug=False)