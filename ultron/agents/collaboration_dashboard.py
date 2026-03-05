#!/usr/bin/env python3
"""
Agent协作网络监控面板
实时展示多智能体系统的运行状态、性能指标、工作流状态
"""
import json
import sqlite3
import subprocess
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = Path(__file__).parent.parent

class CollaborationDashboard:
    def __init__(self):
        self.data = {}
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_system_metrics(self):
        """获取系统指标"""
        try:
            load = subprocess.check_output(
                "cat /proc/loadavg | awk '{print $1}'", shell=True
            ).decode().strip()
            
            mem = subprocess.check_output("free -m | grep Mem:", shell=True).decode()
            mem_parts = mem.split()
            mem_used = mem_parts[2]
            mem_total = mem_parts[1]
            mem_pct = round(int(mem_used) / int(mem_total) * 100, 1)
            
            disk = subprocess.check_output(
                "df -h / | tail -1 | awk '{print $5}'", shell=True
            ).decode().strip().replace('%', '')
            
            gateway = subprocess.run(
                ["pgrep", "-f", "openclaw"],
                capture_output=True
            ).returncode == 0
            
            return {
                "load": float(load),
                "memory_used": f"{mem_used}MB",
                "memory_total": f"{mem_total}MB",
                "memory_pct": mem_pct,
                "disk_pct": int(disk),
                "gateway": "在线" if gateway else "离线"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_agent_status(self):
        """获取Agent状态"""
        state_file = BASE_DIR / "agent_lifecycle_state.json"
        if not state_file.exists():
            return {"agents": [], "message": "无状态文件"}
        
        with open(state_file) as f:
            data = json.load(f)
        
        agents = []
        statuses = data.get("statuses", {})
        
        for name, status in statuses.items():
            state = status.get("state", "unknown")
            if state == "running":
                state_display = "🟢 运行中"
            elif state == "failed":
                state_display = "🔴 失败"
            else:
                state_display = "⚪ 停止"
            
            agents.append({
                "name": name,
                "state": state_display,
                "health": status.get("health_score", 0),
                "cpu": status.get("cpu_percent", 0),
                "memory": status.get("memory_mb", 0),
                "restarts": status.get("restart_count", 0),
                "error": (status.get("last_error") or "")[:50]
            })
        
        return {"agents": agents}
    
    def get_workflow_status(self):
        """获取工作流状态"""
        wf_state = Path("/root/.openclaw/workspace/ultron-workflow/state.json")
        if not wf_state.exists():
            return {"workflow": None}
        
        with open(wf_state) as f:
            data = json.load(f)
        
        current = data.get("current", {})
        return {
            "workflow": {
                "incarnation": current.get("incarnation", "?"),
                "ambition": current.get("ambition", ""),
                "task": data.get("next_life", {}).get("task", ""),
                "status": current.get("task_status", "")
            },
            "history": data.get("history", [])[:5]
        }
    
    def get_message_queue_status(self):
        """获取消息队列状态"""
        queue_file = BASE_DIR / "executor_queue.json"
        if not queue_file.exists():
            return {"queue": None}
        
        with open(queue_file) as f:
            data = json.load(f)
        
        # 支持列表格式和字典格式
        if isinstance(data, list):
            pending = [t for t in data if t.get("status") == "pending"]
            processing = [t for t in data if t.get("status") == "running"]
            completed = [t for t in data if t.get("status") == "completed"]
        else:
            pending = data.get("pending", [])
            processing = data.get("processing", [])
            completed = data.get("completed", [])
        
        return {
            "queue": {
                "pending": len(pending),
                "processing": len(processing),
                "completed": len(completed)
            }
        }
    
    def get_performance_metrics(self):
        """获取性能指标"""
        db_file = BASE_DIR / "performance.db"
        if not db_file.exists():
            return {"performance": None}
        
        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()
            
            # 获取最新性能数据
            cursor.execute('''
                SELECT metric_name, value, timestamp 
                FROM performance_metrics 
                ORDER BY timestamp DESC LIMIT 20
            ''')
            metrics = []
            for row in cursor.fetchall():
                metrics.append({
                    "name": row[0],
                    "value": row[1],
                    "time": row[2]
                })
            
            # 获取压力测试结果
            cursor.execute('''
                SELECT test_type, ops_per_sec, avg_latency_ms, timestamp
                FROM stress_test_results
                ORDER BY timestamp DESC LIMIT 5
            ''')
            stress_tests = []
            for row in cursor.fetchall():
                stress_tests.append({
                    "type": row[0],
                    "ops": row[1],
                    "latency": row[2],
                    "time": row[3]
                })
            
            conn.close()
            return {
                "performance": {
                    "metrics": metrics,
                    "stress_tests": stress_tests
                }
            }
        except Exception as e:
            return {"performance": {"error": str(e)}}
    
    def get_service_mesh_status(self):
        """获取服务网格状态"""
        mesh_state = BASE_DIR / "service_mesh_state.json"
        if not mesh_state.exists():
            return {"mesh": None}
        
        with open(mesh_state) as f:
            data = json.load(f)
        return {"mesh": data}
    
    def collect_all(self):
        """收集所有数据"""
        self.data = {
            "system": self.get_system_metrics(),
            "agents": self.get_agent_status(),
            "workflow": self.get_workflow_status(),
            "queue": self.get_message_queue_status(),
            "performance": self.get_performance_metrics(),
            "mesh": self.get_service_mesh_status(),
            "timestamp": self.timestamp
        }
        return self.data
    
    def generate_html(self):
        """生成HTML监控面板"""
        self.collect_all()
        d = self.data
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Agent协作网络监控面板</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #eee; min-height: 100vh; }}
        h1 {{ color: #00d4ff; margin-bottom: 5px; }}
        h2 {{ color: #00d4ff; margin: 15px 0 10px; font-size: 18px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
        .timestamp {{ color: #888; font-size: 14px; }}
        .card {{ background: rgba(22, 33, 62, 0.8); padding: 20px; margin: 10px 0; border-radius: 12px; border: 1px solid #0f3460; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
        .metric {{ background: #0f3460; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #00d4ff; }}
        .metric-label {{ color: #888; font-size: 12px; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #0f3460; }}
        th {{ background: #0f3460; color: #00d4ff; font-weight: 600; }}
        .status-ok {{ color: #00ff88; }}
        .status-warn {{ color: #ffaa00; }}
        .status-error {{ color: #ff4444; }}
        .status-stopped {{ color: #888; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; background: #00d4ff; color: #000; font-weight: bold; }}
        .badge-warn {{ background: #ffaa00; }}
        .badge-error {{ background: #ff4444; }}
        .workflow-info {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .workflow-item {{ background: #0f3460; padding: 12px 16px; border-radius: 8px; }}
        .workflow-label {{ color: #888; font-size: 12px; }}
        .workflow-value {{ color: #00ff88; font-size: 16px; font-weight: bold; margin-top: 4px; }}
        .history-item {{ padding: 8px 0; border-bottom: 1px solid #0f3460; }}
        .history-item:last-child {{ border-bottom: none; }}
        .progress-bar {{ width: 100%; height: 8px; background: #0f3460; border-radius: 4px; overflow: hidden; margin-top: 8px; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); border-radius: 4px; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
        .live {{ animation: pulse 2s infinite; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🤖 Agent协作网络监控面板</h1>
            <p style="color:#888">Multi-Agent Collaboration Network Dashboard</p>
        </div>
        <div class="timestamp">更新时间: {d['timestamp']}</div>
    </div>
    
    <!-- 系统状态 -->
    <div class="card">
        <h2>🖥️ 系统状态</h2>
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{d['system'].get('load', 'N/A')}</div>
                <div class="metric-label">系统负载</div>
            </div>
            <div class="metric">
                <div class="metric-value">{d['system'].get('memory_pct', 'N/A')}%</div>
                <div class="metric-label">内存使用 ({d['system'].get('memory_used', '')})</div>
            </div>
            <div class="metric">
                <div class="metric-value">{d['system'].get('disk_pct', 'N/A')}%</div>
                <div class="metric-label">磁盘使用</div>
            </div>
            <div class="metric">
                <div class="metric-value class="live"">{d['system'].get('gateway', 'N/A')}</div>
                <div class="metric-label">Gateway状态</div>
            </div>
        </div>
    </div>
    
    <!-- Agent状态 -->
    <div class="card">
        <h2>🦞 Agent状态</h2>
        <table>
            <tr>
                <th>Agent名称</th>
                <th>状态</th>
                <th>健康度</th>
                <th>CPU%</th>
                <th>内存MB</th>
                <th>重启</th>
                <th>错误</th>
            </tr>
'''
        
        agents = d.get("agents", {}).get("agents", [])
        if agents:
            for a in agents:
                status_class = "status-ok" if "运行" in a["state"] else "status-error"
                health_color = "#00ff88" if a["health"] > 80 else "#ffaa00" if a["health"] > 50 else "#ff4444"
                html += f'''            <tr>
                <td><span class="badge">{a['name']}</span></td>
                <td class="{status_class}">{a['state']}</td>
                <td><div class="progress-bar"><div class="progress-fill" style="width:{a['health']}%;background:{health_color}"></div></div>{a['health']}%</td>
                <td>{a['cpu']:.1f}%</td>
                <td>{a['memory']:.1f}</td>
                <td>{a['restarts']}</td>
                <td style="color:#888;font-size:12px">{a['error'] or '-'}</td>
            </tr>
'''
        else:
            html += '            <tr><td colspan="7" style="text-align:center;color:#888">暂无Agent数据</td></tr>\n'
        
        html += '''        </table>
    </div>
    
    <!-- 工作流状态 -->
    <div class="card">
        <h2>🔄 工作流状态 (转世系统)</h2>
'''
        
        wf = d.get("workflow", {}).get("workflow")
        if wf:
            html += f'''        <div class="workflow-info">
            <div class="workflow-item">
                <div class="workflow-label">当前世数</div>
                <div class="workflow-value">第{wf.get('incarnation', '?')}世 🔥</div>
            </div>
            <div class="workflow-item">
                <div class="workflow-label">夙愿</div>
                <div class="workflow-value">{wf.get('ambition', 'N/A')}</div>
            </div>
            <div class="workflow-item">
                <div class="workflow-label">当前任务</div>
                <div class="workflow-value" style="font-size:14px">{wf.get('task', 'N/A')[:40]}...</div>
            </div>
            <div class="workflow-item">
                <div class="workflow-label">任务状态</div>
                <div class="workflow-value status-ok">{wf.get('status', 'N/A')}</div>
            </div>
        </div>
'''
        
        history = d.get("workflow", {}).get("history", [])
        if history:
            html += '''        <h3 style="color:#888;margin:15px 0 10px;font-size:14px">📜 历史记录</h3>
'''
            for h in history:
                html += f'''            <div class="history-item">
                <span class="badge">第{h.get('incarnation', '?')}世</span>
                <span style="margin-left:10px">{h.get('task', '')}</span>
                <span style="float:right" class="status-ok">{h.get('status', '')}</span>
            </div>
'''
        
        html += '''    </div>
    
    <!-- 消息队列 -->
    <div class="card">
        <h2>📬 消息队列</h2>
'''
        
        queue = d.get("queue", {}).get("queue")
        if queue:
            html += f'''        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{queue.get('pending', 0)}</div>
                <div class="metric-label">待处理</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color:#ffaa00">{queue.get('processing', 0)}</div>
                <div class="metric-label">处理中</div>
            </div>
            <div class="metric">
                <div class="metric-value status-ok">{queue.get('completed', 0)}</div>
                <div class="metric-label">已完成</div>
            </div>
        </div>
'''
        else:
            html += '        <p style="color:#888">暂无队列数据</p>\n'
        
        html += '''    </div>
    
    <!-- 性能指标 -->
    <div class="card">
        <h2>📊 性能指标</h2>
'''
        
        perf = d.get("performance", {}).get("performance")
        if perf and perf.get("stress_tests"):
            html += '''        <table>
            <tr>
                <th>测试类型</th>
                <th>吞吐量</th>
                <th>延迟</th>
                <th>时间</th>
            </tr>
'''
            for s in perf["stress_tests"]:
                html += f'''            <tr>
                <td><span class="badge">{s['type']}</span></td>
                <td>{s['ops']} ops/s</td>
                <td>{s['latency']:.2f}ms</td>
                <td style="color:#888">{s['time'][:19]}</td>
            </tr>
'''
            html += '''        </table>
'''
        else:
            html += '        <p style="color:#888">暂无性能测试数据 (运行 stress_test_cli.py 生成)</p>\n'
        
        html += '''    </div>
    
    <script>
        // 每30秒自动刷新
        setInterval(() => location.reload(), 30000);
        
        // 显示倒计时
        let countdown = 30;
        setInterval(() => {
            countdown--;
            if (countdown <= 0) countdown = 30;
        }, 1000);
    </script>
</body>
</html>'''
        
        return html
    
    def save(self, filename="collaboration_dashboard.html"):
        """保存HTML文件"""
        html = self.generate_html()
        output_path = OUTPUT_DIR / filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ 监控面板已生成: {output_path}")
        return output_path

if __name__ == "__main__":
    dashboard = CollaborationDashboard()
    dashboard.save()