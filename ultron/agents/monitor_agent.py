#!/usr/bin/env python3
"""Monitor Agent - 监控系统状态 + 告警通知渠道 + 智能预测告警"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import importlib.util

# 添加父目录到路径
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from agents.message_bus import MessageBus

# 动态导入 ops_alert_notifier
notifier_spec = importlib.util.spec_from_file_location(
    "ops_alert_notifier", 
    BASE_DIR / "ops-alert-notifier.py"
)
notifier_module = importlib.util.module_from_spec(notifier_spec)
notifier_spec.loader.exec_module(notifier_module)
AlertNotifier = notifier_module.AlertNotifier
AlertLevel = notifier_module.AlertLevel

# 动态导入预测告警模块
predictive_spec = importlib.util.spec_from_file_location(
    "predictive_alert",
    BASE_DIR / "predictive_alert.py"
)
predictive_module = importlib.util.module_from_spec(predictive_spec)
predictive_spec.loader.exec_module(predictive_module)
PredictiveAlert = predictive_module.PredictiveAlert

class MonitorAgent:
    def __init__(self):
        self.name = "monitor"
        self.bus = MessageBus()
        self.notifier = AlertNotifier()
        self.predictor = PredictiveAlert()
        self.last_check = None
        self.predictive_alert_cooldown = 300  # 预测告警冷却时间（秒）
    
    def check_system(self):
        """检查系统状态"""
        try:
            # CPU负载
            load = subprocess.check_output(
                "cat /proc/loadavg | awk '{print $1}'", shell=True
            ).decode().strip()
            
            # 内存
            mem = subprocess.check_output(
                "free -m | grep Mem:", shell=True
            ).decode()
            mem_parts = mem.split()
            mem_used = mem_parts[2]
            mem_total = mem_parts[1]
            mem_pct = int(mem_used) / int(mem_total) * 100
            
            # 磁盘
            disk = subprocess.check_output(
                "df -h / | tail -1 | awk '{print $5}'", shell=True
            ).decode().strip().replace('%', '')
            
            # Gateway状态
            gateway_ok = subprocess.run(
                ["pgrep", "-f", "openclaw"],
                capture_output=True
            ).returncode == 0
            
            return {
                "load": float(load),
                "memory_pct": round(mem_pct, 1),
                "disk_pct": int(disk),
                "gateway_ok": gateway_ok,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def should_alert(self, status):
        """判断是否需要告警"""
        alerts = []
        if status.get("load", 0) > 5:
            alerts.append("load_high")
        if status.get("memory_pct", 0) > 90:
            alerts.append("memory_high")
        if status.get("disk_pct", 0) > 90:
            alerts.append("disk_full")
        if not status.get("gateway_ok", True):
            alerts.append("gateway_down")
        return alerts
    
    def predict_alerts(self, status):
        """智能预测告警 - 分析趋势并预测未来可能的问题"""
        # 添加当前指标到历史
        self.predictor.add_metrics({
            'load': status.get('load', 0),
            'memory_pct': status.get('memory_pct', 0),
            'disk_pct': status.get('disk_pct', 0)
        })
        
        # 进行预测分析
        prediction = self.predictor.predict()
        
        # 如果有预测告警，发送通知
        if prediction.get('alerts'):
            alert_list = []
            for pred_alert in prediction['alerts']:
                level = AlertLevel.CRITICAL.value if pred_alert['level'] == 'critical' else AlertLevel.WARNING.value
                alert = {
                    "rule": f"预测:{pred_alert['metric']}",
                    "metric": pred_alert['metric'],
                    "value": pred_alert['current'],
                    "threshold": pred_alert['threshold'],
                    "condition": "预测将达到",
                    "level": pred_alert['level'].upper(),
                    "message": pred_alert['message'],
                    "prediction": pred_alert['prediction'],
                    "timestamp": datetime.now().isoformat()
                }
                alert_list.append(alert)
            
            # 通过告警渠道发送预测告警
            results = self.notifier.notify(alert_list)
            print(f"[Predictive] 预测告警已发送至 {len(results['channels'])} 个渠道")
            
            # 发送到消息总线
            self.bus.publish(
                sender="monitor",
                recipient="executor",
                message=f"预测告警: {[a['metric'] for a in prediction['alerts']]}",
                task_type="task"
            )
            
            return prediction
        
        # 输出趋势摘要
        trend_summary = self.predictor.get_trend_summary()
        print(f"[Predictive] 趋势分析: {trend_summary}")
        
        return prediction
    
    def run(self):
        """运行监控"""
        status = self.check_system()
        alerts = self.should_alert(status)
        
        if alerts:
            # 构建告警列表，发送到各个渠道
            alert_list = []
            for alert_type in alerts:
                level = AlertLevel.CRITICAL.value if alert_type == "gateway_down" else AlertLevel.WARNING.value
                alert = {
                    "rule": f"系统{alert_type}",
                    "metric": alert_type,
                    "value": status.get(alert_type.replace("_high", "_pct").replace("_full", "_pct"), "N/A"),
                    "threshold": "N/A",
                    "condition": ">",
                    "level": "CRITICAL" if alert_type == "gateway_down" else "WARNING",
                    "message": f"系统告警: {alert_type}",
                    "timestamp": datetime.now().isoformat()
                }
                alert_list.append(alert)
            
            # 通过告警渠道发送
            results = self.notifier.notify(alert_list)
            print(f"[Monitor] 告警已发送至 {len(results['channels'])} 个渠道")
            
            # 同时发送到消息总线
            self.bus.publish(
                sender="monitor",
                recipient="executor",
                message=f"告警: {', '.join(alerts)}",
                task_type="task"
            )
        else:
            print(f"[Monitor] 系统正常 - Load:{status['load']} Mem:{status['memory_pct']}% Disk:{status['disk_pct']}%")
        
        # 发送状态报告给messenger
        self.bus.publish(
            sender="monitor",
            recipient="messenger",
            message=f"状态报告: Load={status['load']}, Mem={status['memory_pct']}%, Disk={status['disk_pct']}%",
            task_type="message"
        )
        
        # 执行智能预测告警（每3次检查执行一次预测，避免频繁）
        check_count = getattr(self, 'check_count', 0) + 1
        self.check_count = check_count
        
        if check_count % 3 == 0:  # 每3次监控执行一次预测分析
            self.predict_alerts(status)
        
        return status

if __name__ == "__main__":
    agent = MonitorAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))