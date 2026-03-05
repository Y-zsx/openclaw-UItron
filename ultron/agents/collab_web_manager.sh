#!/bin/bash
# Agent协作网络Web管理界面CLI

PORT=${1:-8089}

cd /root/.openclaw/workspace/ultron/agents
python3 collab_web_manager.py &
echo "Web管理界面启动在端口 $PORT"