#!/usr/bin/env python3
"""
协作网络监控面板CLI工具
用法:
    python3 dashboard_cli.py          # 生成面板
    python3 dashboard_cli.py --watch  # 监听模式(每分钟更新)
    python3 dashboard_cli.py --serve  # 启动HTTP服务器
"""
import argparse
import time
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from agents.collaboration_dashboard import CollaborationDashboard

def generate():
    """生成监控面板"""
    dashboard = CollaborationDashboard()
    dashboard.save()
    print(f"✅ 面板已更新: {Path(__file__).parent / 'collaboration_dashboard.html'}")

def watch(interval=60):
    """监听模式 - 定期更新"""
    print(f"🔄 监听模式已启动 (每{interval}秒更新)")
    while True:
        generate()
        time.sleep(interval)

def serve(port=8080):
    """启动HTTP服务器"""
    import http.server
    import socketserver
    from pathlib import Path
    
    # 先生成面板
    generate()
    
    html_dir = Path(__file__).parent
    os.chdir(html_dir)
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()
    
    print(f"🚀 HTTP服务器已启动: http://localhost:{port}/collaboration_dashboard.html")
    print(f"📁 目录: {html_dir}")
    print("按 Ctrl+C 停止")
    
    with socketserver.TCPServer(("", port), Handler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="协作网络监控面板CLI")
    parser.add_argument("--watch", action="store_true", help="监听模式")
    parser.add_argument("--serve", action="store_true", help="启动HTTP服务器")
    parser.add_argument("--interval", type=int, default=60, help="监听间隔(秒)")
    parser.add_argument("--port", type=int, default=8080, help="HTTP服务器端口")
    
    args = parser.parse_args()
    
    if args.watch:
        watch(args.interval)
    elif args.serve:
        serve(args.port)
    else:
        generate()