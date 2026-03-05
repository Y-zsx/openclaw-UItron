#!/usr/bin/env python3
"""
告警通知器
支持多种通知渠道: 钉钉、邮件、console
"""
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

NOTIFIER_DIR = Path("/root/.openclaw/workspace/ultron-workflow/monitoring")
CONFIG_FILE = NOTIFIER_DIR / "config.json"
LOG_FILE = NOTIFIER_DIR / "notifications.log"


class AlertNotifier:
    """告警通知器"""
    
    def __init__(self):
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置"""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        
        # 默认配置
        default_config = {
            "enabled": True,
            "channels": ["console"],
            "dingtalk": {
                "webhook": None,
                "secret": None
            },
            "email": {
                "smtp": None,
                "to": []
            },
            "levels": ["warning", "error", "critical"]
        }
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        return default_config
    
    def save_config(self):
        """保存配置"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def log(self, level, message):
        """记录日志"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level.upper()}] {message}"
        print(log_entry)
        with open(LOG_FILE, 'a') as f:
            f.write(log_entry + '\n')
    
    def notify(self, alert):
        """发送告警通知"""
        if not self.config.get("enabled", True):
            return {"status": "disabled"}
        
        level = alert.get("level", "info")
        levels = self.config.get("levels", [])
        
        # 检查是否需要通知此级别
        level_priority = {"info": 0, "warning": 1, "error": 2, "critical": 3}
        if level_priority.get(level, 0) < level_priority.get(levels[0] if levels else "info", 0):
            return {"status": "skipped", "reason": "level_not_configured"}
        
        results = []
        
        for channel in self.config.get("channels", []):
            if channel == "dingtalk":
                result = self.notify_dingtalk(alert)
                results.append({"channel": "dingtalk", "result": result})
            elif channel == "console":
                result = self.notify_console(alert)
                results.append({"channel": "console", "result": result})
        
        return {"status": "sent", "results": results}
    
    def notify_console(self, alert):
        """控制台通知"""
        level = alert.get("level", "info")
        message = alert.get("message", "")
        
        emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨"
        }
        
        emoji = emojis.get(level, "ℹ️")
        self.log(level, f"{emoji} {message}")
        
        return {"status": "ok"}
    
    def notify_dingtalk(self, alert):
        """钉钉通知"""
        webhook = self.config.get("dingtalk", {}).get("webhook")
        
        if not webhook:
            return {"status": "error", "reason": "no_webhook_configured"}
        
        level = alert.get("level", "info")
        message = alert.get("message", "")
        
        # 构建消息
        msg_type = "markdown" if level in ["error", "critical"] else "text"
        
        if msg_type == "markdown":
            content = f"### 🤖 奥创告警\n\n" \
                     f"**级别**: {level.upper()}\n\n" \
                     f"**消息**: {message}\n\n" \
                     f"**时间**: {alert.get('timestamp', '')}\n\n" \
                     f"**详情**: {json.dumps(alert.get('context', {}), ensure_ascii=False)}"
        else:
            content = f"🤖 奥创告警\n级别: {level.upper()}\n消息: {message}"
        
        payload = {
            "msgtype": msg_type,
            msg_type: {
                "content": content
            }
        }
        
        try:
            # 使用curl发送
            cmd = [
                "curl", "-s", "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload, ensure_ascii=False),
                webhook
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.log("info", f"钉钉通知发送成功")
                return {"status": "ok", "response": result.stdout}
            else:
                self.log("error", f"钉钉通知发送失败: {result.stderr}")
                return {"status": "error", "reason": result.stderr}
        
        except Exception as e:
            self.log("error", f"钉钉通知异常: {str(e)}")
            return {"status": "error", "reason": str(e)}
    
    def notify_batch(self, alerts):
        """批量通知"""
        results = []
        for alert in alerts:
            result = self.notify(alert)
            results.append(result)
        return results
    
    def set_config(self, key, value):
        """设置配置"""
        keys = key.split(".")
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self.save_config()
        return {"status": "success"}


def get_notifier():
    """获取通知器实例"""
    return AlertNotifier()


if __name__ == "__main__":
    import sys
    
    notifier = get_notifier()
    
    if len(sys.argv) < 2:
        print(json.dumps(notifier.config, indent=2, ensure_ascii=False))
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "config":
        print(json.dumps(notifier.config, indent=2, ensure_ascii=False))
    
    elif cmd == "set":
        key = sys.argv[2]
        value = sys.argv[3]
        # 尝试解析JSON
        try:
            value = json.loads(value)
        except:
            pass
        result = notifier.set_config(key, value)
        print(json.dumps(result))
    
    elif cmd == "test":
        # 发送测试告警
        test_alert = {
            "level": "warning",
            "message": "测试告警 - 系统正常",
            "timestamp": datetime.now().isoformat(),
            "context": {"test": True}
        }
        result = notifier.notify(test_alert)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "send":
        # 发送告警
        alert = json.loads(sys.argv[2])
        result = notifier.notify(alert)
        print(json.dumps(result, indent=2, ensure_ascii=False))