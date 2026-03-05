#!/usr/bin/env python3
"""
告警存储模块 - 自动记录告警历史
"""

import json
import os
from datetime import datetime
from pathlib import Path

ALERT_DIR = Path(__file__).parent
ALERT_INDEX = ALERT_DIR / "alerts_index.json"
ALERT_ARCHIVE = ALERT_DIR / "alerts"

# 确保目录存在
ALERT_ARCHIVE.mkdir(exist_ok=True)

class AlertStore:
    def __init__(self):
        self.alerts = self.load_index()
    
    def load_index(self):
        """加载告警索引"""
        if ALERT_INDEX.exists():
            try:
                with open(ALERT_INDEX, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"alerts": [], "stats": {}}
        return {"alerts": [], "stats": {}}
    
    def save_index(self):
        """保存告警索引"""
        with open(ALERT_INDEX, 'w', encoding='utf-8') as f:
            json.dump(self.alerts, f, ensure_ascii=False, indent=2)
    
    def add(self, alert_type, site, url, error, severity="error"):
        """添加告警"""
        alert = {
            "id": f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": alert_type,
            "site": site,
            "url": url,
            "error": error,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "status": "active"
        }
        
        # 添加到索引
        self.alerts["alerts"].insert(0, alert)
        
        # 限制保留最近1000条
        if len(self.alerts["alerts"]) > 1000:
            self.alerts["alerts"] = self.alerts["alerts"][:1000]
        
        # 更新统计
        stats = self.alerts.get("stats", {})
        stats[alert_type] = stats.get(alert_type, 0) + 1
        self.alerts["stats"] = stats
        
        self.save_index()
        return alert
    
    def get_recent(self, limit=50):
        """获取最近告警"""
        return self.alerts["alerts"][:limit]
    
    def get_stats(self):
        """获取统计信息"""
        stats = self.alerts.get("stats", {})
        return {
            "total": len(self.alerts["alerts"]),
            "by_type": stats,
            "last_updated": self.alerts.get("last_updated", "N/A")
        }
    
    def clear(self):
        """清空告警"""
        self.alerts = {"alerts": [], "stats": {}}
        self.save_index()

if __name__ == "__main__":
    store = AlertStore()
    
    # 测试添加告警
    alert = store.add("site_down", "测试站点", "https://test.com", "Connection timeout", "error")
    print(f"✅ 添加告警: {alert['id']}")
    print(f"📊 统计: {store.get_stats()}")
    print(f"📋 最近告警: {store.get_recent(5)}")