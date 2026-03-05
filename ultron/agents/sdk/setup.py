"""
Ultron Agent SDK
多智能体协作网络 Python SDK

安装方式:
  pip install ultron-agent-sdk
  或
  pip install -e .

环境变量:
  ULTRON_API_URL: API服务器地址 (默认: http://localhost:18789/api/v3)
  ULTRON_API_KEY: API密钥
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("__init__.py", "r", encoding="utf-8") as f:
    version = "__version__ = " + f.read().split('__version__ = "')[1].split('"')[0]

setup(
    name="ultron-agent-sdk",
    version="3.0.0",
    author="奥创 (Ultron)",
    description="Ultron Multi-Agent Collaboration Network SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "ultron=ultron_agent_sdk.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)