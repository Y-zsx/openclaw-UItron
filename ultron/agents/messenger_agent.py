#!/usr/bin/env python3
"""Messenger Agent - 消息通信"""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from message_bus import MessageBus

class MessengerAgent:
    def __init__(self):
        self.name = "messenger"
        self.bus = MessageBus()
        self.report_file = Path(__file__).parent / "reports.json"
        self._ensure_reports()
    
    def _ensure_reports(self):
        if not self.report_file.exists():
            self._save_reports([])
    
    def _load_reports(self):
        return json.loads(self.report_file.read_text())
    
    def _save_reports(self, reports):
        self.report_file.write_text(json.dumps(reports, indent=2, ensure_ascii=False))
    
    def send_report(self, title, content):
        """发送报告"""
        report = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "title": title,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "status": "sent"
        }
        
        reports = self._load_reports()
        reports.append(report)
        self._save_reports(reports)
        
        return report
    
    def get_messages(self):
        """获取订阅的消息"""
        return self.bus.subscribe("messenger")
    
    def run(self):
        """运行messenger"""
        messages = self.get_messages()
        
        if messages:
            # 汇总消息生成报告
            latest = messages[-1]
            report = self.send_report(
                title=f"系统消息: {latest.get('type', 'info')}",
                content=latest.get('message', '')
            )
            print(f"[Messenger] 报告已生成: {report['id']}")
        else:
            print("[Messenger] 无新消息")
        
        return messages

if __name__ == "__main__":
    agent = MessengerAgent()
    agent.run()