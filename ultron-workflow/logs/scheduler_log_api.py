#!/usr/bin/env python3
"""
调度任务日志分析API服务
提供REST接口查询调度任务执行统计和趋势
"""

import json
import os
from flask import Flask, jsonify, request
from scheduler_log_analyzer import SchedulerLogAnalyzer

app = Flask(__name__)
analyzer = SchedulerLogAnalyzer()

PORT = 18192
STATS_FILE = "/root/.openclaw/workspace/ultron-workflow/logs/scheduler_stats.json"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'scheduler-log-analyzer'})

@app.route('/stats', methods=['GET'])
def stats():
    """获取调度任务统计"""
    try:
        stats_data = analyzer.analyze()
        return jsonify(stats_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/trends', methods=['GET'])
def trends():
    """获取任务执行趋势"""
    try:
        hours = int(request.args.get('hours', 6))
        trends_data = analyzer.get_task_trends(hours)
        return jsonify({'trends': trends_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tasks', methods=['GET'])
def tasks():
    """获取各任务详细统计"""
    try:
        stats_data = analyzer.analyze()
        return jsonify(stats_data.get('task_stats', {}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/latest', methods=['GET'])
def latest():
    """获取最近执行记录"""
    try:
        limit = int(request.args.get('limit', 10))
        stats_data = analyzer.analyze()
        runs = stats_data.get('latest_runs', [])
        return jsonify({'runs': runs[:limit]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save', methods=['POST'])
def save():
    """保存统计到文件"""
    try:
        stats = analyzer.save_stats()
        return jsonify({'saved': True, 'file': STATS_FILE})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    print(f"启动调度任务日志分析API服务，端口: {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)