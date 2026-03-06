#!/usr/bin/env python3
"""日志服务代理 - 将18305端口请求转发到18235"""
import http.server
import urllib.request
import json

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        try:
            url = f"http://localhost:18235{path}"
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=10)
            self.send_response(resp.status)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(resp.read())
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            url = f"http://localhost:18235{self.path}"
            req = urllib.request.Request(url, data=body, method='POST')
            req.add_header('Content-Type', 'application/json')
            resp = urllib.request.urlopen(req, timeout=10)
            self.send_response(resp.status)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(resp.read())
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

if __name__ == "__main__":
    server = http.server.HTTPServer(('0.0.0.0', 18305), ProxyHandler)
    print("日志服务代理运行在18305端口")
    server.serve_forever()
