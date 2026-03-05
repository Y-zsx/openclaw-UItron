"""日志分析模块 - 统计分析、模式识别、报表生成"""
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import LOG_ROOT, MODULES, REPORT_DIR


class LogAnalyzer:
    """日志分析器 - 统计分析、模式识别、报表生成"""
    
    def __init__(self):
        self.log_root = LOG_ROOT
        self.report_dir = REPORT_DIR
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def load_logs(
        self,
        module: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        level: Optional[str] = None
    ) -> List[Dict]:
        """
        加载日志条目
        
        Args:
            module: 模块名称
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            level: 日志级别过滤
            
        Returns:
            日志条目列表
        """
        module_dir = self.log_root / module
        if not module_dir.exists():
            return []
        
        # 确定日期范围
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        logs = []
        for log_file in module_dir.glob("*.log"):
            try:
                file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
                if not (start <= file_date <= end):
                    continue
            except ValueError:
                continue
            
            # 读取日志
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if level and entry.get("level") != level:
                            continue
                        logs.append(entry)
                    except json.JSONDecodeError:
                        continue
        
        return logs
    
    def calculate_stats(
        self,
        module: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        计算日志统计信息
        
        Args:
            module: 模块名称
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            统计结果字典
        """
        logs = self.load_logs(module, start_date, end_date)
        
        if not logs:
            return {
                "module": module,
                "total_count": 0,
                "by_level": {},
                "error_rate": 0,
                "avg_duration_ms": None
            }
        
        # 按级别统计
        level_counts = Counter(log.get("level", "INFO") for log in logs)
        
        # 计算错误率
        error_count = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
        error_rate = error_count / len(logs) * 100 if logs else 0
        
        # 提取耗时统计
        durations = []
        for log in logs:
            data = log.get("data", {})
            if isinstance(data, dict):
                duration = data.get("duration_ms")
                if duration is not None:
                    durations.append(float(duration))
        
        avg_duration = sum(durations) / len(durations) if durations else None
        
        # 成功率 (从决策日志中计算)
        success_count = 0
        total_decisions = 0
        for log in logs:
            data = log.get("data", {})
            if isinstance(data, dict) and "status" in data:
                total_decisions += 1
                if data.get("status") == "success":
                    success_count += 1
        
        success_rate = success_count / total_decisions * 100 if total_decisions > 0 else None
        
        return {
            "module": module,
            "total_count": len(logs),
            "by_level": dict(level_counts),
            "error_count": error_count,
            "error_rate": round(error_rate, 2),
            "success_rate": round(success_rate, 2) if success_rate is not None else None,
            "avg_duration_ms": round(avg_duration, 2) if avg_duration else None,
            "duration_samples": len(durations)
        }
    
    def detect_patterns(
        self,
        module: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        检测错误模式
        
        Args:
            module: 模块名称
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            模式识别结果
        """
        logs = self.load_logs(module, start_date, end_date, level="ERROR")
        
        patterns = {
            "error_count": len(logs),
            "common_messages": [],
            "error_sequences": [],
            "time_distribution": {}
        }
        
        if not logs:
            return patterns
        
        # 常见错误消息
        message_counter = Counter(log.get("message", "") for log in logs)
        patterns["common_messages"] = [
            {"message": msg, "count": count}
            for msg, count in message_counter.most_common(10)
        ]
        
        # 时间分布 (按小时)
        hour_counter = Counter()
        for log in logs:
            try:
                ts = datetime.fromisoformat(log.get("timestamp", ""))
                hour_counter[ts.hour] += 1
            except (ValueError, TypeError):
                continue
        
        patterns["time_distribution"] = {
            str(hour): count for hour, count in sorted(hour_counter.items())
        }
        
        # 检测重复错误序列
        error_sequences = []
        recent_errors = []
        for log in logs[:100]:  # 只检查最近100条
            msg = log.get("message", "")
            if msg:
                recent_errors.append(msg)
        
        # 查找连续重复
        if recent_errors:
            sequence = [recent_errors[0]]
            for msg in recent_errors[1:]:
                if msg == sequence[-1]:
                    sequence.append(msg)
                else:
                    if len(sequence) >= 3:
                        error_sequences.append({
                            "message": sequence[0],
                            "repeated": len(sequence)
                        })
                    sequence = [msg]
            
            if len(sequence) >= 3:
                error_sequences.append({
                    "message": sequence[0],
                    "repeated": len(sequence)
                })
        
        patterns["error_sequences"] = error_sequences[:5]
        
        return patterns
    
    def generate_report(
        self,
        module: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        生成分析报告
        
        Args:
            module: 模块名称
            start_date: 开始日期
            end_date: 结束日期
            format: 报告格式 (json/markdown)
            
        Returns:
            报告内容
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        # 收集统计信息
        stats = self.calculate_stats(module, start_date, end_date)
        patterns = self.detect_patterns(module, start_date, end_date)
        
        report = {
            "module": module,
            "period": {
                "start": start_date,
                "end": end_date
            },
            "generated_at": datetime.now().isoformat(),
            "statistics": stats,
            "patterns": patterns
        }
        
        # Markdown格式
        if format == "markdown":
            report["markdown"] = self._to_markdown(report)
        
        return report
    
    def _to_markdown(self, report: Dict) -> str:
        """转换为Markdown格式"""
        md = []
        md.append(f"# 日志分析报告: {report['module']}")
        md.append(f"\n**统计周期**: {report['period']['start']} ~ {report['period']['end']}")
        md.append(f"\n**生成时间**: {report['generated_at']}")
        
        # 统计
        stats = report["statistics"]
        md.append("\n## 统计概览")
        md.append(f"- 总日志数: {stats['total_count']}")
        md.append(f"- 错误率: {stats['error_rate']}%")
        
        if stats.get("success_rate"):
            md.append(f"- 成功率: {stats['success_rate']}%")
        
        if stats.get("avg_duration_ms"):
            md.append(f"- 平均响应时间: {stats['avg_duration_ms']}ms")
        
        # 级别分布
        md.append("\n### 日志级别分布")
        for level, count in stats.get("by_level", {}).items():
            md.append(f"- {level}: {count}")
        
        # 错误模式
        patterns = report["patterns"]
        if patterns.get("common_messages"):
            md.append("\n## 常见错误")
            for item in patterns["common_messages"][:5]:
                md.append(f"- {item['message']} (出现 {item['count']} 次)")
        
        return "\n".join(md)
    
    def save_report(
        self,
        module: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        format: str = "json"
    ) -> Path:
        """
        保存报告到文件
        
        Args:
            module: 模块名称
            start_date: 开始日期
            end_date: 结束日期
            format: 格式 (json/markdown)
            
        Returns:
            报告文件路径
        """
        report = self.generate_report(module, start_date, end_date, format)
        
        # 生成文件名
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        filename = f"{module}_{start_date}_{end_date}.{format}"
        report_path = self.report_dir / filename
        
        if format == "json":
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        else:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report.get("markdown", ""))
        
        return report_path


# 全局单例
_default_analyzer: Optional[LogAnalyzer] = None


def get_analyzer() -> LogAnalyzer:
    """获取默认分析器实例"""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = LogAnalyzer()
    return _default_analyzer


if __name__ == "__main__":
    # 测试
    analyzer = LogAnalyzer()
    stats = analyzer.calculate_stats("decision_engine")
    print(json.dumps(stats, indent=2, ensure_ascii=False))