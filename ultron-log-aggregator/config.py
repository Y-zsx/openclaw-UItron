"""配置模块 - 日志聚合与分析平台配置"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent

# 日志存储根目录
LOG_ROOT = BASE_DIR / "logs"

# 日志保留天数
RETENTION_DAYS = 30

# 单个日志文件最大大小 (MB)
MAX_LOG_FILE_SIZE = 100

# 日志文件轮转数量
LOG_ROTATION_COUNT = 10

# 模块列表
MODULES = [
    "decision_engine",
    "rule_executor",
    "model_inference",
    "data_pipeline",
    "api_gateway"
]

# 日志级别
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# SQLite数据库路径
DB_PATH = BASE_DIR / "logs_index.db"

# 分析报告输出目录
REPORT_DIR = BASE_DIR / "reports"

def ensure_dirs():
    """确保必要的目录存在"""
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for module in MODULES:
        (LOG_ROOT / module).mkdir(parents=True, exist_ok=True)

# 初始化目录
ensure_dirs()