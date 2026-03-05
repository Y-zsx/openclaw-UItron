"""日志存储模块 - 日志轮转、保留策略、存储管理"""
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from config import (
    LOG_ROOT,
    RETENTION_DAYS,
    MAX_LOG_FILE_SIZE,
    LOG_ROTATION_COUNT,
    MODULES
)


class LogStorage:
    """日志存储管理 - 支持轮转和保留策略"""
    
    def __init__(self):
        self.log_root = LOG_ROOT
        self.retention_days = RETENTION_DAYS
        self.max_file_size = MAX_LOG_FILE_SIZE * 1024 * 1024  # MB -> bytes
        self.rotation_count = LOG_ROTATION_COUNT
        
    def get_module_log_dir(self, module: str) -> Path:
        """获取模块日志目录"""
        return self.log_root / module
    
    def get_log_files(self, module: str, date: Optional[str] = None) -> List[Path]:
        """
        获取模块的日志文件列表
        
        Args:
            module: 模块名称
            date: 日期字符串 (YYYY-MM-DD)，默认返回所有
            
        Returns:
            日志文件路径列表
        """
        module_dir = self.get_module_log_dir(module)
        if not module_dir.exists():
            return []
        
        if date:
            log_file = module_dir / f"{date}.log"
            return [log_file] if log_file.exists() else []
        
        return sorted(module_dir.glob("*.log"), reverse=True)
    
    def get_log_file_path(self, module: str, date: Optional[str] = None) -> Path:
        """
        获取日志文件路径
        
        Args:
            module: 模块名称
            date: 日期字符串 (YYYY-MM-DD)，默认今天
            
        Returns:
            日志文件路径
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return self.get_module_log_dir(module) / f"{date}.log"
    
    def rotate_log_file(self, module: str, date: str) -> bool:
        """
        执行日志文件轮转
        
        Args:
            module: 模块名称
            date: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            是否成功轮转
        """
        log_file = self.get_module_log_dir(module) / f"{date}.log"
        if not log_file.exists():
            return False
        
        try:
            # 检查是否需要轮转
            if log_file.stat().st_size < self.max_file_size:
                return False
            
            # 轮转旧文件
            for i in range(self.rotation_count - 1, 0, -1):
                old_file = self.get_module_log_dir(module) / f"{date}.log.{i}"
                new_file = self.get_module_log_dir(module) / f"{date}.log.{i + 1}"
                if old_file.exists():
                    old_file.rename(new_file)
            
            # 移动当前文件到.1
            rotated_file = self.get_module_log_dir(module) / f"{date}.log.1"
            log_file.rename(rotated_file)
            
            # 创建新文件
            log_file.touch()
            return True
            
        except Exception as e:
            print(f"日志轮转失败: {e}")
            return False
    
    def cleanup_old_logs(self, module: Optional[str] = None) -> int:
        """
        清理过期日志
        
        Args:
            module: 模块名称，默认所有模块
            
        Returns:
            清理的文件数量
        """
        if module:
            modules = [module]
        else:
            modules = MODULES
            
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        cleaned = 0
        
        for mod in modules:
            module_dir = self.get_module_log_dir(mod)
            if not module_dir.exists():
                continue
            
            for log_file in module_dir.glob("*.log*"):
                # 提取日期
                filename = log_file.name
                if filename.endswith(".log"):
                    date_str = filename.replace(".log", "")
                elif ".log." in filename:
                    date_str = filename.split(".log.")[0]
                else:
                    continue
                
                try:
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if file_date < cutoff_date:
                        log_file.unlink()
                        cleaned += 1
                except ValueError:
                    continue
        
        return cleaned
    
    def get_storage_stats(self, module: Optional[str] = None) -> dict:
        """
        获取存储统计信息
        
        Args:
            module: 模块名称，默认所有模块
            
        Returns:
            存储统计字典
        """
        if module:
            modules = [module]
        else:
            modules = MODULES
            
        stats = {
            "total_size": 0,
            "file_count": 0,
            "modules": {}
        }
        
        for mod in modules:
            module_dir = self.get_module_log_dir(mod)
            mod_stats = {
                "size": 0,
                "files": 0,
                "dates": []
            }
            
            if module_dir.exists():
                for log_file in module_dir.glob("*.log"):
                    size = log_file.stat().st_size
                    mod_stats["size"] += size
                    mod_stats["files"] += 1
                    mod_stats["dates"].append(log_file.stem)
            
            stats["modules"][mod] = mod_stats
            stats["total_size"] += mod_stats["size"]
            stats["file_count"] += mod_stats["files"]
        
        # 格式化大小
        stats["total_size_mb"] = round(stats["total_size"] / 1024 / 1024, 2)
        return stats
    
    def archive_logs(self, module: str, start_date: str, end_date: str, archive_path: Path) -> bool:
        """
        归档指定日期范围的日志
        
        Args:
            module: 模块名称
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            archive_path: 归档文件路径
            
        Returns:
            是否成功归档
        """
        import tarfile
        
        module_dir = self.get_module_log_dir(module)
        if not module_dir.exists():
            return False
        
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            
            # 收集需要归档的文件
            files_to_archive = []
            for log_file in module_dir.glob("*.log"):
                try:
                    file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
                    if start <= file_date <= end:
                        files_to_archive.append(log_file)
                except ValueError:
                    continue
            
            if not files_to_archive:
                return False
            
            # 创建归档
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path, "w:gz") as tar:
                for f in files_to_archive:
                    tar.add(f, arcname=f.name)
            
            return True
            
        except Exception as e:
            print(f"日志归档失败: {e}")
            return False


# 全局单例
_default_storage: Optional[LogStorage] = None


def get_storage() -> LogStorage:
    """获取默认存储实例"""
    global _default_storage
    if _default_storage is None:
        _default_storage = LogStorage()
    return _default_storage


if __name__ == "__main__":
    # 测试
    storage = LogStorage()
    
    # 存储统计
    stats = storage.get_storage_stats()
    print(f"总大小: {stats['total_size_mb']} MB")
    print(f"文件数: {stats['file_count']}")
    
    # 清理测试
    cleaned = storage.cleanup_old_logs()
    print(f"清理文件数: {cleaned}")