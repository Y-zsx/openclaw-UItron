#!/usr/bin/env python3
"""
决策引擎 Web 仪表盘
Decision Engine Web Dashboard
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, render_template_string
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>决策引擎仪表盘</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eee;
        }
        .header {
            background: linear-gradient(90deg, #0f3460, #e94560);
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .header h1 { font-size: 1.8rem; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 {
            color: #e94560;
            margin-bottom: 15px;
            font-size: 1.2rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .stat-value { font-size: 2.5rem; font-weight: bold; color: #4ecca3; }
        .stat-label { color: #aaa; font-size: 0.9rem; }
        .btn {
            background: linear-gradient(90deg, #e94560, #0f3460);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1rem;
            margin: 5px;
            transition: transform 0.2s;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #aaa; }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            border-radius: 6px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(255,255,255,0.05);
            color: #eee;
        }
        .log {
            background: #0d0d0d;
            border-radius: 6px;
            padding: 10px;
            max-height: 200px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.85rem;
        }
        .log-entry { margin: 5px 0; padding: 5px; border-left: 3px solid #e94560; }
        .risk-low { color: #4ecca3; }
        .risk-medium { color: #f39c12; }
        .risk-high { color: #e94560; }
        .risk-critical { color: #ff0000; }
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #e94560;
            color: white;
            border: none;
            padding: 15px 25px;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(233,69,96,0.4);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 决策引擎仪表盘</h1>
    </div>
    
    <div class="container">
        <!-- 快速操作 -->
        <div class="card">
            <h2>🚀 快速操作</h2>
            <div class="btn-group">
                <button class="btn" onclick="makeDecision()">发起决策</button>
                <button class="btn" onclick="assessRisk()">风险评估</button>
                <button class="btn" onclick="refreshAll()">🔄 刷新全部</button>
            </div>
        </div>
        
        <div class="grid">
            <!-- 统计卡片 -->
            <div class="card">
                <h2>📊 决策统计</h2>
                <div id="stats">
                    <div class="stat-value" id="total-decisions">-</div>
                    <div class="stat-label">总决策数</div>
                </div>
            </div>
            
            <div class="card">
                <h2>✅ 成功率</h2>
                <div>
                    <div class="stat-value" id="success-rate">-</div>
                    <div class="stat-label">成功率</div>
                </div>
            </div>
            
            <div class="card">
                <h2>⚠️ 风险等级</h2>
                <div>
                    <div class="stat-value" id="risk-level">-</div>
                    <div class="stat-label">当前风险</div>
                </div>
            </div>
            
            <div class="card">
                <h2>📋 规则数量</h2>
                <div>
                    <div class="stat-value" id="rule-count">-</div>
                    <div class="stat-label">活跃规则</div>
                </div>
            </div>
        </div>
        
        <div class="grid">
            <!-- 风险评估 -->
            <div class="card">
                <h2>🎯 快速风险评估</h2>
                <div class="form-group">
                    <label>CPU (%)</label>
                    <input type="number" id="risk-cpu" value="45" min="0" max="100">
                </div>
                <div class="form-group">
                    <label>内存 (%)</label>
                    <input type="number" id="risk-memory" value="60" min="0" max="100">
                </div>
                <div class="form-group">
                    <label>磁盘 (%)</label>
                    <input type="number" id="risk-disk" value="50" min="0" max="100">
                </div>
                <div class="form-group">
                    <label>错误率 (%)</label>
                    <input type="number" id="risk-error" value="2" min="0" max="100">
                </div>
                <button class="btn" onclick="runRiskAssessment()">运行评估</button>
                <div id="risk-result" style="margin-top: 15px;"></div>
            </div>
            
            <!-- 决策日志 -->
            <div class="card">
                <h2>📜 决策日志</h2>
                <div class="log" id="decision-log">
                    <div class="log-entry">等待数据...</div>
                </div>
            </div>
            
            <!-- 活跃规则 -->
            <div class="card">
                <h2>📖 活跃规则</h2>
                <div class="log" id="rules-list">
                    <div class="log-entry">加载中...</div>
                </div>
            </div>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="refreshAll()">🔄</button>
    
    <script>
        const API_BASE = '';
        
        async function refreshAll() {
            await Promise.all([refreshStats(), refreshRules(), refreshDecisions()]);
        }
        
        async function refreshStats() {
            try {
                const resp = await fetch(API_BASE + '/stats');
                const data = await resp.json();
                const stats = data.decision_engine || {};
                document.getElementById('total-decisions').textContent = stats.total_decisions || 0;
                document.getElementById('success-rate').textContent = ((stats.success_rate || 0) * 100).toFixed(1) + '%';
                document.getElementById('rule-count').textContent = data.rule_engine?.active_rules || 0;
            } catch(e) {
                console.error('Stats error:', e);
            }
        }
        
        async function refreshRules() {
            try {
                const resp = await fetch(API_BASE + '/rules');
                const data = await resp.json();
                const rules = data.rules || [];
                document.getElementById('rules-list').innerHTML = rules.slice(0, 10).map(r => 
                    '<div class="log-entry"><strong>' + r.name + '</strong>: ' + r.action + '</div>'
                ).join('') || '<div class="log-entry">无规则</div>';
            } catch(e) {
                document.getElementById('rules-list').innerHTML = '<div class="log-entry">加载失败</div>';
            }
        }
        
        async function refreshDecisions() {
            try {
                const resp = await fetch(API_BASE + '/decisions/recent?limit=10');
                if (resp.ok) {
                    const data = await resp.json();
                    const decisions = data.decisions || [];
                    document.getElementById('decision-log').innerHTML = decisions.map(d => 
                        '<div class="log-entry"><strong>' + d.action + '</strong> - ' + d.status + '</div>'
                    ).join('') || '<div class="log-entry">无决策记录</div>';
                }
            } catch(e) {
                document.getElementById('decision-log').innerHTML = '<div class="log-entry">加载失败</div>';
            }
        }
        
        async function makeDecision() {
            const context = {
                trigger: 'dashboard',
                source: 'web-ui',
                context: { type: 'manual', details: '从仪表盘发起' }
            };
            
            try {
                const resp = await fetch(API_BASE + '/decide', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(context)
                });
                const data = await resp.json();
                alert('决策: ' + (data.decision?.action || '无') + '\\n状态: ' + (data.decision?.status || '未知'));
                refreshAll();
            } catch(e) {
                alert('决策失败: ' + e);
            }
        }
        
        async function assessRisk() {
            const cpu = document.getElementById('risk-cpu').value;
            const memory = document.getElementById('risk-memory').value;
            const disk = document.getElementById('risk-disk').value;
            const error = document.getElementById('risk-error').value;
            
            await runRiskAssessmentWithValues(cpu, memory, disk, error);
        }
        
        async function runRiskAssessmentWithValues(cpu, memory, disk, error) {
            const metrics = { cpu: parseFloat(cpu), memory: parseFloat(memory), disk: parseFloat(disk), error_rate: parseFloat(error) };
            
            try {
                const resp = await fetch(API_BASE + '/risk', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ metrics })
                });
                const data = await resp.json();
                const risk = data.risk_assessment;
                const el = document.getElementById('risk-result');
                el.innerHTML = '<strong>风险等级: </strong><span class="risk-' + risk.overall_level + '">' + 
                    risk.overall_level.toUpperCase() + '</span><br>' +
                    '<strong>风险分数: </strong>' + risk.risk_score + '<br>' +
                    '<strong>风险项: </strong>' + risk.risks.length;
                    
                document.getElementById('risk-level').textContent = risk.overall_level.toUpperCase();
                document.getElementById('risk-level').className = 'stat-value risk-' + risk.overall_level;
            } catch(e) {
                alert('评估失败: ' + e);
            }
        }
        
        function runRiskAssessment() { assessRisk(); }
        
        // 自动刷新
        refreshAll();
        setInterval(refreshAll, 30000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """主页面"""
    return render_template_string(DASHBOARD_HTML)


if __name__ == '__main__':
    print("启动决策引擎仪表盘: http://localhost:18121")
    app.run(host='0.0.0.0', port=18121, debug=True)