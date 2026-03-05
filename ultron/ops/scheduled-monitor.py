#!/usr/bin/env python3
"""
智能运维助手 - 定时监控调度器
功能：定期执行系统监控、检查告警并发送通知

第76世: 定时监控调度
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))
parent_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, parent_dir)

from monitor_agent import MonitorAgent
import importlib.util

# 动态加载 ops-alert-notifier
spec = importlib.util.spec_from_file_location(
    "ops_alert_notifier", 
    os.path.join(parent_dir, "ops-alert-notifier.py")
)
ops_alert_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops_alert_module)

AlertNotifier = ops_alert_module.AlertNotifier
AlertLevel = ops_alert_module.AlertLevel

# 配置
LOG_PATH = "/root/.openclaw/workspace/ultron/logs/scheduled-monitor.log"
STATE_PATH = "/root/.openclaw/workspace/ultron/logs/monitor-state.json"
INTERVAL_SECONDS = 300  # 5分钟


def log(message: str):
    """日志输出"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(log_line.strip())
    
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, 'a') as f:
        f.write(log_line)


def load_state() -> dict:
    """加载监控状态"""
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, 'r') as f:
            return json.load(f)
    return {
        "last_check": None,
        "last_alert": None,
        "check_count": 0,
        "alert_count": 0,
        "last_metrics": {}
    }


def save_state(state: dict):
    """保存监控状态"""
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def check_and_alert():
    """执行监控并检查是否需要告警"""
    log("开始执行定时监控...")
    
    # 加载状态
    state = load_state()
    
    try:
        # 1. 执行系统检查
        agent = MonitorAgent()
        metrics = agent.check_system()
        
        log(f"系统状态: load={metrics.get('load', 'N/A')}, "
            f"memory={metrics.get('memory_pct', 'N/A')}%, "
            f"disk={metrics.get('disk_pct', 'N/A')}%, "
            f"gateway={metrics.get('gateway_ok', 'N/A')}")
        
        # 2. 检查是否需要告警
        alerts = agent.should_alert(metrics)
        
        # 3. 发送告警
        if alerts:
            log(f"检测到 {len(alerts)} 个告警条件!")
            
            # 初始化告警通知器
            notifier = AlertNotifier()
            
            for alert in alerts:
                level_str = alert.get('level', 'WARNING')
                level = AlertLevel.WARNING if level_str == 'WARNING' else AlertLevel.CRITICAL
                
                alert_data = {
                    'level': level_str,
                    'message': alert.get('message', '系统告警'),
                    'metric': alert.get('metric', 'N/A'),
                    'value': alert.get('value', 0),
                    'threshold': alert.get('threshold', 0),
                    'condition': alert.get('condition', '>'),
                    'rule': alert.get('rule', 'auto-threshold'),
                    'timestamp': datetime.now().isoformat()
                }
                
                notifier.notify(alert_data, level)
                state['alert_count'] = state.get('alert_count', 0) + 1
                state['last_alert'] = datetime.now().isoformat()
        else:
            log("系统运行正常，无告警")
        
        # 4. 更新状态
        state['last_check'] = datetime.now().isoformat()
        state['check_count'] = state.get('check_count', 0) + 1
        state['last_metrics'] = metrics
        save_state(state)
        
        log(f"监控完成: 第 {state['check_count']} 次检查")
        return True
        
    except Exception as e:
        log(f"监控执行失败: {e}")
        return False


def main():
    """主函数"""
    log("=" * 50)
    log("定时监控调度器启动")
    log("=" * 50)
    
    # 立即执行一次检查
    check_and_alert()
    
    log(f"等待 {INTERVAL_SECONDS} 秒后进行下一次检查...")


if __name__ == "__main__":
    main()