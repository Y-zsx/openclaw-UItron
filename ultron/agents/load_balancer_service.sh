#!/bin/bash
# 负载均衡服务启动脚本

cd /root/.openclaw/workspace/ultron/agents

echo "🚀 启动负载均衡API服务..."
python3 load_balancer_api.py &
API_PID=$!

echo "✅ API服务启动 (PID: $API_PID, 端口: 8093)"
echo "📊 监控面板: file://$(pwd)/load_balancer_dashboard.html"
echo ""
echo "使用以下命令测试:"
echo "  python3 load_balancer_cli.py list"
echo "  python3 load_balancer_cli.py stats"
echo "  python3 load_balancer_cli.py register agent-1 --weight 100"
echo "  python3 load_balancer_cli.py select"
echo ""
echo "停止服务: kill $API_PID"