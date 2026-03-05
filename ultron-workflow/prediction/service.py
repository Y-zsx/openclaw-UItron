#!/usr/bin/env python3
"""
预测分析API服务
端口: 18125
"""
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 直接导入，避免循环依赖
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prediction.predictor import PredictionEngine

# 全局预测引擎
engine = PredictionEngine()

class PredictionHandler(BaseHTTPRequestHandler):
    """HTTP请求处理"""
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == "/health":
            self.send_json({"status": "ok", "service": "prediction-api", "port": 18125})
            
        elif path == "/predict":
            metric = params.get("metric", ["default"])[0]
            steps = int(params.get("steps", [3])[0])
            model = params.get("model", ["exponential_smoothing"])[0]
            
            result = engine.predict_metric(metric, steps, model)
            self.send_json(result)
            
        elif path == "/stats":
            metric = params.get("metric", ["default"])[0]
            predictor = engine.get_or_create_predictor(metric)
            self.send_json(predictor.get_statistics())
            
        elif path == "/metrics":
            self.send_json({"metrics": list(engine.predictors.keys())})
            
        else:
            self.send_json({"error": "Not found"}, status=404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON"}, status=400)
            return
        
        if path == "/add":
            metric = data.get("metric", "default")
            value = data.get("value", 0)
            timestamp = data.get("timestamp")
            
            engine.add_metric_data(metric, float(value), timestamp)
            self.send_json({"status": "added", "metric": metric, "value": value})
            
        elif path == "/batch":
            metric = data.get("metric", "default")
            values = data.get("values", [])
            
            for item in values:
                val = item.get("value")
                ts = item.get("timestamp")
                if val is not None:
                    engine.add_metric_data(metric, float(val), ts)
                    
            self.send_json({"status": "batch_added", "count": len(values)})
            
        else:
            self.send_json({"error": "Not found"}, status=404)
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def log_message(self, format, *args):
        if args:
            logger.info(format % args)
        else:
            logger.info(format)


def start_server(port=18125):
    """启动服务器"""
    server = HTTPServer(('0.0.0.0', port), PredictionHandler)
    logger.info(f"🚀 预测分析服务启动: http://0.0.0.0:{port}")
    logger.info(f"   - GET  /health              健康检查")
    logger.info(f"   - GET  /predict?metric=xxx  预测接口")
    logger.info(f"   - GET  /stats?metric=xxx    统计信息")
    logger.info(f"   - POST /add                 添加数据点")
    logger.info(f"   - POST /batch               批量添加")
    
    # 添加一些初始数据用于演示
    cpu_values = [45, 52, 48, 55, 60, 58, 65, 70, 68, 75, 72, 80]
    for i, val in enumerate(cpu_values):
        engine.add_metric_data("cpu_usage", val)
    
    memory_values = [60, 62, 65, 63, 70, 68, 72, 75, 73, 78, 76, 80]
    for i, val in enumerate(memory_values):
        engine.add_metric_data("memory_usage", val)
        
    logger.info("   初始数据已加载: cpu_usage, memory_usage")
    
    server.serve_forever()


if __name__ == "__main__":
    start_server()