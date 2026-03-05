#!/usr/bin/env python3
"""日志聚合平台 - 主入口"""
import sys
from pathlib import Path

# 确保可以导入同级模块
sys.path.insert(0, str(Path(__file__).parent))

from cli import main

if __name__ == "__main__":
    main()