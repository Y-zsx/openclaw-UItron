"""日志收集器 - LogCollector 类"""
import json
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from config import LOG_ROOT, LOG_LEVELS


class LogCollector:
    """日志收集器 - 结构化JSON日志实时写入"""
    
    def __init__(self, buffer_size: int = 100, flush_interval: float = 1.0):
        """
        初始化日志收集器
        
        Args:
            buffer_size: 缓冲区大小，达到后自动刷新
            flush_interval: 自动刷新间隔(秒)
        """
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self._buffer = []
        self._lock = Lock()
        self._module_files = {}  # 模块 -> 文件对象缓存
        
        # 配置日志格式
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
    def _get_log_file(self, module: str) -> Path:
        """获取模块今天的日志文件路径"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_dir = LOG_ROOT / module
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{today}.log"
    
    def _write_log(self, log_entry: dict):
        """写入单条日志到文件"""
        module = log_entry["module"]
        log_file = self._get_log_file(module)
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def add_log(
        self,
        module: str,
        level: str,
        message: str,
        data: Optional[dict] = None
    ) -> bool:
        """
        添加日志条目
        
        Args:
            module: 模块名称
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: 日志消息
            data: 额外数据 (可选)
            
        Returns:
            bool: 是否成功添加
        """
        if level not in LOG_LEVELS:
            level = "INFO"
            
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "module": module,
            "level": level,
            "message": message,
            "data": data or {}
        }
        
        try:
            self._write_log(log_entry)
            return True
        except Exception as e:
            self.logger.error(f"写入日志失败: {e}")
            return False
    
    def add_decision_log(
        self,
        module: str,
        decision_id: str,
        input_data: dict,
        output_data: dict,
        status: str,
        duration_ms: Optional[float] = None
    ):
        """添加决策日志 (便捷方法)"""
        data = {
            "decision_id": decision_id,
            "input": input_data,
            "output": output_data,
            "status": status,
            "duration_ms": duration_ms
        }
        level = "ERROR" if status == "failed" else "INFO"
        self.add_log(module, level, f"Decision {decision_id}: {status}", data)
    
    def add_metric_log(
        self,
        module: str,
        metric_name: str,
        value: float,
        tags: Optional[dict] = None
    ):
        """添加指标日志 (便捷方法)"""
        data = {
            "metric_name": metric_name,
            "value": value,
            "tags": tags or {}
        }
        self.add_log(module, "INFO", f"Metric: {metric_name}={value}", data)


# 全局单例
_default_collector: Optional[LogCollector] = None


def get_collector() -> LogCollector:
    """获取默认日志收集器实例"""
    global _default_collector
    if _default_collector is None:
        _default_collector = LogCollector()
    return _default_collector


if __name__ == "__main__":
    # 测试
    collector = LogCollector()
    collector.add_log("decision_engine", "INFO", "测试日志", {"test": True})
    collector.add_decision_log(
        "decision_engine",
        "dec_001",
        {"input": "test"},
        {"result": "ok"},
        "success",
        125.5
    )
    print("日志收集器测试完成")