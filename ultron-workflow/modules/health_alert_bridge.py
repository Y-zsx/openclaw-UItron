#!/usr/bin/env python3
"""
健康检查告警桥接器
将健康检查系统与告警API服务(端口18170)深度集成
"""
import os
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

WORKSPACE = '/root/.openclaw/workspace'
ALERT_API_URL = 'http://localhost:18170'
HEALTH_CHECK_LOG = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'
HEALTH_ALERT_CONFIG = f'{WORKSPACE}/ultron-workflow/config/health_alert_config.json'

# 默认检查项
DEFAULT_CHECKS = {
    'gateway': {
        'url': 'http://localhost:18789/',
        'expected_status': 200,
        'timeout': 5,
        'alert_level': 'critical'
    },
    'status_panel': {
        'url': 'http://localhost:8889/',
        'expected_status': 200,
        'timeout': 5,
        'alert_level': 'error'
    },
    'health_api': {
        'url': 'http://localhost:8890/health',
        'expected_status': 200,
        'timeout': 5,
        'alert_level': 'warning'
    },
    'alert_api': {
        'url': 'http://localhost:18170/health',
        'expected_status': 200,
        'timeout': 5,
        'alert_level': 'critical'
    },
    'browser': {
        'url': 'http://localhost:18800/json',
        'expected_status': 200,
        'timeout': 5,
        'alert_level': 'warning'
    }
}


class HealthAlertBridge:
    """健康检查与告警系统的桥接器"""
    
    def __init__(self):
        self.alert_api_url = ALERT_API_URL
        self.checks = self._load_config()
        self.last_alerts = {}  # 用于跟踪上次告警状态，避免重复
    
    def _load_config(self) -> Dict:
        """加载配置"""
        if os.path.exists(HEALTH_ALERT_CONFIG):
            with open(HEALTH_ALERT_CONFIG) as f:
                return json.load(f)
        return {'checks': DEFAULT_CHECKS, 'enabled': True}
    
    def _save_config(self):
        """保存配置"""
        os.makedirs(os.path.dirname(HEALTH_ALERT_CONFIG), exist_ok=True)
        with open(HEALTH_ALERT_CONFIG, 'w') as f:
            json.dump(self.checks, f, indent=2)
    
    def check_api_health(self) -> bool:
        """检查告警API是否可用"""
        try:
            resp = requests.get(f'{self.alert_api_url}/health', timeout=3)
            return resp.status_code == 200
        except:
            return False
    
    def check_service(self, name: str, config: Dict) -> Dict:
        """检查单个服务"""
        url = config.get('url', '')
        expected = config.get('expected_status', 200)
        timeout = config.get('timeout', 5)
        
        try:
            resp = requests.get(url, timeout=timeout)
            is_healthy = resp.status_code == expected
            
            return {
                'name': name,
                'healthy': is_healthy,
                'status_code': resp.status_code,
                'url': url,
                'error': None
            }
        except requests.exceptions.Timeout:
            return {
                'name': name,
                'healthy': False,
                'status_code': 0,
                'url': url,
                'error': 'Timeout'
            }
        except Exception as e:
            return {
                'name': name,
                'healthy': False,
                'status_code': 0,
                'url': url,
                'error': str(e)
            }
    
    def send_alert(self, service_name: str, check_result: Dict, level: str) -> Optional[Dict]:
        """发送告警到API"""
        alert_data = {
            'rule_id': f'health_check_{service_name}',
            'rule_name': f'健康检查: {service_name}',
            'service_name': 'health-monitor',
            'level': level,
            'message': f"服务 {service_name} 不可用: {check_result.get('error', 'Unknown error')}",
            'value': check_result.get('status_code', 0),
            'threshold': 200,
            'labels': {
                'service': service_name,
                'check_type': 'http_health'
            },
            'annotations': {
                'url': check_result.get('url', ''),
                'checked_at': datetime.now().isoformat()
            }
        }
        
        try:
            resp = requests.post(
                f'{self.alert_api_url}/alerts',
                json=alert_data,
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"发送告警失败: {e}")
        
        return None
    
    def resolve_alert(self, service_name: str) -> bool:
        """解决告警"""
        # 查找该服务的未解决告警
        try:
            resp = requests.get(
                f'{self.alert_api_url}/alerts',
                params={'status': 'firing', 'service': 'health-monitor'},
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                for alert in data.get('alerts', []):
                    labels = alert.get('labels', {})
                    if labels.get('service') == service_name:
                        # 发送解决请求
                        resolve_resp = requests.post(
                            f"{self.alert_api_url}/alerts/{alert['id']}/resolve",
                            json={'message': '健康检查恢复'},
                            timeout=5
                        )
                        return resolve_resp.status_code == 200
        except:
            pass
        
        return False
    
    def run_check(self, alert_on_failure: bool = True, resolve_on_recovery: bool = True) -> Dict:
        """执行健康检查并发送告警"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'api_available': self.check_api_health(),
            'checks': [],
            'alerts_sent': [],
            'alerts_resolved': []
        }
        
        # 执行所有检查
        checks_config = self.checks.get('checks', DEFAULT_CHECKS)
        for name, config in checks_config.items():
            result = self.check_service(name, config)
            results['checks'].append(result)
        
        # 统计
        total = len(results['checks'])
        healthy = sum(1 for c in results['checks'] if c['healthy'])
        results['summary'] = {
            'total': total,
            'healthy': healthy,
            'unhealthy': total - healthy,
            'status': 'healthy' if healthy == total else 'degraded'
        }
        
        # 发送告警或解决告警
        if results['api_available']:
            for check in results['checks']:
                service_name = check['name']
                was_healthy = self.last_alerts.get(service_name, True)
                is_healthy = check['healthy']
                
                if not is_healthy and was_healthy:
                    # 刚变为不健康，发送告警
                    if alert_on_failure:
                        level = checks_config.get(service_name, {}).get('alert_level', 'error')
                        alert_result = self.send_alert(service_name, check, level)
                        if alert_result:
                            results['alerts_sent'].append({
                                'service': service_name,
                                'alert_id': alert_result.get('alert', {}).get('id')
                            })
                    self.last_alerts[service_name] = False
                
                elif is_healthy and not was_healthy:
                    # 刚恢复，解决告警
                    if resolve_on_recovery:
                        if self.resolve_alert(service_name):
                            results['alerts_resolved'].append(service_name)
                    self.last_alerts[service_name] = True
        
        # 保存检查日志
        self._save_log(results)
        
        return results
    
    def _save_log(self, results: Dict):
        """保存检查日志"""
        os.makedirs(os.path.dirname(HEALTH_CHECK_LOG), exist_ok=True)
        
        # 加载现有日志
        logs = []
        if os.path.exists(HEALTH_CHECK_LOG):
            try:
                with open(HEALTH_CHECK_LOG) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        logs = data
                    else:
                        logs = [data]
            except:
                logs = []
        
        logs.append(results)
        
        # 只保留最近100条
        if len(logs) > 100:
            logs = logs[-100:]
        
        with open(HEALTH_CHECK_LOG, 'w') as f:
            json.dump(logs, f, indent=2)
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            'api_available': self.check_api_health(),
            'last_alerts': self.last_alerts,
            'configured_checks': list(self.checks.get('checks', DEFAULT_CHECKS).keys())
        }
    
    def add_check(self, name: str, config: Dict):
        """添加检查项"""
        self.checks.setdefault('checks', {})[name] = config
        self._save_config()
    
    def remove_check(self, name: str):
        """移除检查项"""
        if 'checks' in self.checks and name in self.checks['checks']:
            del self.checks['checks'][name]
            self._save_config()


def main():
    """CLI入口"""
    import sys
    
    bridge = HealthAlertBridge()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == 'check':
            # 执行检查
            result = bridge.run_check()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == 'status':
            # 查看状态
            status = bridge.get_status()
            print(json.dumps(status, indent=2, ensure_ascii=False))
        
        elif cmd == 'add':
            # 添加检查项
            if len(sys.argv) > 3:
                name = sys.argv[2]
                config = json.loads(sys.argv[3])
                bridge.add_check(name, config)
                print(f"添加检查项: {name}")
            else:
                print("用法: add <name> <config_json>")
        
        elif cmd == 'remove':
            # 移除检查项
            if len(sys.argv) > 2:
                name = sys.argv[2]
                bridge.remove_check(name)
                print(f"移除检查项: {name}")
            else:
                print("用法: remove <name>")
        
        elif cmd == 'run':
            # 持续运行模式
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            print(f"启动健康检查桥接器，间隔 {interval} 秒...")
            while True:
                try:
                    result = bridge.run_check()
                    status = result['summary']['status']
                    unhealthy = result['summary']['unhealthy']
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 检查完成: {status} ({unhealthy}个异常)")
                except Exception as e:
                    print(f"检查异常: {e}")
                time.sleep(interval)
        
        else:
            print(f"未知命令: {cmd}")
            print("可用命令: check, status, add, remove, run")
    else:
        # 默认执行检查
        result = bridge.run_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()