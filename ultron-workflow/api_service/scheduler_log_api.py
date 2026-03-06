#!/usr/bin/env python3
"""
调度任务执行日志分析 API 服务
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.scheduler_log_analyzer import SchedulerLogAnalyzer

PORT = 18155
ANALYSIS_FILE = Path("/root/.openclaw/workspace/ultron-workflow/logs/scheduler_log_analysis.json")


class LogAnalyzerAPI(BaseHTTPRequestHandler):
    """日志分析 API 处理器"""
    
    def do_GET(self):
        path = self.path
        
        if path == "/" or path == "/stats":
            self.send_json_response(self.get_stats())
        elif path == "/health":
            self.send_json_response({"status": "ok", "service": "scheduler-log-analyzer"})
        elif path == "/refresh":
            self.refresh_analysis()
            self.send_json_response({"status": "ok", "message": "Analysis refreshed"})
        else:
            self.send_error(404, "Not Found")
    
    def get_stats(self):
        """获取分析统计"""
        if ANALYSIS_FILE.exists():
            with open(ANALYSIS_FILE, 'r') as f:
                return json.load(f)
        return {"error": "No analysis data available"}
    
    def refresh_analysis(self):
        """刷新分析"""
        analyzer = SchedulerLogAnalyzer()
        analyzer.load_logs()
        analyzer.analyze()
        analyzer.save()
    
    def send_json_response(self, data):
        """发送 JSON 响应"""
        response = json.dumps(data, indent=2, ensure_ascii=False)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response.encode("utf-8"))
    
    def log_message(self, format, *args):
        """日志输出"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")


def main():
    """主函数"""
    # 先执行一次分析
    print("Initial analysis...")
    analyzer = SchedulerLogAnalyzer()
    analyzer.load_logs()
    analyzer.analyze()
    analyzer.save()
    
    # 启动 API 服务
    server = HTTPServer(("0.0.0.0", PORT), LogAnalyzerAPI)
    print(f"Scheduler Log Analyzer API running on port {PORT}")
    print(f"Endpoints:")
    print(f"  - http://localhost:{PORT}/stats  - Get analysis statistics")
    print(f"  - http://localhost:{PORT}/refresh - Refresh analysis")
    print(f"  - http://localhost:{PORT}/health - Health check")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()