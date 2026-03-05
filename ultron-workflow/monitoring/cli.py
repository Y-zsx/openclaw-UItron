#!/usr/bin/env python3
"""
监控CLI工具
"""
import json
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from monitor import get_monitor
from alert_engine import get_engine
from notifier import get_notifier

COMMANDS = """
🤖 Agent服务监控与告警系统

用法: ultron-monitor.py <command> [args...]

命令:
  collect              收集所有指标
  summary              获取健康状态摘要
  metrics              获取所有指标(JSON)
  
  alert list           列出告警规则
  alert add <rule>     添加告警规则
  alert remove <id>    删除告警规则
  alert evaluate <json> 评估规则
  
  alerts [level]       查看告警历史
  alert clear <id>     清除告警
  
  notify test          发送测试通知
  notify config        查看通知配置
  notify set <key> <value> 设置配置
  
  dashboard            生成HTML仪表板
  run                  运行完整监控循环
"""


def main():
    if len(sys.argv) < 2:
        print(COMMANDS)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "collect":
        monitor = get_monitor()
        metrics = monitor.collect_all()
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    
    elif cmd == "summary":
        monitor = get_monitor()
        summary = monitor.get_status_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    elif cmd == "metrics":
        monitor = get_monitor()
        metrics = monitor.collect_all()
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    
    elif cmd == "alert":
        if len(sys.argv) < 3:
            print("用法: ultron-monitor.py alert <list|add|remove|evaluate>")
            sys.exit(1)
        
        subcmd = sys.argv[2]
        engine = get_engine()
        
        if subcmd == "list":
            print(json.dumps(engine.rules, indent=2, ensure_ascii=False))
        
        elif subcmd == "add":
            rule = json.loads(sys.argv[3])
            engine.add_rule(rule)
            print(json.dumps({"status": "success"}))
        
        elif subcmd == "remove":
            rule_id = sys.argv[3]
            engine.remove_rule(rule_id)
            print(json.dumps({"status": "success"}))
        
        elif subcmd == "evaluate":
            metrics = json.loads(sys.argv[3])
            triggered = engine.evaluate(metrics)
            print(json.dumps({"triggered": triggered}, indent=2, ensure_ascii=False))
    
    elif cmd == "alerts":
        engine = get_engine()
        level = sys.argv[2] if len(sys.argv) > 2 else None
        alerts = engine.get_alerts(level)
        print(json.dumps(alerts, indent=2, ensure_ascii=False))
    
    elif cmd == "alert":
        if len(sys.argv) < 3:
            print("用法: ultron-monitor.py alert <list|add|remove|evaluate|clear>")
            sys.exit(1)
        
        subcmd = sys.argv[2]
        engine = get_engine()
        
        if subcmd == "list":
            print(json.dumps(engine.rules, indent=2, ensure_ascii=False))
        elif subcmd == "clear":
            alert_id = sys.argv[3]
            engine.clear_alert(alert_id)
            print(json.dumps({"status": "success"}))
    
    elif cmd == "notify":
        if len(sys.argv) < 3:
            print("用法: ultron-monitor.py notify <test|config|set>")
            sys.exit(1)
        
        subcmd = sys.argv[2]
        notifier = get_notifier()
        
        if subcmd == "test":
            test_alert = {
                "level": "warning",
                "message": "测试告警 - 系统运行正常",
                "timestamp": json.dumps({"now": "test"}, default=str),
                "context": {"test": True}
            }
            result = notifier.notify(test_alert)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif subcmd == "config":
            print(json.dumps(notifier.config, indent=2, ensure_ascii=False))
        
        elif subcmd == "set":
            if len(sys.argv) < 5:
                print("用法: ultron-monitor.py notify set <key> <value>")
                sys.exit(1)
            key = sys.argv[3]
            value = sys.argv[4]
            try:
                value = json.loads(value)
            except:
                pass
            result = notifier.set_config(key, value)
            print(json.dumps(result))
    
    elif cmd == "dashboard":
        monitor = get_monitor()
        engine = get_engine()
        
        summary = monitor.get_status_summary()
        alerts = engine.get_alerts(limit=10)
        
        # 构建HTML
        health = summary['health']
        issues_html = ''.join([f'<div>• {issue}</div>' for issue in summary.get('issues', [])]) if summary.get('issues') else '<div>✓ 所有系统正常</div>'
        
        # 资源指标
        cpu_val = summary['metrics'].get('cpu_percent', 0)
        mem_val = summary['metrics'].get('memory_percent', 0)
        disk_val = summary['metrics'].get('disk_percent', 0)
        
        cpu_class = 'warning' if cpu_val > 80 else ''
        mem_class = 'warning' if mem_val > 85 else ''
        disk_class = 'warning' if disk_val > 90 else ''
        
        # Gateway指标
        gateway_reachable = summary['metrics'].get('gateway_reachable', False)
        gateway_reachable_text = '否' if not gateway_reachable else '是'
        gateway_reachable_class = 'error' if not gateway_reachable else ''
        gateway_service_running = summary['metrics'].get('gateway_service_running', False)
        gateway_service_text = '运行中' if gateway_service_running else '未运行'
        
        # Agent状态
        agent_coordinator = summary['metrics'].get('agent_coordinator_status', 'unknown')
        agent_executor = summary['metrics'].get('agent_executor_status', 'unknown')
        agent_analyzer = summary['metrics'].get('agent_analyzer_status', 'unknown')
        agent_monitor = summary['metrics'].get('agent_monitor_status', 'unknown')
        
        # 告警HTML
        if alerts:
            alerts_html = ''.join([f'<div class="alert {a.get("level", "info")}">{a.get("message", "")} <small>{a.get("timestamp", "")}</small></div>' for a in alerts])
        else:
            alerts_html = '<div>无告警记录</div>'
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Agent监控仪表板</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; }}
        .status {{ padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .status.healthy {{ background: #1b4332; border: 2px solid #2d6a4f; }}
        .status.degraded {{ background: #3d2c00; border: 2px solid #b8860b; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }}
        .card {{ background: #16213e; padding: 15px; border-radius: 8px; border: 1px solid #0f3460; }}
        .card h3 {{ margin-top: 0; color: #00d4ff; }}
        .metric {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #0f3460; }}
        .metric:last-child {{ border-bottom: none; }}
        .value {{ color: #00d4ff; font-weight: bold; }}
        .value.warning {{ color: #f39c12; }}
        .value.error {{ color: #e74c3c; }}
        .alert {{ padding: 10px; margin: 5px 0; border-radius: 5px; }}
        .alert.warning {{ background: #3d2c00; border-left: 4px solid #f39c12; }}
        .alert.error {{ background: #3d0a0a; border-left: 4px solid #e74c3c; }}
        .alert.critical {{ background: #3d0a0a; border-left: 4px solid #ff0000; animation: pulse 1s infinite; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}
        .issues {{ background: #3d0a0a; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Agent服务监控</h1>
        
        <div class="status {health}">
            <h2>状态: {health.upper()}</h2>
            {issues_html}
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>系统资源</h3>
                <div class="metric"><span>CPU</span><span class="{cpu_class}">{cpu_val:.1f}%</span></div>
                <div class="metric"><span>内存</span><span class="{mem_class}">{mem_val:.1f}%</span></div>
                <div class="metric"><span>磁盘</span><span class="{disk_class}">{disk_val:.1f}%</span></div>
                <div class="metric"><span>负载</span><span>{summary['metrics'].get('load_avg_1m', 0):.2f}</span></div>
            </div>
            
            <div class="card">
                <h3>Gateway状态</h3>
                <div class="metric"><span>可达</span><span class="{gateway_reachable_class}">{gateway_reachable_text}</span></div>
                <div class="metric"><span>服务</span><span>{gateway_service_text}</span></div>
                <div class="metric"><span>Agent数</span><span>{summary['metrics'].get('agent_count', 0)}</span></div>
                <div class="metric"><span>会话数</span><span>{summary['metrics'].get('session_count', 0)}</span></div>
            </div>
            
            <div class="card">
                <h3>Agent状态</h3>
                <div class="metric"><span>Coordinator</span><span>{agent_coordinator}</span></div>
                <div class="metric"><span>Executor</span><span>{agent_executor}</span></div>
                <div class="metric"><span>Analyzer</span><span>{agent_analyzer}</span></div>
                <div class="metric"><span>Monitor</span><span>{agent_monitor}</span></div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <h3>最近告警</h3>
            {alerts_html}
        </div>
    </div>
</body>
</html>"""
        
        with open("/root/.openclaw/workspace/ultron-workflow/monitoring/dashboard.html", 'w') as f:
            f.write(html)
        
        print("仪表板已生成: /root/.openclaw/workspace/ultron-workflow/monitoring/dashboard.html")
    
    elif cmd == "run":
        # 运行完整监控循环
        import time
        from datetime import datetime
        
        print("开始监控循环...")
        
        monitor = get_monitor()
        engine = get_engine()
        notifier = get_notifier()
        
        while True:
            try:
                # 收集指标
                metrics = monitor.collect_all()
                print(f"[{datetime.now().isoformat()}] 指标收集完成")
                
                # 评估规则
                triggered = engine.evaluate(metrics)
                
                if triggered:
                    print(f"[{datetime.now().isoformat()}] 触发 {len(triggered)} 个告警")
                    for alert in triggered:
                        notifier.notify(alert)
                
                time.sleep(60)  # 每分钟检查一次
            
            except KeyboardInterrupt:
                print("监控循环已停止")
                break
            except Exception as e:
                print(f"错误: {e}")
                time.sleep(10)
    
    else:
        print(COMMANDS)


if __name__ == "__main__":
    main()