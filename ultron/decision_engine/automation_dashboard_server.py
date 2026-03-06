#!/usr/bin/env python3
"""
Decision Automation Dashboard Server
决策自动化增强面板服务
"""

from flask import Flask, send_from_directory
import os

app = Flask(__name__)
APP_DIR = "/root/.openclaw/workspace/ultron/decision_engine"

@app.route('/')
def index():
    return send_from_directory(APP_DIR, 'automation_dashboard.html')

@app.route('/health')
def health():
    return {"service": "automation-dashboard", "status": "ok"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18262, debug=False)