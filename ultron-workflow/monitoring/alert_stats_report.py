#!/usr/bin/env python3
"""
告警统计分析报表服务
端口: 18216
提供多维度统计分析报表
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sqlite3
import csv
import io

MONITORING_DIR = Path("/root/.openclaw/workspace/ultron-workflow/monitoring")
DB_FILE = MONITORING_DIR / "alert_integration.db"


class AlertStatsReporter:
    """告警统计分析报表"""
    
    def __init__(self):
        pass
    
    def _get_conn(self):
        """获取数据库连接"""
        if not DB_FILE.exists():
            return None
        return sqlite3.connect(DB_FILE)
    
    def get_hourly_stats(self, hours=24):
        """获取按小时统计"""
        conn = self._get_conn()
        if not conn:
            return []
        
        c = conn.cursor()
        c.execute(f'''SELECT 
            strftime('%Y-%m-%d %H:00', timestamp) as hour,
            COUNT(*) as count,
            level
            FROM alert_history 
            WHERE timestamp >= datetime('now', '-{hours} hours')
            GROUP BY hour, level
            ORDER BY hour DESC''')
        
        rows = c.fetchall()
        conn.close()
        
        # 整理为时间线格式
        hourly = {}
        for row in rows:
            hour, count, level = row
            if hour not in hourly:
                hourly[hour] = {"hour": hour, "total": 0, "by_level": {}}
            hourly[hour]["total"] += count
            hourly[hour]["by_level"][level] = count
        
        return list(hourly.values())
    
    def get_daily_stats(self, days=7):
        """获取按天统计"""
        conn = self._get_conn()
        if not conn:
            return []
        
        c = conn.cursor()
        c.execute(f'''SELECT 
            strftime('%Y-%m-%d', timestamp) as day,
            COUNT(*) as count,
            level
            FROM alert_history 
            WHERE timestamp >= datetime('now', '-{days} days')
            GROUP BY day, level
            ORDER BY day DESC''')
        
        rows = c.fetchall()
        conn.close()
        
        daily = {}
        for row in rows:
            day, count, level = row
            if day not in daily:
                daily[day] = {"day": day, "total": 0, "by_level": {}}
            daily[day]["total"] += count
            daily[day]["by_level"][level] = count
        
        return list(daily.values())
    
    def get_trend_analysis(self, hours=24):
        """获取趋势分析"""
        conn = self._get_conn()
        if not conn:
            return {"trend": "stable", "change_rate": 0}
        
        c = conn.cursor()
        
        # 前半段
        c.execute(f'''SELECT COUNT(*) FROM alert_history 
            WHERE timestamp >= datetime('now', '-{hours} hours')
            AND timestamp < datetime('now', '-{hours//2} hours')''')
        first_half = c.fetchone()[0]
        
        # 后半段
        c.execute(f'''SELECT COUNT(*) FROM alert_history 
            WHERE timestamp >= datetime('now', '-{hours//2} hours')''')
        second_half = c.fetchone()[0]
        
        conn.close()
        
        if first_half == 0:
            change_rate = 100 if second_half > 0 else 0
        else:
            change_rate = round((second_half - first_half) / first_half * 100, 1)
        
        if change_rate > 20:
            trend = "increasing"
        elif change_rate < -20:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "change_rate": change_rate,
            "first_half": first_half,
            "second_half": second_half,
            "period_hours": hours
        }
    
    def get_channel_success_rate(self):
        """获取渠道成功率"""
        conn = self._get_conn()
        if not conn:
            return []
        
        c = conn.cursor()
        c.execute('''SELECT 
            channel,
            status,
            COUNT(*) as count
            FROM alert_history 
            GROUP BY channel, status''')
        
        rows = c.fetchall()
        conn.close()
        
        # 按渠道汇总
        channel_stats = {}
        for row in rows:
            channel, status, count = row
            if channel not in channel_stats:
                channel_stats[channel] = {"channel": channel, "total": 0, "success": 0, "failed": 0}
            channel_stats[channel]["total"] += count
            if status == "ok":
                channel_stats[channel]["success"] = count
            else:
                channel_stats[channel]["failed"] = count
        
        # 计算成功率
        result = []
        for ch, data in channel_stats.items():
            success_rate = round(data["success"] / data["total"] * 100, 1) if data["total"] > 0 else 0
            result.append({
                "channel": data["channel"],
                "total": data["total"],
                "success": data["success"],
                "failed": data["failed"],
                "success_rate": success_rate
            })
        
        return result
    
    def get_level_distribution(self):
        """获取告警级别分布"""
        conn = self._get_conn()
        if not conn:
            return []
        
        c = conn.cursor()
        c.execute('''SELECT 
            level,
            COUNT(*) as count,
            ROUND(CAST(COUNT(*) AS FLOAT) / (SELECT COUNT(*) FROM alert_history) * 100, 1) as percentage
            FROM alert_history 
            GROUP BY level''')
        
        rows = c.fetchall()
        conn.close()
        
        return [{"level": r[0], "count": r[1], "percentage": r[2]} for r in rows]
    
    def get_message_analysis(self, limit=10):
        """获取高频告警消息分析"""
        conn = self._get_conn()
        if not conn:
            return []
        
        c = conn.cursor()
        c.execute(f'''SELECT 
            message,
            COUNT(*) as count,
            level
            FROM alert_history 
            GROUP BY message
            ORDER BY count DESC
            LIMIT {limit}''')
        
        rows = c.fetchall()
        conn.close()
        
        return [{"message": r[0], "count": r[1], "level": r[2]} for r in rows]
    
    def get_summary_report(self):
        """获取汇总报表"""
        conn = self._get_conn()
        if not conn:
            return {"total": 0}
        
        c = conn.cursor()
        
        # 总数
        c.execute("SELECT COUNT(*) FROM alert_history")
        total = c.fetchone()[0]
        
        # 今日
        c.execute("SELECT COUNT(*) FROM alert_history WHERE date(timestamp) = date('now')")
        today = c.fetchone()[0]
        
        # 本周
        c.execute("SELECT COUNT(*) FROM alert_history WHERE timestamp >= datetime('now', '-7 days')")
        this_week = c.fetchone()[0]
        
        # 成功率
        c.execute("SELECT COUNT(*) FROM alert_history WHERE status = 'ok'")
        success = c.fetchone()[0]
        success_rate = round(success / total * 100, 1) if total > 0 else 0
        
        # 最新告警时间
        c.execute("SELECT MAX(timestamp) FROM alert_history")
        latest = c.fetchone()[0]
        
        conn.close()
        
        return {
            "total": total,
            "today": today,
            "this_week": this_week,
            "success_rate": success_rate,
            "latest_alert": latest
        }
    
    def export_csv(self, limit=100):
        """导出CSV格式"""
        conn = self._get_conn()
        if not conn:
            return ""
        
        c = conn.cursor()
        c.execute(f'''SELECT 
            id, alert_id, level, message, channel, status, timestamp
            FROM alert_history 
            ORDER BY timestamp DESC
            LIMIT {limit}''')
        
        rows = c.fetchall()
        conn.close()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Alert ID", "Level", "Message", "Channel", "Status", "Timestamp"])
        
        for row in rows:
            writer.writerow(row)
        
        return output.getvalue()


class AlertStatsHandler(BaseHTTPRequestHandler):
    """API处理器"""
    
    reporter = AlertStatsReporter()
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")
    
    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        if path == '/health':
            self.send_json(200, {
                "status": "ok",
                "service": "alert-stats-report",
                "port": 18216,
                "timestamp": datetime.now().isoformat()
            })
        
        elif path == '/api/summary':
            # 汇总报表
            report = self.reporter.get_summary_report()
            self.send_json(200, report)
        
        elif path == '/api/hourly':
            # 按小时统计
            hours = int(query.get('hours', [24])[0])
            data = self.reporter.get_hourly_stats(hours)
            self.send_json(200, {"hourly": data, "hours": hours})
        
        elif path == '/api/daily':
            # 按天统计
            days = int(query.get('days', [7])[0])
            data = self.reporter.get_daily_stats(days)
            self.send_json(200, {"daily": data, "days": days})
        
        elif path == '/api/trend':
            # 趋势分析
            hours = int(query.get('hours', [24])[0])
            trend = self.reporter.get_trend_analysis(hours)
            self.send_json(200, trend)
        
        elif path == '/api/channels':
            # 渠道成功率
            channels = self.reporter.get_channel_success_rate()
            self.send_json(200, {"channels": channels})
        
        elif path == '/api/levels':
            # 告警级别分布
            levels = self.reporter.get_level_distribution()
            self.send_json(200, {"levels": levels})
        
        elif path == '/api/messages':
            # 高频告警消息
            limit = int(query.get('limit', [10])[0])
            messages = self.reporter.get_message_analysis(limit)
            self.send_json(200, {"messages": messages})
        
        elif path == '/api/export':
            # 导出CSV
            limit = int(query.get('limit', [100])[0])
            csv_data = self.reporter.export_csv(limit)
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename=alert_history.csv')
            self.end_headers()
            self.wfile.write(csv_data.encode('utf-8'))
            return
        
        elif path == '/api/report':
            # 完整报表
            report = self.reporter.get_summary_report()
            hourly = self.reporter.get_hourly_stats(24)
            trend = self.reporter.get_trend_analysis(24)
            channels = self.reporter.get_channel_success_rate()
            levels = self.reporter.get_level_distribution()
            messages = self.reporter.get_message_analysis(10)
            
            self.send_json(200, {
                "summary": report,
                "hourly": hourly,
                "trend": trend,
                "channels": channels,
                "levels": levels,
                "top_messages": messages,
                "generated_at": datetime.now().isoformat()
            })
        
        elif path == '/':
            # 返回报表页面
            self.send_json(200, {
                "service": "alert-stats-report",
                "endpoints": [
                    "GET /health - 健康检查",
                    "GET /api/summary - 汇总统计",
                    "GET /api/hourly?hours=24 - 按小时统计",
                    "GET /api/daily?days=7 - 按天统计",
                    "GET /api/trend?hours=24 - 趋势分析",
                    "GET /api/channels - 渠道成功率",
                    "GET /api/levels - 告警级别分布",
                    "GET /api/messages - 高频告警消息",
                    "GET /api/report - 完整报表",
                    "GET /api/export?limit=100 - 导出CSV"
                ]
            })
        
        else:
            self.send_json(404, {"error": "Not found"})


def start_server(port=18216):
    server = HTTPServer(('0.0.0.0', port), AlertStatsHandler)
    print(f"📊 告警统计分析报表服务启动成功")
    print(f"   端口: {port}")
    print(f"   端点:")
    print(f"   - GET  /health           健康检查")
    print(f"   - GET  /api/summary      汇总统计")
    print(f"   - GET  /api/hourly       按小时统计")
    print(f"   - GET  /api/daily        按天统计")
    print(f"   - GET  /api/trend        趋势分析")
    print(f"   - GET  /api/channels     渠道成功率")
    print(f"   - GET  /api/levels       告警级别分布")
    print(f"   - GET  /api/messages     高频告警消息")
    print(f"   - GET  /api/report       完整报表")
    print(f"   - GET  /api/export       导出CSV")
    print(f"\n监听中...")
    server.serve_forever()


if __name__ == "__main__":
    start_server()