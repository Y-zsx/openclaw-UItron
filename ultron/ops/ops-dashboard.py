#!/usr/bin/env python3
"""
运维仪表板 - 智能运维助手系统
实时展示系统健康状态、告警信息、修复记录
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

ULTRON_DIR = Path("/root/.openclaw/workspace/ultron")
DATA_DIR = ULTRON_DIR / "data"
OUTPUT_FILE = ULTRON_DIR / "ops-dashboard.html"


def get_system_metrics():
    """采集系统指标"""
    metrics = {}
    
    # CPU使用率
    try:
        result = subprocess.run(
            ["sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"],
            capture_output=True, text=True, timeout=5
        )
        metrics['cpu_percent'] = float(result.stdout.strip()) if result.stdout.strip() else 0
    except:
        metrics['cpu_percent'] = 0
    
    # 内存使用
    try:
        result = subprocess.run(
            ["sh", "-c", "free | grep Mem"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout:
            parts = result.stdout.split()
            total = int(parts[1])
            used = int(parts[2])
            metrics['mem_total'] = total
            metrics['mem_used'] = used
            metrics['mem_percent'] = round(used / total * 100, 1)
    except:
        metrics['mem_percent'] = 0
    
    # 磁盘使用
    try:
        result = subprocess.run(
            ["sh", "-c", "df -h / | tail -1 | awk '{print $2,$3,$4,$5}'"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout:
            parts = result.stdout.split()
            metrics['disk_total'] = parts[0]
            metrics['disk_used'] = parts[1]
            metrics['disk_available'] = parts[2]
            metrics['disk_percent'] = parts[3].replace('%', '')
    except:
        pass
    
    # 系统负载
    try:
        result = subprocess.run(
            ["sh", "-c", "uptime | awk -F'load average:' '{print $2}'"],
            capture_output=True, text=True, timeout=5
        )
        metrics['load_avg'] = result.stdout.strip() if result.stdout.strip() else "N/A"
    except:
        metrics['load_avg'] = "N/A"
    
    # 进程数
    try:
        result = subprocess.run(
            ["sh", "-c", "ps aux | wc -l"],
            capture_output=True, text=True, timeout=5
        )
        metrics['process_count'] = int(result.stdout.strip()) if result.stdout.strip() else 0
    except:
        metrics['process_count'] = 0
    
    # 网络连接数
    try:
        result = subprocess.run(
            ["sh", "-c", "netstat -an 2>/dev/null | wc -l"],
            capture_output=True, text=True, timeout=5
        )
        metrics['net_connections'] = int(result.stdout.strip()) if result.stdout.strip() else 0
    except:
        metrics['net_connections'] = 0
    
    return metrics


def get_alert_summary():
    """获取告警摘要"""
    # 检查两个位置: data/alerts.json 和 alerts/alerts.json
    alert_file = DATA_DIR / "alerts.json"
    if not alert_file.exists():
        alert_file = ULTRON_DIR / "alerts" / "alerts.json"
    if alert_file.exists():
        try:
            with open(alert_file) as f:
                alerts = json.load(f)
                # 支持大小写
                return {
                    "total": len(alerts),
                    "critical": len([a for a in alerts if 'critical' in str(a.get('level', '')).lower()]),
                    "warning": len([a for a in alerts if 'warning' in str(a.get('level', '')).lower()]),
                    "info": len([a for a in alerts if 'info' in str(a.get('level', '')).lower()])
                }
        except:
            pass
    return {"total": 0, "critical": 0, "warning": 0, "info": 0}


def get_repair_history():
    """获取修复历史"""
    repair_file = DATA_DIR / "repair_history.json"
    if repair_file.exists():
        try:
            with open(repair_file) as f:
                repairs = json.load(f)
                # 返回最近10条
                return repairs[-10:] if len(repairs) > 10 else repairs
        except:
            pass
    return []


def get_gateway_status():
    """获取OpenClaw Gateway状态"""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--short"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout if result.stdout else "Unknown"
    except:
        return "Not Running"


def generate_dashboard():
    """生成运维仪表板"""
    metrics = get_system_metrics()
    alerts = get_alert_summary()
    repairs = get_repair_history()
    gateway_status = get_gateway_status()
    
    # 确定健康状态
    health = "healthy"
    health_color = "#22c55e"
    if metrics.get('cpu_percent', 0) > 80 or metrics.get('mem_percent', 0) > 85:
        health = "warning"
        health_color = "#f59e0b"
    if metrics.get('cpu_percent', 0) > 95 or metrics.get('mem_percent', 0) > 95:
        health = "critical"
        health_color = "#ef4444"
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>奥创运维仪表板</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .logo {{ font-size: 28px; font-weight: bold; }}
        .logo span {{ color: #ef4444; }}
        .status-badge {{
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            background: {health_color};
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 24px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .card-title {{
            font-size: 14px;
            color: rgba(255,255,255,0.6);
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-label {{ color: rgba(255,255,255,0.7); }}
        .metric-value {{ 
            font-size: 20px; 
            font-weight: bold;
            color: {health_color};
        }}
        .progress-bar {{
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            margin-top: 8px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }}
        .progress-cpu {{ background: linear-gradient(90deg, #22c55e, #f59e0b, #ef4444); }}
        .progress-mem {{ background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ef4444); }}
        .progress-disk {{
            background: linear-gradient(90deg, #22c55e, #f59e0b);
            width: {metrics.get('disk_percent', '0')};
        }}
        .alert-count {{
            font-size: 48px;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
        }}
        .alert-critical {{ color: #ef4444; }}
        .alert-warning {{ color: #f59e0b; }}
        .alert-info {{ color: #3b82f6; }}
        .repair-list {{
            max-height: 300px;
            overflow-y: auto;
        }}
        .repair-item {{
            padding: 12px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            margin-bottom: 8px;
            font-size: 13px;
        }}
        .repair-time {{
            color: rgba(255,255,255,0.5);
            font-size: 11px;
        }}
        .repair-strategy {{
            display: inline-block;
            padding: 2px 8px;
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border-radius: 4px;
            font-size: 12px;
            margin: 4px 0;
        }}
        .gateway-status {{
            font-family: monospace;
            white-space: pre-wrap;
            font-size: 12px;
            color: rgba(255,255,255,0.8);
            background: rgba(0,0,0,0.3);
            padding: 12px;
            border-radius: 8px;
            max-height: 150px;
            overflow: auto;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: rgba(255,255,255,0.4);
            font-size: 12px;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .live {{ animation: pulse 2s infinite; }}
    </style>
    <meta http-equiv="refresh" content="30">
</head>
<body>
    <div class="header">
        <div class="logo">奥创<span>运维</span>仪表板 🦞</div>
        <div class="status-badge {health}" style="background: {health_color};">
            {health.upper()} <span class="live">●</span>
        </div>
    </div>
    
    <div class="grid">
        <!-- 系统指标 -->
        <div class="card">
            <div class="card-title">💻 系统资源</div>
            <div class="metric">
                <span class="metric-label">CPU 使用率</span>
                <span class="metric-value">{metrics.get('cpu_percent', 0):.1f}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill progress-cpu" style="width: {min(metrics.get('cpu_percent', 0), 100)}%"></div>
            </div>
            
            <div class="metric" style="margin-top: 20px;">
                <span class="metric-label">内存使用率</span>
                <span class="metric-value">{metrics.get('mem_percent', 0):.1f}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill progress-mem" style="width: {min(metrics.get('mem_percent', 0), 100)}%"></div>
            </div>
            
            <div class="metric" style="margin-top: 20px;">
                <span class="metric-label">磁盘使用率</span>
                <span class="metric-value">{metrics.get('disk_percent', '0')}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill progress-disk" style="width: {min(int(metrics.get('disk_percent', '0')), 100)}%"></div>
            </div>
            
            <div class="metric" style="margin-top: 20px;">
                <span class="metric-label">系统负载</span>
                <span class="metric-value" style="font-size: 16px;">{metrics.get('load_avg', 'N/A')}</span>
            </div>
            <div class="metric">
                <span class="metric-label">进程数 / 网络连接</span>
                <span class="metric-value" style="font-size: 16px;">{metrics.get('process_count', 0)} / {metrics.get('net_connections', 0)}</span>
            </div>
        </div>
        
        <!-- 告警状态 -->
        <div class="card">
            <div class="card-title">🚨 告警状态</div>
            <div class="alert-count" style="color: #ef4444;">{alerts['total']}</div>
            <div style="text-align: center; color: rgba(255,255,255,0.6);">总告警数</div>
            
            <div style="display: flex; justify-content: space-around; margin-top: 30px;">
                <div>
                    <div class="alert-count alert-critical" style="font-size: 28px;">{alerts['critical']}</div>
                    <div style="text-align: center; color: #ef4444;">严重</div>
                </div>
                <div>
                    <div class="alert-count alert-warning" style="font-size: 28px;">{alerts['warning']}</div>
                    <div style="text-align: center; color: #f59e0b;">警告</div>
                </div>
                <div>
                    <div class="alert-count alert-info" style="font-size: 28px;">{alerts['info']}</div>
                    <div style="text-align: center; color: #3b82f6;">信息</div>
                </div>
            </div>
        </div>
        
        <!-- 修复历史 -->
        <div class="card">
            <div class="card-title">🔧 修复历史</div>
            <div class="repair-list">
                {''.join([f'''
                <div class="repair-item">
                    <div class="repair-time">{r['timestamp'][:19]}</div>
                    <span class="repair-strategy">{r['strategy']}</span>
                    <div style="color: rgba(255,255,255,0.7); margin-top: 4px;">
                        {'✓ ' + str(r['result'].get('action', 'N/A')) if r['result'].get('success') else '✗ Failed'}
                    </div>
                </div>''' for r in repairs]) if repairs else '<div style="color: rgba(255,255,255,0.5); text-align: center; padding: 20px;">暂无修复记录</div>'}
            </div>
        </div>
        
        <!-- Gateway状态 -->
        <div class="card">
            <div class="card-title">🔌 OpenClaw Gateway</div>
            <div class="gateway-status">{gateway_status[:500]}</div>
        </div>
    </div>
    
    <div class="footer">
        最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 页面每30秒自动刷新
    </div>
</body>
</html>"""
    
    with open(OUTPUT_FILE, 'w') as f:
        f.write(html)
    
    return str(OUTPUT_FILE)


if __name__ == "__main__":
    output = generate_dashboard()
    print(f"✅ 运维仪表板已生成: {output}")