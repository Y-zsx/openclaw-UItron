#!/usr/bin/env python3
"""
告警集成模块
负责统一处理各类告警通知
"""
import os, json
from datetime import datetime

class AlertManager:
    def __init__(self):
        self.alert_history = []
        self.config = self.load_config()
    
    def load_config(self):
        config_path = '/root/.openclaw/workspace/ultron-workflow/config/alert_config.json'
        if os.path.exists(config_path):
            with open(config_path) as f:
                return json.load(f)
        return {'enabled': True, 'cooldown': 300}
    
    def send_alert(self, title, message, level='warning'):
        """发送告警"""
        alert = {
            'time': datetime.now().isoformat(),
            'title': title,
            'message': message,
            'level': level
        }
        self.alert_history.append(alert)
        
        if len(self.alert_history) > 20:
            self.alert_history = self.alert_history[-20:]
        
        print(f"[ALERT] {level.upper()}: {title} - {message}")
        return alert
    
    def check_cooldown(self, alert_type):
        """检查冷却时间"""
        if not self.alert_history:
            return True
        
        recent = [a for a in self.alert_history if alert_type in a.get('title', '')]
        if not recent:
            return True
        
        last_time = datetime.fromisoformat(recent[-1]['time'])
        cooldown = self.config.get('cooldown', 300)
        
        return (datetime.now() - last_time).seconds >= cooldown

if __name__ == '__main__':
    am = AlertManager()
    am.send_alert('Test Alert', 'This is a test', 'info')