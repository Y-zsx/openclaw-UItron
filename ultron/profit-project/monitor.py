#!/usr/bin/env python3
"""
网站监控MVP - 核心监控模块 (并行优化版)
Website Monitoring SaaS - Core Monitor with Parallel Execution
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alerter

CONFIG_FILE = "sites.json"
LOG_FILE = "../logs/monitor.json"
ALERT_LOG = "../logs/alerts.json"

# 并行检查配置
MAX_WORKERS = 10  # 最大并行线程数

class WebsiteMonitor:
    def __init__(self):
        self.sites = self.load_config()
        self.results = []
        self.stats = {
            "total": 0,
            "up": 0,
            "down": 0,
            "by_category": {}
        }
        
    def load_config(self):
        """加载监控站点配置"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "sites": [
                    {"url": "https://www.baidu.com", "name": "百度", "category": "cn-search", "interval": 60, "enabled": True},
                    {"url": "https://www.taobao.com", "name": "淘宝", "category": "ecommerce-cn", "interval": 60, "enabled": True},
                    {"url": "https://httpbin.org/status/200", "name": "测试API", "category": "test", "interval": 30, "enabled": True}
                ]
            }
    
    def check_site(self, site):
        """检查单个站点"""
        url = site.get('url', '')
        name = site.get('name', url)
        category = site.get('category', 'unknown')
        
        result = {
            "site": name,
            "url": url,
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "status": "unknown",
            "response_time": 0,
            "status_code": None,
            "error": None
        }
        
        start_time = time.time()
        try:
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
                        return {"ssl_valid": True, "issuer": cert.get('issuer', 'Unknown')}
        except Exception as e:
            return {"ssl_valid": False, "error": str(e)}
        return {"ssl_valid": True}
    
    def run(self):
        """运行并行监控检查"""
        sites_list = self.sites.get('sites', [])
        enabled_sites = [s for s in sites_list if s.get('enabled', True)]
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始并行监控 {len(enabled_sites)} 个站点 (max workers: {MAX_WORKERS})...")
        
        self.results = []
        start_total = time.time()
        
        # 使用线程池并行检查
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_site = {executor.submit(self.check_site, site): site for site in enabled_sites}
            
            for future in as_completed(future_to_site):
                result = future.result()
                self.results.append(result)
                
                # 更新统计
                self.stats["total"] += 1
                if result['status'] == 'up':
                    self.stats["up"] += 1
                else:
                    self.stats["down"] += 1
                
                # 按分类统计
                cat = result.get('category', 'unknown')
                if cat not in self.stats["by_category"]:
                    self.stats["by_category"][cat] = {"up": 0, "down": 0, "total": 0}
                self.stats["by_category"][cat]["total"] += 1
                if result['status'] == 'up':
                    self.stats["by_category"][cat]["up"] += 1
                else:
                    self.stats["by_category"][cat]["down"] += 1
                
                # 打印状态
                status_icon = "✅" if result['status'] == 'up' else "❌"
                print(f"  {status_icon} [{cat}] {result['site']}: {result['status']} ({result['response_time']}ms)")
                
                # 如果宕机，记录告警
                if result['status'] == 'down':
                    self.log_alert(result)
        
        total_time = round(time.time() - start_total, 2)
        
        # 打印统计摘要
        print(f"\n📊 监控完成: 总计 {self.stats['total']} | ✅ {self.stats['up']} | ❌ {self.stats['down']} | 耗时 {total_time}s")
        
        # 打印分类统计
        print("\n📈 分类统计:")
        for cat, data in self.stats["by_category"].items():
            cat_name = self.sites.get('categories', {}).get(cat, {}).get('name', cat)
            up_rate = round(data["up"] / data["total"] * 100, 1) if data["total"] > 0 else 0
            print(f"  • {cat_name}: {data['up']}/{data['total']} ({up_rate}%)")
        
        # 保存结果
        self.save_results()
        return self.results
    
    def log_alert(self, result):
        """记录告警并发送钉钉通知"""
        alert = {
            "type": "site_down",
            "site": result['site'],
            "category": result.get('category', 'unknown'),
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
                    "stats": self.stats,
                    "results": self.results
                }, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"保存结果失败: {e}")

if __name__ == "__main__":
    monitor = WebsiteMonitor()
    monitor.run()