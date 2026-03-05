#!/usr/bin/env python3
"""
合规检查系统
定期检查Agent操作的合规性
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from audit_logger import get_logger

class ComplianceChecker:
    """合规检查器"""
    
    def __init__(self):
        self.logger = get_logger()
        self.rules = self._load_rules()
    
    def _load_rules(self) -> List[Dict]:
        """加载合规规则"""
        return [
            {
                "id": "R001",
                "name": "认证失败监控",
                "description": "检测连续认证失败",
                "severity": "high",
                "threshold": 5,
                "window_minutes": 10,
                "check": self._check_auth_failures
            },
            {
                "id": "R002",
                "name": "异常API调用",
                "description": "检测异常API调用模式",
                "severity": "medium",
                "threshold": 100,
                "window_minutes": 5,
                "check": self._check_api_anomaly
            },
            {
                "id": "R003",
                "name": "数据访问审计",
                "description": "确保敏感数据访问被记录",
                "severity": "high",
                "check": self._check_data_access
            },
            {
                "id": "R004",
                "name": "任务完成率",
                "description": "监控任务完成情况",
                "severity": "low",
                "threshold": 0.8,
                "check": self._check_task_completion
            },
            {
                "id": "R005",
                "name": "通信加密",
                "description": "验证通信使用加密",
                "severity": "high",
                "check": self._check_encryption
            }
        ]
    
    def _check_auth_failures(self) -> Dict:
        """检查认证失败"""
        since = (datetime.now() - timedelta(minutes=10)).isoformat()
        logs = self.logger.query(event_type="AUTH", start_time=since, status="FAILURE", limit=1000)
        
        # 按agent分组
        failures = {}
        for log in logs:
            agent_id = log.get("agent_id", "unknown")
            failures[agent_id] = failures.get(agent_id, 0) + 1
        
        violations = []
        for agent_id, count in failures.items():
            if count >= 5:
                violations.append({
                    "agent_id": agent_id,
                    "failures": count,
                    "severity": "high"
                })
        
        return {
            "rule_id": "R001",
            "passed": len(violations) == 0,
            "violations": violations
        }
    
    def _check_api_anomaly(self) -> Dict:
        """检查API异常"""
        since = (datetime.now() - timedelta(minutes=5)).isoformat()
        logs = self.logger.query(event_type="API", start_time=since, limit=1000)
        
        # 按agent统计
        api_calls = {}
        for log in logs:
            agent_id = log.get("agent_id", "unknown")
            api_calls[agent_id] = api_calls.get(agent_id, 0) + 1
        
        violations = []
        for agent_id, count in api_calls.items():
            if count > 100:
                violations.append({
                    "agent_id": agent_id,
                    "api_calls": count,
                    "severity": "medium"
                })
        
        return {
            "rule_id": "R002",
            "passed": len(violations) == 0,
            "violations": violations
        }
    
    def _check_data_access(self) -> Dict:
        """检查数据访问审计"""
        # 检查是否有未记录的敏感操作
        recent = (datetime.now() - timedelta(hours=1)).isoformat()
        logs = self.logger.query(start_time=recent, limit=1000)
        
        # 检查是否有缺少checksum的记录
        missing_checksum = [log for log in logs if not log.get("checksum")]
        
        return {
            "rule_id": "R003",
            "passed": len(missing_checksum) == 0,
            "violations": [{"missing_checksum_count": len(missing_checksum)}] if missing_checksum else []
        }
    
    def _check_task_completion(self) -> Dict:
        """检查任务完成率"""
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        logs = self.logger.query(event_type="TASK", start_time=since, limit=1000)
        
        if not logs:
            return {"rule_id": "R004", "passed": True, "violations": []}
        
        completed = sum(1 for log in logs if log.get("status") == "SUCCESS")
        total = len(logs)
        rate = completed / total if total > 0 else 0
        
        return {
            "rule_id": "R004",
            "passed": rate >= 0.8,
            "completion_rate": rate,
            "violations": [] if rate >= 0.8 else [{"completion_rate": rate, "threshold": 0.8}]
        }
    
    def _check_encryption(self) -> Dict:
        """检查通信加密"""
        recent = (datetime.now() - timedelta(hours=1)).isoformat()
        comm_logs = self.logger.query(event_type="COMMUNICATION", start_time=recent, limit=1000)
        
        # 检查是否有details中包含encryption字段
        unencrypted = []
        for log in comm_logs:
            details = log.get("details")
            if details:
                try:
                    details_dict = json.loads(details)
                    if not details_dict.get("encrypted") and not details_dict.get("encryption"):
                        unencrypted.append(log["id"])
                except:
                    pass
        
        return {
            "rule_id": "R005",
            "passed": len(unencrypted) == 0,
            "violations": [{"unencrypted_count": len(unencrypted)}] if unencrypted else []
        }
    
    def run_all_checks(self) -> Dict:
        """运行所有合规检查"""
        results = []
        for rule in self.rules:
            try:
                result = rule["check"]()
                results.append(result)
            except Exception as e:
                results.append({
                    "rule_id": rule["id"],
                    "passed": False,
                    "error": str(e)
                })
        
        passed = sum(1 for r in results if r.get("passed", False))
        failed = len(results) - passed
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_rules": len(results),
            "passed": passed,
            "failed": failed,
            "results": results
        }


if __name__ == "__main__":
    checker = ComplianceChecker()
    results = checker.run_all_checks()
    print(json.dumps(results, indent=2, ensure_ascii=False))