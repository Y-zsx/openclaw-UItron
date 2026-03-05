#!/usr/bin/env python3
"""
智能告警分析API服务
端口: 18125
"""

from flask import Flask, jsonify, request
import json
import os
from datetime import datetime

app = Flask(__name__)

DATA_DIR = "/root/.openclaw/workspace/ultron/data"
HISTORY_FILE = f"{DATA_DIR}/alert-intelligence-history.json"
ANALYSIS_FILE = f"{DATA_DIR}/alert-analysis.json"
REPORT_FILE = f"{DATA_DIR}/alert-intelligence-report.json"

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'alert-intelligence-api'})

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """获取历史指标"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({'metrics': [], 'alerts': []})

@app.route('/analysis', methods=['GET'])
def get_analysis():
    """获取分析结果"""
    if os.path.exists(ANALYSIS_FILE):
        with open(ANALYSIS_FILE, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({'status': 'no_analysis', 'message': '暂无分析数据'})

@app.route('/report', methods=['GET'])
def get_report():
    """获取完整智能报告"""
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({'status': 'no_report', 'message': '暂无报告'})

@app.route('/collect', methods=['POST'])
def collect():
    """手动触发采集"""
    from alert_analyzer import AlertIntelligence
    ai = AlertIntelligence()
    metrics = ai.collect_metrics()
    ai.analyze_trends()
    ai.analyze_alert_patterns()
    return jsonify({'status': 'collected', 'metrics': metrics})

@app.route('/predict', methods=['GET'])
def predict():
    """获取预测结果"""
    if os.path.exists(ANALYSIS_FILE):
        with open(ANALYSIS_FILE, 'r') as f:
            data = json.load(f)
            return jsonify(data.get('prediction', {}))
    return jsonify({'status': 'no_data'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18125, debug=False)