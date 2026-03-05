#!/usr/bin/env python3
"""运维仪表板V2 - 智能运维助手系统"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

ULTRON_DIR = Path("/root/.openclaw/workspace/ultron")
DATA_DIR = ULTRON_DIR / "data"
OUTPUT_FILE = ULTRON_DIR / "ops-dashboard-v2.html"


def get_system_metrics():
    metrics = {}
    try:
        result = subprocess.run(["sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"], capture_output=True, text=True, timeout=5)
        metrics['cpu_percent'] = float(result.stdout.strip()) if result.stdout.strip() else 0
    except: metrics['cpu_percent'] = 0
    try:
        result = subprocess.run(["sh", "-c", "free -m | grep Mem"], capture_output=True, text=True, timeout=5)
        if result.stdout:
            parts = result.stdout.split()
            metrics['mem_total'] = int(parts[1])
            metrics['mem_used'] = int(parts[2])
            metrics['mem_percent'] = round(metrics['mem_used'] / metrics['mem_total'] * 100, 1)
    except: pass
    try:
        result = subprocess.run(["sh", "-c", "df -h / | tail -1 | awk '{print $2,$3,$4,$5}'"], capture_output=True, text=True, timeout=5)
        if result.stdout:
            parts = result.stdout.split()
            metrics['disk_total'], metrics['disk_used'], metrics['disk_available'], metrics['disk_percent'] = parts[0], parts[1], parts[2], parts[3].replace('%', '')
    except: pass
    try:
        result = subprocess.run(["sh", "-c", "uptime | awk -F'load average:' '{print $2}'"], capture_output=True, text=True, timeout=5)
        metrics['load_avg'] = result.stdout.strip() or "N/A"
    except: pass
    try:
        result = subprocess.run(["sh", "-c", "ps aux | wc -l"], capture_output=True, text=True, timeout=5)
        metrics['process_count'] = int(result.stdout.strip()) if result.stdout.strip() else 0
    except: pass
    try:
        result = subprocess.run(["sh", "-c", "netstat -an 2>/dev/null | wc -l || ss -tun 2>/dev/null | wc -l"], capture_output=True, text=True, timeout=5)
        metrics['network_conn'] = int(result.stdout.strip()) if result.stdout.strip() else 0
    except: pass
    try:
        result = subprocess.run(["uptime -s"], capture_output=True, text=True, timeout=5)
        metrics['boot_time'] = result.stdout.strip() or "N/A"
    except: pass
    return metrics


def get_alert_stats():
    alert_file = DATA_DIR / "alert_repair_log.json"
    if alert_file.exists():
        try:
            with open(alert_file) as f:
                data = json.load(f)
                alerts = data.get('alerts', [])
                return {'total': len(alerts), 'critical': len([a for a in alerts if a.get('level') == 'CRITICAL']), 'warning': len([a for a in alerts if a.get('level') == 'WARNING']), 'recent': alerts[-5:]}
        except: pass
    return {'total': 0, 'critical': 0, 'warning': 0, 'recent': []}


def get_repair_stats():
    repair_file = DATA_DIR / "repair_history.json"
    if repair_file.exists():
        try:
            with open(repair_file) as f:
                data = json.load(f)
                repairs = data.get('repairs', [])
                return {'total': len(repairs), 'success': len([r for r in repairs if r.get('status') == 'success']), 'failed': len([r for r in repairs if r.get('status') == 'failed']), 'recent': repairs[-5:]}
        except: pass
    return {'total': 0, 'success': 0, 'failed': 0, 'recent': []}


def get_gateway_status():
    try:
        result = subprocess.run(["openclaw", "status", "--short"], capture_output=True, text=True, timeout=10)
        output = result.stdout
        status = "online" if "running" in output.lower() or "online" in output.lower() else "offline"
        return {'status': status, 'output': output[:500]}
    except: return {'status': 'unknown', 'output': 'failed'}


def get_cron_jobs():
    try:
        result = subprocess.run(["openclaw", "cron", "list", "--format", "json"], capture_output=True, text=True, timeout=10)
        if result.stdout.strip(): return json.loads(result.stdout)
    except: pass
    return []


def generate_dashboard():
    metrics = get_system_metrics()
    alerts = get_alert_stats()
    repairs = get_repair_stats()
    gateway = get_gateway_status()
    crons = get_cron_jobs()
    
    cpu = metrics.get('cpu_percent', 0)
    mem = metrics.get('mem_percent', 0)
    disk = int(metrics.get('disk_percent', 0))
    
    cpu_color = '#22c55e' if cpu < 50 else '#f59e0b' if cpu < 80 else '#ef4444'
    mem_color = '#22c55e' if mem < 50 else '#f59e0b' if mem < 80 else '#ef4444'
    disk_color = '#22c55e' if disk < 50 else '#f59e0b' if disk < 80 else '#ef4444'
    
    health_score = 100
    if cpu > 80: health_score -= 20
    if mem > 80: health_score -= 20
    if disk > 80: health_score -= 20
    if alerts.get('critical', 0) > 0: health_score -= 15
    if repairs.get('failed', 0) > 0: health_score -= 10
    if gateway.get('status') != 'online': health_score -= 25
    health_score = max(0, health_score)
    health_color = '#22c55e' if health_score >= 80 else '#f59e0b' if health_score >= 50 else '#ef4444'
    
    cron_html = ""
    if crons:
        cron_items = "".join([f'<div class="cron-item"><span class="cron-name">{c.get("name", "Unknown")}</span><span class="cron-interval">{c.get("schedule", "N/A")}</span></div>' for c in crons[:10]])
        cron_html = f'<div class="section"><div class="section-title">TIMER定时任务 ({len(crons)})</div><div class="cron-list">{cron_items}</div></div>'
    
    alert_items = "".join([f'<div class="alert-item {a.get("level", "info").lower()}"><div class="alert-icon">{"🔴" if a.get("level") == "CRITICAL" else "🟡" if a.get("level") == "WARNING" else "🔵"}</div><div class="alert-content"><div class="alert-title">{a.get("message", "Unknown")[:50]}</div><div class="alert-time">{a.get("timestamp", "N/A")}</div></div></div>' for a in alerts.get('recent', [])])
    
    repair_items = "".join([f'<div class="alert-item {r.get("status", "info")}"><div class="alert-icon">{"✅" if r.get("status") == "success" else "❌"}</div><div class="alert-content"><div class="alert-title">{r.get("action", "Unknown")[:50]}</div><div class="alert-time">{r.get("timestamp", "N/A")}</div></div></div>' for r in repairs.get('recent', [])])
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>奥创智能运维仪表板 V2</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%); min-height: 100vh; color: #fff; padding: 20px; }}
.header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; padding: 20px 30px; background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 16px; border: 1px solid rgba(255,255,255,0.2); }}
.logo {{ font-size: 28px; font-weight: bold; }}
.logo span {{ color: #ff6b6b; }}
.header-right {{ display: flex; align-items: center; gap: 15px; }}
.status-badge {{ padding: 8px 20px; border-radius: 20px; font-weight: bold; background: linear-gradient(90deg, {health_color}, {health_color}dd); box-shadow: 0 4px 15px {health_color}66; }}
.time-display {{ color: rgba(255,255,255,0.8); font-size: 14px; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 25px; }}
@media (max-width: 1200px) {{ .grid {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 768px) {{ body {{ padding: 10px; }} .header {{ flex-direction: column; gap: 15px; padding: 15px; text-align: center; }} .logo {{ font-size: 20px; }} .grid {{ grid-template-columns: 1fr; gap: 15px; }} }}
.stat-card {{ background: rgba(255,255,255,0.08); backdrop-filter: blur(10px); border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); text-align: center; transition: transform 0.3s; }}
.stat-card:hover {{ transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }}
.stat-icon {{ font-size: 32px; margin-bottom: 10px; }}
.stat-value {{ font-size: 36px; font-weight: bold; background: linear-gradient(90deg, #00d2ff, #3a7bd5); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
.stat-label {{ color: rgba(255,255,255,0.6); font-size: 14px; margin-top: 5px; }}
.section {{ background: rgba(255,255,255,0.08); backdrop-filter: blur(10px); border-radius: 16px; padding: 25px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.1); }}
.section-title {{ font-size: 20px; font-weight: bold; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }}
.section-title span {{ color: #00d2ff; }}
.chart-container {{ height: 250px; position: relative; }}
.info-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }}
@media (max-width: 768px) {{ .info-grid {{ grid-template-columns: 1fr; }} }}
.info-card {{ background: rgba(255,255,255,0.05); border-radius: 12px; padding: 15px; }}
.info-label {{ color: rgba(255,255,255,0.5); font-size: 12px; margin-bottom: 5px; }}
.info-value {{ font-size: 16px; font-weight: 500; }}
.alert-list {{ max-height: 300px; overflow-y: auto; }}
.alert-item {{ display: flex; align-items: center; gap: 12px; padding: 12px; margin-bottom: 10px; background: rgba(255,255,255,0.05); border-radius: 10px; border-left: 4px solid; }}
.alert-item.critical {{ border-color: #ef4444; }}
.alert-item.warning {{ border-color: #f59e0b; }}
.alert-item.info {{ border-color: #3b82f6; }}
.alert-item.success {{ border-color: #22c55e; }}
.alert-item.failed {{ border-color: #ef4444; }}
.alert-icon {{ font-size: 20px; }}
.alert-content {{ flex: 1; }}
.alert-title {{ font-weight: 500; margin-bottom: 3px; }}
.alert-time {{ color: rgba(255,255,255,0.5); font-size: 12px; }}
.health-bar {{ height: 10px; background: rgba(255,255,255,0.1); border-radius: 5px; overflow: hidden; margin-top: 10px; }}
.health-fill {{ height: 100%; border-radius: 5px; transition: width 0.5s ease; }}
.refresh-btn {{ background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: #fff; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 14px; }}
.refresh-btn:hover {{ background: rgba(255,255,255,0.2); }}
.progress-ring {{ width: 120px; height: 120px; position: relative; margin: 0 auto; }}
.progress-ring svg {{ transform: rotate(-90deg); }}
.progress-ring circle {{ fill: none; stroke-width: 8; }}
.progress-ring .bg {{ stroke: rgba(255,255,255,0.1); }}
.progress-ring .progress {{ stroke: {health_color}; stroke-linecap: round; stroke-dasharray: 314; stroke-dashoffset: {314 - int(314 * health_score / 100)}; transition: stroke-dashoffset 0.5s ease; }}
.progress-value {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 28px; font-weight: bold; }}
.cron-list {{ max-height: 200px; overflow-y: auto; }}
.cron-item {{ display: flex; justify-content: space-between; align-items: center; padding: 10px; margin-bottom: 8px; background: rgba(255,255,255,0.05); border-radius: 8px; }}
.cron-name {{ font-weight: 500; }}
.cron-interval {{ color: rgba(255,255,255,0.5); font-size: 12px; }}
.status-indicator {{ display: inline-flex; align-items: center; gap: 6px; }}
.status-dot {{ width: 8px; height: 8px; border-radius: 50%; background: {health_color}; box-shadow: 0 0 10px {health_color}; }}
</style>
</head>
<body>
<div class="header">
<div class="logo">LOBSTER <span>奥创</span> 智能运维仪表板</div>
<div class="header-right">
<div class="status-badge"><span class="status-indicator"><span class="status-dot"></span>健康度 {health_score}%</span></div>
<button class="refresh-btn" onclick="location.reload()">REFRESH刷新</button>
<div class="time-display" id="time"></div>
</div>
</div>

<div class="grid">
<div class="stat-card">
<div class="progress-ring">
<svg width="120" height="120"><circle class="bg" cx="60" cy="60" r="50"/><circle class="progress" cx="60" cy="60" r="50"/></svg>
<div class="progress-value">{health_score}%</div>
</div>
<div class="stat-label">系统健康度</div>
</div>

<div class="stat-card">
<div class="stat-icon">SERVER</div>
<div class="stat-value" style="color: {cpu_color}">{cpu:.1f}%</div>
<div class="stat-label">CPU 使用率</div>
<div class="health-bar"><div class="health-fill" style="width: {min(cpu, 100)}%; background: {cpu_color}"></div></div>
</div>

<div class="stat-card">
<div class="stat-icon">MEM</div>
<div class="stat-value" style="color: {mem_color}">{mem:.1f}%</div>
<div class="stat-label">内存 ({metrics.get('mem_used', 0)}/{metrics.get('mem_total', 0)}MB)</div>
<div class="health-bar"><div class="health-fill" style="width: {min(mem, 100)}%; background: {mem_color}"></div></div>
</div>

<div class="stat-card">
<div class="stat-icon">DISK</div>
<div class="stat-value" style="color: {disk_color}">{disk}%</div>
<div class="stat-label">磁盘 ({metrics.get('disk_used', 'N/A')}/{metrics.get('disk_total', 'N/A')})</div>
<div class="health-bar"><div class="health-fill" style="width: {min(disk, 100)}%; background: {disk_color}"></div></div>
</div>
</div>

<div class="section">
<div class="section-title">INFO <span>系统信息</span></div>
<div class="info-grid">
<div class="info-card"><div class="info-label">运行时间</div><div class="info-value">{metrics.get('boot_time', 'N/A')}</div></div>
<div class="info-card"><div class="info-label">系统负载</div><div class="info-value">{metrics.get('load_avg', 'N/A')}</div></div>
<div class="info-card"><div class="info-label">进程数</div><div class="info-value">{metrics.get('process_count', 0)}</div></div>
<div class="info-card"><div class="info-label">网络连接</div><div class="info-value">{metrics.get('network_conn', 0)}</div></div>
<div class="info-card"><div class="info-label">Gateway</div><div class="info-value">{'GREEN 在线' if gateway.get('status') == 'online' else 'RED 离线'}</div></div>
<div class="info-card"><div class="info-label">定时任务</div><div class="info-value">{len(crons)} 个活跃</div></div>
</div>
</div>

<div class="grid">
<div class="section">
<div class="section-title">ALERT <span>告警统计</span></div>
<div class="alert-list">
<div style="display: flex; gap: 20px; margin-bottom: 15px;">
<div style="text-align: center; flex: 1;"><div style="font-size: 28px; font-weight: bold; color: #ef4444;">{alerts.get('critical', 0)}</div><div style="color: rgba(255,255,255,0.6); font-size: 12px;">严重</div></div>
<div style="text-align: center; flex: 1;"><div style="font-size: 28px; font-weight: bold; color: #f59e0b;">{alerts.get('warning', 0)}</div><div style="color: rgba(255,255,255,0.6); font-size: 12px;">警告</div></div>
<div style="text-align: center; flex: 1;"><div style="font-size: 28px; font-weight: bold; color: #3b82f6;">{alerts.get('total', 0)}</div><div style="color: rgba(255,255,255,0.6); font-size: 12px;">总计</div></div>
</div>
{alert_items}
</div>
</div>

<div class="section">
<div class="section-title">FIX <span>修复统计</span></div>
<div class="alert-list">
<div style="display: flex; gap: 20px; margin-bottom: 15px;">
<div style="text-align: center; flex: 1;"><div style="font-size: 28px; font-weight: bold; color: #22c55e;">{repairs.get('success', 0)}</div><div style="color: rgba(255,255,255,0.6); font-size: 12px;">成功</div></div>
<div style="text-align: center; flex: 1;"><div style="font-size: 28px; font-weight: bold; color: #ef4444;">{repairs.get('failed', 0)}</div><div style="color: rgba(255,255,255,0.6); font-size: 12px;">失败</div></div>
<div style="text-align: center; flex: 1;"><div style="font-size: 28px; font-weight: bold; color: #3b82f6;">{repairs.get('total', 0)}</div><div style="color: rgba(255,255,255,0.6); font-size: 12px;">总计</div></div>
</div>
{repair_items}
</div>
</div>
</div>

{cron_html}

<script>
function updateTime() {{ const now = new Date(); document.getElementById('time').textContent = now.toLocaleString('zh-CN'); }}
updateTime();
setInterval(updateTime, 1000);
setTimeout(() => location.reload(), 30000);
</script>
</body>
</html>"""
    
    # 修复emoji
    html = html.replace("SERVER", "🖥️").replace("MEM", "💾").replace("DISK", "💿")
    html = html.replace("GREEN", "🟢").replace("RED", "🔴")
    html = html.replace("ALERT", "🚨").replace("FIX", "🔧").replace("INFO", "📊")
    html = html.replace("REFRESH", "🔄").replace("TIMER", "⏰")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"DONE: {OUTPUT_FILE}")
    return {'health': health_score, 'metrics': metrics, 'alerts': alerts, 'repairs': repairs, 'gateway': gateway}


if __name__ == '__main__':
    result = generate_dashboard()
    print(f"Health: {result['health']}% | CPU: {result['metrics'].get('cpu_percent', 0):.1f}% | Mem: {result['metrics'].get('mem_percent', 0):.1f}% | Disk: {result['metrics'].get('disk_percent', 0)}% | Alerts: {result['alerts'].get('total', 0)} | Repairs: {result['repairs'].get('total', 0)} | Gateway: {result['gateway'].get('status')}")