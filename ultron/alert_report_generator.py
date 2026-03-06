#!/usr/bin/env python3
"""
告警分析报告自动生成服务
自动生成周期性告警分析报告
端口: 18224
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from collections import defaultdict

app = Flask(__name__)

DB_FILE = "/root/.openclaw/workspace/ultron/data/alerts.db"
REPORTS_DIR = "/root/.openclaw/workspace/ultron/reports"
CONFIG_FILE = "/root/.openclaw/workspace/ultron/data/report_config.json"

# 默认报告配置
DEFAULT_CONFIG = {
    "schedules": [
        {
            "id": "daily",
            "name": "每日报告",
            "schedule": "0 9 * * *",  # 每天9点
            "enabled": True,
            "period": "yesterday",
            "format": "json"
        },
        {
            "id": "weekly",
            "name": "每周报告",
            "schedule": "0 10 * * 1",  # 每周一10点
            "enabled": True,
            "period": "last_week",
            "format": "json"
        },
        {
            "id": "monthly",
            "name": "每月报告",
            "schedule": "0 11 1 * *",  # 每月1号10点
            "enabled": True,
            "period": "last_month",
            "format": "json"
        }
    ],
    "retention_days": 30
}

def init_dirs():
    """初始化目录"""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

def load_config():
    """加载配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """保存配置"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def generate_report_data(period):
    """生成报告数据"""
    conn = get_db()
    c = conn.cursor()
    
    # 计算时间范围
    now = datetime.now()
    if period == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
        end = now.replace(hour=0, minute=0, second=0)
    elif period == "last_week":
        start = now - timedelta(days=7)
        end = now
    elif period == "last_month":
        start = now - timedelta(days=30)
        end = now
    elif period == "today":
        start = now.replace(hour=0, minute=0, second=0)
        end = now
    else:
        start = now - timedelta(days=1)
        end = now
    
    start_str = start.strftime('%Y-%m-%d %H:%M:%S')
    end_str = end.strftime('%Y-%m-%d %H:%M:%S')
    
    # 总告警数
    c.execute("SELECT COUNT(*) FROM alerts WHERE timestamp >= ? AND timestamp < ?", (start_str, end_str))
    total = c.fetchone()[0]
    
    # 按级别统计
    c.execute("SELECT level, COUNT(*) FROM alerts WHERE timestamp >= ? AND timestamp < ? GROUP BY level", (start_str, end_str))
    by_level = {row[0]: row[1] for row in c.fetchall()}
    
    # 按渠道统计
    c.execute("SELECT channel, COUNT(*) FROM alerts WHERE timestamp >= ? AND timestamp < ? GROUP BY channel", (start_str, end_str))
    by_channel = {row[0]: row[1] for row in c.fetchall()}
    
    # 按服务统计
    c.execute("SELECT service, COUNT(*) FROM alerts WHERE timestamp >= ? AND timestamp < ? AND service IS NOT NULL GROUP BY service", (start_str, end_str))
    by_service = {row[0]: row[1] for row in c.fetchall()}
    
    # 按指标统计
    c.execute("SELECT metric, COUNT(*) FROM alerts WHERE timestamp >= ? AND timestamp < ? AND metric IS NOT NULL GROUP BY metric", (start_str, end_str))
    by_metric = {row[0]: row[1] for row in c.fetchall()}
    
    # 按状态统计
    c.execute("SELECT status, COUNT(*) FROM alerts WHERE timestamp >= ? AND timestamp < ? GROUP BY status", (start_str, end_str))
    by_status = {row[0]: row[1] for row in c.fetchall()}
    
    # 成功率
    ok_count = by_status.get('ok', 0)
    success_rate = (ok_count / total * 100) if total > 0 else 100
    
    # 告警趋势（按天）
    c.execute("""SELECT DATE(timestamp) as date, COUNT(*) 
        FROM alerts 
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY DATE(timestamp)
        ORDER BY date""", (start_str, end_str))
    daily_trend = [{"date": row[0], "count": row[1]} for row in c.fetchall()]
    
    # 高频告警消息
    c.execute("""SELECT message, COUNT(*) as cnt 
        FROM alerts 
        WHERE timestamp >= ? AND timestamp < ? AND message IS NOT NULL
        GROUP BY message
        ORDER BY cnt DESC
        LIMIT 10""", (start_str, end_str))
    top_messages = [{"message": row[0], "count": row[1]} for row in c.fetchall()]
    
    conn.close()
    
    return {
        "period": period,
        "start_time": start_str,
        "end_time": end_str,
        "summary": {
            "total": total,
            "success_rate": round(success_rate, 2),
            "by_level": by_level,
            "by_channel": by_channel,
            "by_status": by_status
        },
        "details": {
            "by_service": by_service,
            "by_metric": by_metric
        },
        "trends": {
            "daily": daily_trend
        },
        "top_messages": top_messages
    }

def generate_insights(report_data):
    """根据报告数据生成洞察"""
    insights = []
    
    summary = report_data.get('summary', {})
    details = report_data.get('details', {})
    
    # 告警数量分析
    total = summary.get('total', 0)
    if total == 0:
        insights.append({
            "type": "info",
            "title": "无告警记录",
            "description": "报告期间没有告警记录，系统运行正常"
        })
    else:
        insights.append({
            "type": "info",
            "title": f"告警概况",
            "description": f"报告期间共产生 {total} 条告警，成功率 {summary.get('success_rate', 0)}%"
        })
    
    # 级别分析
    by_level = summary.get('by_level', {})
    if 'critical' in by_level and by_level['critical'] > 0:
        insights.append({
            "type": "critical",
            "title": "严重告警",
            "description": f"存在 {by_level['critical']} 条严重告警，需要立即处理"
        })
    
    if 'warning' in by_level and by_level['warning'] > 10:
        insights.append({
            "type": "warning",
            "title": "警告较多",
            "description": f"存在 {by_level['warning']} 条警告告警，建议检查相关服务"
        })
    
    # 服务分析
    by_service = details.get('by_service', {})
    if by_service:
        top_service = max(by_service.items(), key=lambda x: x[1])
        if top_service[1] > 5:
            insights.append({
                "type": "warning",
                "title": "高频告警服务",
                "description": f"服务 '{top_service[0]}' 产生了 {top_service[1]} 条告警，建议重点关注"
            })
    
    # 趋势分析
    trends = report_data.get('trends', {}).get('daily', [])
    if len(trends) >= 2:
        if trends[-1]['count'] > trends[0]['count'] * 2:
            insights.append({
                "type": "warning",
                "title": "告警增加趋势",
                "description": "告警数量呈上升趋势，建议关注"
            })
        elif trends[-1]['count'] < trends[0]['count'] * 0.5:
            insights.append({
                "type": "success",
                "title": "告警减少趋势",
                "description": "告警数量显著下降，系统运行状况改善"
            })
    
    return insights

@app.route('/api/generate', methods=['POST'])
def generate_report():
    """生成报告"""
    data = request.get_json() or {}
    period = data.get('period', 'yesterday')
    report_format = data.get('format', 'json')
    
    report_data = generate_report_data(period)
    report_data['insights'] = generate_insights(report_data)
    report_data['generated_at'] = datetime.now().isoformat()
    report_data['report_id'] = f"{period}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 保存报告
    if report_format == 'json':
        filename = f"{REPORTS_DIR}/{report_data['report_id']}.json"
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    return jsonify({
        "status": "ok",
        "report": report_data,
        "format": report_format
    })

@app.route('/api/reports', methods=['GET'])
def list_reports():
    """列出报告"""
    limit = request.args.get('limit', 20, type=int)
    
    if not os.path.exists(REPORTS_DIR):
        return jsonify({"status": "ok", "reports": []})
    
    reports = []
    for filename in sorted(os.listdir(REPORTS_DIR), reverse=True)[:limit]:
        if filename.endswith('.json'):
            filepath = os.path.join(REPORTS_DIR, filename)
            stat = os.stat(filepath)
            reports.append({
                "filename": filename,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    return jsonify({
        "status": "ok",
        "reports": reports
    })

@app.route('/api/reports/<filename>', methods=['GET'])
def get_report(filename):
    """获取报告详情"""
    filepath = os.path.join(REPORTS_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({"status": "error", "message": "Report not found"}), 404
    
    with open(filepath, 'r') as f:
        report_data = json.load(f)
    
    return jsonify({
        "status": "ok",
        "report": report_data
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取报告配置"""
    config = load_config()
    return jsonify({
        "status": "ok",
        "config": config
    })

@app.route('/api/config', methods=['PUT', 'POST'])
def update_config():
    """更新报告配置"""
    config = load_config()
    data = request.get_json()
    
    if 'schedules' in data:
        config['schedules'] = data['schedules']
    if 'retention_days' in data:
        config['retention_days'] = data['retention_days']
    
    save_config(config)
    
    return jsonify({
        "status": "ok",
        "config": config
    })

@app.route('/api/insights', methods=['GET'])
def get_insights():
    """获取当前洞察"""
    period = request.args.get('period', 'today')
    report_data = generate_report_data(period)
    insights = generate_insights(report_data)
    
    return jsonify({
        "status": "ok",
        "period": period,
        "insights": insights
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "alert-report-generator",
        "port": 18224
    })

if __name__ == '__main__':
    init_dirs()
    print("启动告警分析报告自动生成服务...")
    print(f"端口: 18224")
    print(f"报告目录: {REPORTS_DIR}")
    app.run(host='0.0.0.0', port=18224, debug=False)