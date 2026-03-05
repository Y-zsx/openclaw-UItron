#!/usr/bin/env python3
"""故障预测Dashboard服务器 - 端口18239"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="/root/.openclaw/workspace/ultron", **kwargs)

if __name__ == '__main__':
    print("启动故障预测Dashboard: http://0.0.0.0:18239")
    server = HTTPServer(('0.0.0.0', 18239), Handler)
    server.serve_forever()