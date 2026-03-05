#!/usr/bin/env python3
"""
系统日志分析器
完善系统日志分析功能 - 第158世任务
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

LOG_DIR = Path(__file__).parent

class LogAnalyzer:
    def __init__(self, log_dir=LOG_DIR):
        self.log_dir = Path(log_dir)
        self.analysis = {
            "timestamp": datetime.now().isoformat(),
            "logs_analyzed": [],
            "summary": {},
            "alerts": [],
            "metrics": {}
        }
    
    def analyze_all_logs(self):
        """分析所有日志文件"""
        log_files = list(self.log_dir.glob("*.log")) + list(self.log_dir.glob("*.json"))
        
        for log_file in log_files:
            try:
                self.analyze_file(log_file)
            except Exception as e:
                print(f"分析 {log_file.name} 失败: {e}")
        
        return self.analysis
    
    def analyze_file(self, file_path):
        """分析单个日志文件"""
        stats = {
            "file": file_path.name,
            "size_bytes": file_path.stat().st_size,
            "line_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    stats["line_count"] += 1
                    line_lower = line.lower()
                    if "error" in line_lower or "failed" in line_lower:
                        stats["error_count"] += 1
                    elif "warning" in line_lower or "warn" in line_lower:
                        stats["warning_count"] += 1
                    elif "info" in line_lower:
                        stats["info_count"] += 1
        except Exception as e:
            stats["error"] = str(e)
        
        self.analysis["logs_analyzed"].append(stats)
        
        # 汇总统计
        self.analysis["summary"][file_path.name] = {
            "lines": stats["line_count"],
            "errors": stats["error_count"],
            "warnings": stats["warning_count"]
        }
        
        # 告警
        if stats["error_count"] > 0:
            self.analysis["alerts"].append({
                "file": file_path.name,
                "type": "error",
                "count": stats["error_count"]
            })
    
    def get_system_health(self):
        """获取系统健康状态"""
        total_errors = sum(s.get("errors", 0) for s in self.analysis["logs_analyzed"])
        total_warnings = sum(s.get("warnings", 0) for s in self.analysis["logs_analyzed"])
        
        if total_errors > 10:
            status = "critical"
        elif total_errors > 5 or total_warnings > 20:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "logs_count": len(self.analysis["logs_analyzed"])
        }
    
    def generate_report(self):
        """生成分析报告"""
        health = self.get_system_health()
        self.analysis["metrics"] = health
        
        # 保存报告
        report_file = self.log_dir / "analysis_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis, f, indent=2, ensure_ascii=False)
        
        return {
            "health": health,
            "report_file": str(report_file),
            "logs_analyzed": len(self.analysis["logs_analyzed"])
        }


def main():
    """主函数"""
    analyzer = LogAnalyzer()
    analyzer.analyze_all_logs()
    report = analyzer.generate_report()
    
    print(f"日志分析完成!")
    print(f"健康状态: {report['health']['status']}")
    print(f"错误数: {report['health']['total_errors']}")
    print(f"警告数: {report['health']['total_warnings']}")
    print(f"分析日志数: {report['logs_analyzed']}")
    print(f"报告文件: {report['report_file']}")
    
    return report


if __name__ == "__main__":
    main()