#!/usr/bin/env python3
"""Monitor Agent - 监控系统状态"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from message_bus import MessageBus

class MonitorAgent:
    def __init__(self):
        self.name = "monitor"
        self.bus = MessageBus()
        self.last_check = None
    
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
    
    def run(self):
        """运行监控"""
        status = self.check_system()
        alerts = self.should_alert(status)
        
        if alerts:
            # 发送告警给executor
            self.bus.publish(
                sender="monitor",
                recipient="executor",
                message=f"告警: {', '.join(alerts)}",
                task_type="task"
            )
            print(f"[Monitor] 告警已发送: {alerts}")
        else:
            print(f"[Monitor] 系统正常 - Load:{status['load']} Mem:{status['memory_pct']}% Disk:{status['disk_pct']}%")
        
        # 发送状态报告给messenger
        self.bus.publish(
            sender="monitor",
            recipient="messenger",
            message=f"状态报告: Load={status['load']}, Mem={status['memory_pct']}%, Disk={status['disk_pct']}%",
            task_type="message"
        )
        
        return status

if __name__ == "__main__":
    agent = MonitorAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))