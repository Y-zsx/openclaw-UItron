#!/usr/bin/env python3
"""
决策引擎自动化调度器
Automatic Scheduler for Decision Engine
周期性收集系统指标、触发决策评估、发送告警
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import threading
import requests
import json

logger = logging.getLogger(__name__)


class DecisionScheduler:
    """
    决策引擎自动化调度器
    - 定期收集系统指标
    - 触发决策引擎进行评估
    - 根据决策结果触发告警
    """
    
    def __init__(self, decision_engine_url: str = "http://localhost:18120", 
                 check_interval: int = 60,
                 alert_callback: Optional[Callable] = None):
        self.decision_engine_url = decision_engine_url
        self.check_interval = check_interval  # 秒
        self.alert_callback = alert_callback
        self.running = False
        self._thread = None
        self.stats = {
            "checks": 0,
            "decisions_made": 0,
            "alerts_sent": 0,
            "errors": 0,
            "last_check": None,
            "last_alert": None
        }
        
    def _collect_system_metrics(self) -> Dict[str, Any]:
        """收集系统指标"""
        metrics = {}
        
        try:
            # CPU使用率
            with open('/proc/loadavg', 'r') as f:
                load = f.read().split()[:3]
                metrics['cpu_load'] = [float(x) for x in load]
                # 简单估算CPU使用率
                metrics['cpu'] = min(100, float(load[0]) * 25)
        except Exception as e:
            logger.warning(f"CPU指标收集失败: {e}")
            metrics['cpu'] = 0
            
        try:
            # 内存使用率
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                total = int([x for x in meminfo.split('\n') if x.startswith('MemTotal:')][0].split()[1])
                available = int([x for x in meminfo.split('\n') if x.startswith('MemAvailable:')][0].split()[1])
                if total > 0:
                    metrics['memory'] = round((1 - available/total) * 100, 1)
        except Exception as e:
            logger.warning(f"内存指标收集失败: {e}")
            metrics['memory'] = 0
            
        try:
            # 磁盘使用率
            import shutil
            usage = shutil.disk_usage('/')
            metrics['disk'] = round((usage.used / usage.total) * 100, 1)
        except Exception as e:
            logger.warning(f"磁盘指标收集失败: {e}")
            metrics['disk'] = 0
            
        # 决策引擎服务健康状态
        try:
            resp = requests.get(f"{self.decision_engine_url}/health", timeout=5)
            metrics['decision_engine_status'] = 'ok' if resp.status_code == 200 else 'error'
        except:
            metrics['decision_engine_status'] = 'unavailable'
            
        # 时间戳
        metrics['_timestamp'] = datetime.now().isoformat()
        
        return metrics
    
    def _collect_additional_metrics(self) -> Dict[str, Any]:
        """收集额外指标"""
        metrics = {}
        
        # 网络连接数
        try:
            result = subprocess.run(
                ['ss', '-tln'],
                capture_output=True, text=True, timeout=5
            )
            metrics['network_connections'] = len([x for x in result.stdout.split('\n') if ':' in x])
        except:
            metrics['network_connections'] = 0
            
        # 进程数
        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True, text=True, timeout=5
            )
            metrics['process_count'] = len(result.stdout.split('\n')) - 1
        except:
            metrics['process_count'] = 0
            
        # 决策引擎统计
        try:
            resp = requests.get(f"{self.decision_engine_url}/stats", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                metrics['decision_stats'] = data
        except Exception as e:
            logger.debug(f"决策统计获取失败: {e}")
            
        return metrics
    
    def check_and_decide(self) -> Optional[Dict]:
        """收集指标并触发决策"""
        self.stats['checks'] += 1
        self.stats['last_check'] = datetime.now().isoformat()
        
        try:
            # 收集系统指标
            metrics = self._collect_system_metrics()
            additional = self._collect_additional_metrics()
            metrics.update(additional)
            
            logger.info(f"系统指标: CPU={metrics.get('cpu')}% MEM={metrics.get('memory')}% DISK={metrics.get('disk')}%")
            
            # 调用决策引擎进行风险评估
            try:
                resp = requests.post(
                    f"{self.decision_engine_url}/risk",
                    json={"metrics": metrics},
                    timeout=10
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    risk_data = result.get('risk_assessment', {})
                    
                    logger.info(f"风险评估: {risk_data.get('overall_level')} (score: {risk_data.get('risk_score')})")
                    
                    # 如果有风险，触发告警
                    if risk_data.get('overall_level') != 'low':
                        alerts = risk_data.get('risks', [])
                        for alert in alerts:
                            self._send_alert(alert, metrics)
                    
                    # 触发决策引擎评估
                    decide_resp = requests.post(
                        f"{self.decision_engine_url}/decide",
                        json={
                            "trigger": "scheduler",
                            "source": "auto-scheduler",
                            "context": metrics
                        },
                        timeout=10
                    )
                    
                    if decide_resp.status_code == 200:
                        decision_result = decide_resp.json()
                        if decision_result.get('success'):
                            self.stats['decisions_made'] += 1
                            logger.info(f"决策: {decision_result.get('decision', {}).get('action')}")
                            
                    return {
                        "metrics": metrics,
                        "risk": risk_data,
                        "timestamp": datetime.now().isoformat()
                    }
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"决策引擎调用失败: {e}")
                self.stats['errors'] += 1
                
        except Exception as e:
            logger.error(f"指标收集失败: {e}")
            self.stats['errors'] += 1
            
        return None
    
    def _send_alert(self, alert: Dict, metrics: Dict):
        """发送告警"""
        self.stats['alerts_sent'] += 1
        self.stats['last_alert'] = datetime.now().isoformat()
        
        alert_msg = {
            "type": alert.get('type'),
            "level": alert.get('level'),
            "value": alert.get('value'),
            "threshold": alert.get('threshold'),
            "severity": alert.get('severity'),
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "cpu": metrics.get('cpu'),
                "memory": metrics.get('memory'),
                "disk": metrics.get('disk')
            }
        }
        
        logger.warning(f"🚨 告警: {alert_msg}")
        
        # 调用告警回调
        if self.alert_callback:
            try:
                self.alert_callback(alert_msg)
            except Exception as e:
                logger.error(f"告警回调失败: {e}")
        
        # 尝试通过决策引擎的notify动作发送
        try:
            requests.post(
                f"{self.decision_engine_url}/execute",
                json={
                    "action": "notify",
                    "context": alert_msg
                },
                timeout=5
            )
        except Exception as e:
            logger.debug(f"决策引擎通知失败: {e}")
    
    def run(self):
        """运行调度器"""
        logger.info(f"启动决策调度器: 间隔={self.check_interval}秒")
        
        while self.running:
            try:
                self.check_and_decide()
            except Exception as e:
                logger.error(f"调度循环错误: {e}")
                
            # 等待下一个周期
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def start(self):
        """启动调度器（后台线程）"""
        if self.running:
            return
            
        self.running = True
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        logger.info("决策调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("决策调度器已停止")
    
    def get_stats(self) -> Dict:
        """获取调度器统计"""
        return self.stats.copy()


# DingTalk告警集成
class DingTalkAlert:
    """钉钉告警发送器"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
        self.enabled = webhook_url is not None
        
    def send(self, title: str, content: str, level: str = "info") -> bool:
        """发送告警到钉钉"""
        if not self.enabled:
            logger.info(f"[DingTalk模拟] {title}: {content}")
            return True
            
        # 告警级别映射到颜色
        colors = {
            "critical": "FF0000",
            "high": "FF6600", 
            "medium": "FFCC00",
            "low": "00CC00",
            "info": "000000"
        }
        
        color = colors.get(level, "000000")
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{content}\n\n> 来自 **奥创决策引擎** 🦞"
            }
        }
        
        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"钉钉告警发送失败: {e}")
            return False


def main():
    """测试入口"""
    import sys
    
    # 创建调度器
    scheduler = DecisionScheduler(
        decision_engine_url="http://localhost:18120",
        check_interval=30
    )
    
    # 立即执行一次检查
    result = scheduler.check_and_decide()
    if result:
        print(f"✓ 检查完成: {result}")
    else:
        print("✗ 检查失败")
    
    print(f"统计: {scheduler.get_stats()}")


if __name__ == '__main__':
    main()