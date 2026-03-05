#!/usr/bin/env python3
"""
监控数据可视化模块
功能：将监控数据转换为可视化HTML报告
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

STATE_FILE = "/root/.openclaw/workspace/ultron/logs/monitor-state.json"
METRICS_FILE = "/root/.openclaw/workspace/ultron/logs/metrics-history.json"
OUTPUT_DIR = "/root/.openclaw/workspace/ultron/docs"
OUTPUT_FILE = f"{OUTPUT_DIR}/monitor-dashboard.html"


def load_state() -> Dict:
    """加载监控状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def load_metrics() -> List[Dict]:
    """加载历史指标"""
    if os.path.exists(METRICS_FILE):
        with open(METRICS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('metrics', []) if isinstance(data, dict) else data
    return []


def get_status_color(value: float, threshold: float) -> str:
    """根据阈值返回状态颜色"""
    if value < threshold * 0.7:
        return "#22c55e"  # 绿色 - 良好
    elif value < threshold:
        return "#eab308"  # 黄色 - 警告
    else:
        return "#ef4444"  # 红色 - 危险


def get_gateway_status_color(ok: bool) -> str:
    """网关状态颜色"""
    return "#22c55e" if ok else "#ef4444"


def generate_gauge(value: float, max_val: float, label: str, unit: str, threshold: float) -> str:
    """生成仪表盘HTML"""
    percentage = min(100, (value / max_val) * 100)
    color = get_status_color(value, threshold)
    
    return f'''
        <div class="gauge-container">
            <div class="gauge-label">{label}</div>
            <div class="gauge">
                <div class="gauge-fill" style="width: {percentage}%; background: {color};"></div>
                <div class="gauge-value">{value:.1f}{unit}</div>
            </div>
            <div class="gauge-threshold">阈值: {threshold}{unit}</div>
        </div>
    '''


def generate_chart_bars(metrics: List[Dict]) -> str:
    """生成柱状图HTML"""
    recent = metrics[-8:] if len(metrics) > 8 else metrics
    bars_html = ""
    for m in recent:
        height = min(100, (m.get('load', 0) / 4) * 100)
        bars_html += f'''
                <div>
                    <div class="bar bar-load" style="height: {height}px;"></div>
                    <div class="bar-label">Load</div>
                </div>
        '''
    return bars_html


def generate_dashboard(state: Dict, metrics: List[Dict]) -> str:
    """生成监控仪表盘HTML"""
    last_metrics = state.get('last_metrics', {})
    
    load = last_metrics.get('load', 0)
    mem = last_metrics.get('memory_pct', 0)
    disk = last_metrics.get('disk_pct', 0)
    gateway = last_metrics.get('gateway_ok', False)
    check_count = state.get('check_count', 0)
    alert_count = state.get('alert_count', 0)
    last_check = state.get('last_check', 'N/A')
    
    status_badge = '🟢 系统正常' if gateway else '🔴 网关异常'
    gateway_text = '是' if gateway else '否'
    
    # 生成仪表盘
    gauge_load = generate_gauge(load, 4, 'Load Average', '', 2.0)
    gauge_mem = generate_gauge(mem, 100, '内存使用', '%', 80)
    gauge_disk = generate_gauge(disk, 100, '磁盘使用', '%', 90)
    
    # 生成柱状图
    chart_bars = generate_chart_bars(metrics)
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ultron 监控仪表盘</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
            min-height: 100vh;
            padding: 20px;
            color: #e2e8f0;
        }}
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header .subtitle {{
            color: #94a3b8;
            font-size: 0.9rem;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            margin-top: 15px;
            background: {get_gateway_status_color(gateway)};
            color: white;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: rgba(30, 41, 59, 0.8);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.1);
        }}
        .card-title {{
            font-size: 1.1rem;
            color: #94a3b8;
            margin-bottom: 20px;
            font-weight: 500;
        }}
        .gauge-container {{
            margin-bottom: 20px;
        }}
        .gauge-label {{
            font-size: 0.9rem;
            color: #94a3b8;
            margin-bottom: 8px;
        }}
        .gauge {{
            height: 24px;
            background: #334155;
            border-radius: 12px;
            overflow: hidden;
            position: relative;
        }}
        .gauge-fill {{
            height: 100%;
            border-radius: 12px;
            transition: width 0.5s ease;
        }}
        .gauge-value {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: bold;
            font-size: 0.85rem;
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        }}
        .gauge-threshold {{
            font-size: 0.75rem;
            color: #64748b;
            margin-top: 4px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 20px;
        }}
        .stat {{
            text-align: center;
            padding: 15px;
            background: rgba(15, 23, 42, 0.5);
            border-radius: 12px;
        }}
        .stat-value {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #60a5fa;
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: #64748b;
            margin-top: 5px;
        }}
        .chart-section {{
            background: rgba(30, 41, 59, 0.8);
            border-radius: 16px;
            padding: 24px;
            margin-top: 20px;
        }}
        .chart-placeholder {{
            height: 150px;
            display: flex;
            align-items: flex-end;
            justify-content: space-around;
            padding: 20px 0;
        }}
        .bar {{
            width: 30px;
            border-radius: 4px 4px 0 0;
            transition: height 0.3s ease;
        }}
        .bar-load {{ background: linear-gradient(to top, #3b82f6, #60a5fa); }}
        .bar-mem {{ background: linear-gradient(to top, #8b5cf6, #a78bfa); }}
        .bar-disk {{ background: linear-gradient(to top, #10b981, #34d399); }}
        .bar-label {{
            text-align: center;
            font-size: 0.75rem;
            color: #64748b;
            margin-top: 8px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #475569;
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>🦞 Ultron 监控仪表盘</h1>
            <div class="subtitle">服务器实时状态监控</div>
            <div class="status-badge">
                {status_badge}
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">📊 系统负载</div>
                {gauge_load}
                {gauge_mem}
                {gauge_disk}
            </div>
            
            <div class="card">
                <div class="card-title">🔧 运行状态</div>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{check_count}</div>
                        <div class="stat-label">检查次数</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{alert_count}</div>
                        <div class="stat-label">告警次数</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{gateway_text}</div>
                        <div class="stat-label">网关状态</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{len(metrics)}</div>
                        <div class="stat-label">数据点</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="chart-section">
            <div class="card-title">📈 最近趋势 (Load)</div>
            <div class="chart-placeholder">
                {chart_bars}
            </div>
        </div>
        
        <div class="footer">
            <p>最后更新: {last_check}</p>
            <p>Powered by Ultron 🦞</p>
        </div>
    </div>
</body>
</html>
'''
    return html


def generate_markdown_report(state: Dict, metrics: List[Dict]) -> str:
    """生成Markdown格式的简报"""
    last_metrics = state.get('last_metrics', {})
    load = last_metrics.get('load', 0)
    mem = last_metrics.get('memory_pct', 0)
    disk = last_metrics.get('disk_pct', 0)
    gateway = last_metrics.get('gateway_ok', False)
    
    # 计算状态
    status = "✅ 正常"
    if load > 2 or mem > 80 or disk > 90 or not gateway:
        status = "⚠️ 警告"
    if load > 3 or mem > 90 or disk > 95:
        status = "🔴 危险"
    
    # 状态图标
    load_icon = '🟢' if load < 2 else '🟡' if load < 3 else '🔴'
    mem_icon = '🟢' if mem < 70 else '🟡' if mem < 85 else '🔴'
    disk_icon = '🟢' if disk < 80 else '🟡' if disk < 90 else '🔴'
    gateway_icon = '🟢' if gateway else '🔴'
    gateway_text = '运行中' if gateway else '离线'
    
    report = f'''# 📊 Ultron 监控报告

**状态**: {status}  
**更新时间**: {state.get('last_check', 'N/A')}

---

## 系统指标

| 指标 | 当前值 | 状态 |
|------|--------|------|
| Load | {load:.2f} | {load_icon} |
| 内存 | {mem:.1f}% | {mem_icon} |
| 磁盘 | {disk:.1f}% | {disk_icon} |
| Gateway | {gateway_text} | {gateway_icon} |

---

## 统计信息

- 检查次数: **{state.get('check_count', 0)}**
- 告警次数: **{state.get('alert_count', 0)}**
- 历史数据点: **{len(metrics)}**

---

*Powered by Ultron 🦞*
'''
    return report


def main():
    """主函数"""
    print("📊 生成监控可视化报告...")
    
    # 加载数据
    state = load_state()
    metrics = load_metrics()
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 生成HTML仪表盘
    dashboard_html = generate_dashboard(state, metrics)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(dashboard_html)
    print(f"✅ HTML仪表盘已生成: {OUTPUT_FILE}")
    
    # 生成Markdown报告
    md_file = f"{OUTPUT_DIR}/monitor-report.md"
    report_md = generate_markdown_report(state, metrics)
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(report_md)
    print(f"✅ Markdown报告已生成: {md_file}")
    
    # 输出摘要
    last_metrics = state.get('last_metrics', {})
    print(f"\n📈 当前状态:")
    print(f"   Load: {last_metrics.get('load', 0):.2f}")
    print(f"   内存: {last_metrics.get('memory_pct', 0):.1f}%")
    print(f"   磁盘: {last_metrics.get('disk_pct', 0):.1f}%")
    print(f"   网关: {'正常' if last_metrics.get('gateway_ok', False) else '离线'}")
    print(f"   检查次数: {state.get('check_count', 0)}")
    
    return True


if __name__ == "__main__":
    main()