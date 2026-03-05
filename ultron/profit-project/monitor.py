#!/usr/bin/env python3
"""
网站监控MVP - 核心监控模块
Website Monitoring SaaS - Core Monitor
"""

import json
import time
import requests
from datetime import datetime
from urllib.parse import urlparse
import ssl
import socket
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alerter

CONFIG_FILE = "sites.json"
LOG_FILE = "../logs/monitor.json"
ALERT_LOG = "../logs/alerts.json"

class WebsiteMonitor:
    def __init__(self):
        self.sites = self.load_config()
        self.results = []
        
    def load_config(self):
        """加载监控站点配置"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # 默认示例站点
            return {
                "sites": [
                    {"url": "https://www.baidu.com", "name": "百度", "interval": 60, "enabled": True},
                    {"url": "https://www.taobao.com", "name": "淘宝", "interval": 60, "enabled": True},
                    {"url": "https://httpbin.org/status/200", "name": "测试API", "interval": 30, "enabled": True}
                ]
            }
    
    def check_site(self, site):
        """检查单个站点"""
        url = site.get('url', '')
        name = site.get('name', url)
        
        result = {
            "site": name,
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "status": "unknown",
            "response_time": 0,
            "status_code": None,
            "error": None
        }
        
        start_time = time.time()
        try:
            # HTTP请求
            response = requests.get(url, timeout=10, verify=False)
            result["response_time"] = round((time.time() - start_time) * 1000, 2)
            result["status_code"] = response.status_code
            
            if response.status_code == 200:
                result["status"] = "up"
            else:
                result["status"] = "down"
                result["error"] = f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            result["status"] = "down"
            result["error"] = "Timeout"
            result["response_time"] = round((time.time() - start_time) * 1000, 2)
        except requests.exceptions.ConnectionError as e:
            result["status"] = "down"
            result["error"] = f"Connection error: {str(e)[:50]}"
        except Exception as e:
            result["status"] = "down"
            result["error"] = str(e)[:100]
        
        return result
    
    def check_ssl(self, url):
        """检查SSL证书"""
        try:
            parsed = urlparse(url)
            if parsed.scheme == 'https':
                hostname = parsed.netloc.split(':')[0]
                port = parsed.port or 443
                
                context = ssl.create_default_context()
                with socket.create_connection((hostname, port), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                        cert = ssock.getpeercert()
                        # 简单检查有效期
                        return {
                            "ssl_valid": True,
                            "issuer": cert.get('issuer', 'Unknown')
                        }
        except Exception as e:
            return {"ssl_valid": False, "error": str(e)}
        return {"ssl_valid": True}
    
    def run(self):
        """运行监控检查"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始监控 {len(self.sites.get('sites', []))} 个站点...")
        
        for site in self.sites.get('sites', []):
            if not site.get('enabled', True):
                continue
            
            result = self.check_site(site)
            self.results.append(result)
            
            # 打印状态
            status_icon = "✅" if result['status'] == 'up' else "❌"
            print(f"  {status_icon} {result['site']}: {result['status']} ({result['response_time']}ms)")
            
            # 如果宕机，记录告警
            if result['status'] == 'down':
                self.log_alert(result)
        
        # 保存结果
        self.save_results()
        return self.results
    
    def log_alert(self, result):
        """记录告警并发送钉钉通知"""
        alert = {
            "type": "site_down",
            "site": result['site'],
            "url": result['url'],
            "timestamp": result['timestamp'],
            "error": result.get('error', 'Unknown')
        }
        
        try:
            with open(ALERT_LOG, 'a') as f:
                f.write(json.dumps(alert, ensure_ascii=False) + '\n')
            print(f"  ⚠️  告警已记录: {result['site']}")
            
            # 发送钉钉通知
            alerter.send_alert(
                result['site'],
                result['url'],
                result.get('error', 'Unknown')
            )
        except Exception as e:
            print(f"  ❌ 告警记录失败: {e}")
    
    def save_results(self):
        """保存监控结果"""
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "results": self.results
                }, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"保存结果失败: {e}")

if __name__ == "__main__":
    monitor = WebsiteMonitor()
    monitor.run()