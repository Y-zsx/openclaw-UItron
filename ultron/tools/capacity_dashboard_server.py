#!/usr/bin/env python3
"""
容量规划Dashboard服务器
"""

from flask import Flask, send_file
import os

app = Flask(__name__)

@app.route('/')
def index():
    return send_file('/root/.openclaw/workspace/ultron/tools/capacity_dashboard.html')

if __name__ == '__main__':
    print("🚀 容量规划Dashboard启动...")
    print("📊 Dashboard: http://0.0.0.0:18241")
    app.run(host='0.0.0.0', port=18241, debug=False)