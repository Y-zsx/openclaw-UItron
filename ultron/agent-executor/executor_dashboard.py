<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent执行器监控面板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eee;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 20px;
        }
        .header h1 { 
            font-size: 2rem; 
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .stat-card h3 { color: #888; font-size: 0.9rem; margin-bottom: 8px; }
        .stat-card .value { font-size: 2rem; font-weight: bold; }
        .stat-card.total .value { color: #00d4ff; }
        .stat-card.completed .value { color: #00ff88; }
        .stat-card.failed .value { color: #ff4757; }
        .stat-card.cache .value { color: #ffa502; }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .panel {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
        }
        .panel h2 { 
            font-size: 1.2rem; 
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .agent-list { max-height: 300px; overflow-y: auto; }
        .agent-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
        }
        .agent-info { display: flex; align-items: center; gap: 10px; }
        .agent-status {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .agent-status.idle { background: #00ff88; }
        .agent-status.busy { background: #ffa502; }
        .agent-caps { font-size: 0.8rem; color: #888; }
        
        .task-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }
        .task-stat {
            text-align: center;
            padding: 15px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
        }
        .task-stat .num { font-size: 1.5rem; font-weight: bold; }
        .task-stat .label { font-size: 0.8rem; color: #888; }
        
        .queue-info {
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }
        .queue-item {
            flex: 1;
            text-align: center;
            padding: 10px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
        }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: #888; font-weight: normal; font-size: 0.9rem; }
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
        }
        .status-badge.completed { background: rgba(0,255,136,0.2); color: #00ff88; }
        .status-badge.pending { background: rgba(255,165,2,0.2); color: #ffa502; }
        .status-badge.running { background: rgba(0,212,255,0.2); color: #00d4ff; }
        .status-badge.failed { background: rgba(255,71,87,0.2); color: #ff4757; }
        
        .charts-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .chart-container { height: 200px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Agent执行器监控面板</h1>
        <p>端口: <span id="port">-</span> | 运行时间: <span id="uptime">-</span></p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card total">
            <h3>总任务数</h3>
            <div class="value" id="totalTasks">-</div>
        </div>
        <div class="stat-card completed">
            <h3>已完成</h3>
            <div class="value" id="completedTasks">-</div>
        </div>
        <div class="stat-card failed">
            <h3>失败</h3>
            <div class="value" id="failedTasks">-</div>
        </div>
        <div class="stat-card cache">
            <h3>缓存命中率</h3>
            <div class="value" id="cacheHitRate">-</div>
        </div>
    </div>
    
    <div class="main-grid">
        <div class="panel">
            <h2>👥 Agent状态</h2>
            <div class="agent-list" id="agentList"></div>
        </div>
        <div class="panel">
            <h2>📊 任务统计</h2>
            <div class="task-stats">
                <div class="task-stat">
                    <div class="num" id="pendingTasks">-</div>
                    <div class="label">等待中</div>
                </div>
                <div class="task-stat">
                    <div class="num" id="runningTasks">-</div>
                    <div class="label">执行中</div>
                </div>
                <div class="task-stat">
                    <div class="num" id="waitingDeps">-</div>
                    <div class="label">等待依赖</div>
                </div>
            </div>
            <div class="queue-info" id="queueInfo"></div>
        </div>
    </div>
    
    <div class="panel">
        <h2>📝 最近任务</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>类型</th>
                    <th>优先级</th>
                    <th>Agent</th>
                    <th>状态</th>
                    <th>耗时</th>
                </tr>
            </thead>
            <tbody id="taskList"></tbody>
        </table>
    </div>

    <script>
        let statusData = null;
        
        async function fetchStatus() {
            try {
                const res = await fetch('/status');
                statusData = await res.json();
                updateUI();
            } catch(e) {
                console.error('Failed to fetch status:', e);
            }
        }
        
        function updateUI() {
            if (!statusData) return;
            
            document.getElementById('port').textContent = statusData.port;
            document.getElementById('uptime').textContent = formatUptime(statusData.uptime);
            
            document.getElementById('totalTasks').textContent = statusData.stats.total_tasks;
            document.getElementById('completedTasks').textContent = statusData.stats.completed_tasks;
            document.getElementById('failedTasks').textContent = statusData.stats.failed_tasks;
            document.getElementById('cacheHitRate').textContent = (statusData.cache.hit_rate * 100).toFixed(1) + '%';
            
            // Agent列表
            const agentList = document.getElementById('agentList');
            agentList.innerHTML = Object.values(statusData.agents).map(a => `
                <div class="agent-item">
                    <div class="agent-info">
                        <div class="agent-status ${a.status}"></div>
                        <div>
                            <div>${a.name}</div>
                            <div class="agent-caps">${a.capabilities.join(', ')}</div>
                        </div>
                    </div>
                    <div>${a.tasks_completed} 任务</div>
                </div>
            `).join('');
            
            // 任务统计
            document.getElementById('pendingTasks').textContent = statusData.tasks.pending;
            document.getElementById('runningTasks').textContent = statusData.tasks.running;
            document.getElementById('waitingDeps').textContent = statusData.tasks.waiting_deps;
            
            // 队列信息
            const queueInfo = document.getElementById('queueInfo');
            queueInfo.innerHTML = Object.entries(statusData.queues).map(([name, count]) => `
                <div class="queue-item">
                    <div class="num">${count}</div>
                    <div class="label">${name}</div>
                </div>
            `).join('');
        }
        
        function formatUptime(seconds) {
            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            const s = Math.floor(seconds % 60);
            return `${h}h ${m}m ${s}s`;
        }
        
        fetchStatus();
        setInterval(fetchStatus, 3000);
    </script>
</body>
</html>