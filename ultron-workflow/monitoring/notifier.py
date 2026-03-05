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
            elif channel == "email":
                result = self.notify_email(alert)
                results.append({"channel": "email", "result": result})
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
        dingtalk_config = self.config.get("dingtalk", {})
        webhook = dingtalk_config.get("webhook")
        
        if not webhook:
            return {"status": "skipped", "reason": "no_webhook_configured"}
        
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
        
        # 如果有密钥，使用签名
        secret = dingtalk_config.get("secret")
        if secret:
            import hmac
            import hashlib
            import base64
            import urllib.parse
            
            timestamp = str(int(datetime.now().timestamp() * 1000))
            sign_str = f"{timestamp}\n{secret}"
            sign = base64.b64encode(hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).digest()).decode()
            sign = urllib.parse.quote_plus(sign)
            webhook = f"{webhook}&timestamp={timestamp}&sign={sign}"
        
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
    
    def notify_email(self, alert):
        """邮件通知"""
        email_config = self.config.get("email", {})
        smtp_config = email_config.get("smtp", {})
        
        if not smtp_config:
            return {"status": "skipped", "reason": "no_smtp_configured"}
        
        recipients = email_config.get("to", [])
        if not recipients:
            return {"status": "skipped", "reason": "no_recipients_configured"}
        
        level = alert.get("level", "info")
        message = alert.get("message", "")
        timestamp = alert.get("timestamp", datetime.now().isoformat())
        
        # 邮件主题
        level_emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
        subject = f"{level_emoji.get(level, 'ℹ️')} 奥创告警: {level.upper()}"
        
        # 邮件正文
        body = f"""
<html>
<body>
<h2>🤖 奥创智能告警系统</h2>
<table style="border-collapse: collapse; width: 100%; max-width: 600px;">
<tr>
    <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><b>告警级别</b></td>
    <td style="padding: 8px; border: 1px solid #ddd;"><span style="color: {self._get_level_color(level)}; font-weight: bold;">{level.upper()}</span></td>
</tr>
<tr>
    <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><b>消息</b></td>
    <td style="padding: 8px; border: 1px solid #ddd;">{message}</td>
</tr>
<tr>
    <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><b>时间</b></td>
    <td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td>
</tr>
<tr>
    <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><b>详情</b></td>
    <td style="padding: 8px; border: 1px solid #ddd;"><pre>{json.dumps(alert.get('context', {}), indent=2, ensure_ascii=False)}</pre></td>
</tr>
</table>
<hr>
<p style="color: #888; font-size: 12px;">此邮件由奥创智能告警系统自动发送</p>
</body>
</html>
"""
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = smtp_config.get("from", "ultron@localhost")
            msg['To'] = ", ".join(recipients)
            
            # 添加HTML和纯文本版本
            text_body = f"告警级别: {level.upper()}\n消息: {message}\n时间: {timestamp}\n详情: {json.dumps(alert.get('context', {}), ensure_ascii=False)}"
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 连接SMTP服务器发送
            host = smtp_config.get("host", "localhost")
            port = smtp_config.get("port", 25)
            username = smtp_config.get("username")
            password = smtp_config.get("password")
            use_tls = smtp_config.get("use_tls", False)
            
            server = smtplib.SMTP(host, port, timeout=10)
            if use_tls:
                server.starttls()
            if username and password:
                server.login(username, password)
            
            server.sendmail(
                smtp_config.get("from", "ultron@localhost"),
                recipients,
                msg.as_string()
            )
            server.quit()
            
            self.log("info", f"邮件通知发送成功 to {recipients}")
            return {"status": "ok", "recipients": recipients}
        
        except ImportError:
            return {"status": "error", "reason": "smtplib not available"}
        except Exception as e:
            self.log("error", f"邮件通知失败: {str(e)}")
            return {"status": "error", "reason": str(e)}
    
    def _get_level_color(self, level):
        """获取级别对应的颜色"""
        colors = {
            "info": "#2196F3",
            "warning": "#FF9800",
            "error": "#F44336",
            "critical": "#9C27B0"
        }
        return colors.get(level, "#666666")
    
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