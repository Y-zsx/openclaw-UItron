#!/usr/bin/env python3
"""
成本优化Dashboard服务
"""

from flask import Flask, send_file, jsonify
import os

app = Flask(__name__)

DASHBOARD_PATH = "/root/.openclaw/workspace/ultron/cost_optimizer/dashboard.html"
API_BASE = "http://localhost:18242"

@app.route('/')
def index():
    return send_file(DASHBOARD_PATH)

@app.route('/api/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    import requests
    url = f"{API_BASE}/{path}"
    try:
        if request.method == 'GET':
            resp = requests.get(url, params=request.args, timeout=5)
        else:
            resp = requests.post(url, json=request.json, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Cost Optimizer Dashboard running on port 18243")
    app.run(host='0.0.0.0', port=18243, debug=False)