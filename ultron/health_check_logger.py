#!/usr/bin/env python3
"""
健康检查日志记录模块
功能：记录健康检查历史、提供日志查询和统计功能
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


class HealthCheckLogger:
    """健康检查日志记录器"""
    
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/logs/health_check_log.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_check_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                check_count INTEGER,
                total_services INTEGER,
                healthy_services INTEGER,
                unhealthy_services INTEGER,
                network_health REAL,
                details_json TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_status_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                port INTEGER,
                service_name TEXT,
                status TEXT,
                response_time_ms REAL,
                http_code INTEGER,
                error TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON health_check_logs(timestamp)
        """)
        
        # 为service_status_logs添加索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_service_timestamp ON service_status_logs(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_service_port ON service_status_logs(port)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_service_name ON service_status_logs(service_name)
        """)
        
        # 创建聚合表用于快速统计
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hourly_health_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour TEXT NOT NULL UNIQUE,
                total_checks INTEGER,
                avg_health REAL,
                min_health REAL,
                max_health REAL,
                healthy_count INTEGER,
                unhealthy_count INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _update_hourly_stats(self, timestamp: str):
        """更新小时聚合统计（减少查询计算）"""
        hour = timestamp[:13]  # 取小时
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取该小时的数据
        cursor.execute("""
            SELECT 
                COUNT(*) as total_checks,
                AVG(network_health) as avg_health,
                MIN(network_health) as min_health,
                MAX(network_health) as max_health,
                SUM(CASE WHEN unhealthy_services = 0 THEN 1 ELSE 0 END) as healthy_count,
                SUM(CASE WHEN unhealthy_services > 0 THEN 1 ELSE 0 END) as unhealthy_count
            FROM health_check_logs 
            WHERE timestamp LIKE ?
        """, (hour + "%",))
        
        row = cursor.fetchone()
        
        if row and row[0] > 0:
            cursor.execute("""
                INSERT OR REPLACE INTO hourly_health_stats 
                (hour, total_checks, avg_health, min_health, max_health, healthy_count, unhealthy_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (hour, row[0], row[1], row[2], row[3], row[4], row[5]))
        
        conn.commit()
        conn.close()
    
    def log_check(self, status: Dict):
        """记录健康检查结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = status.get("timestamp", datetime.now().isoformat())
        
        # 记录总体状态
        cursor.execute("""
            INSERT INTO health_check_logs 
            (timestamp, check_count, total_services, healthy_services, unhealthy_services, network_health, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            status.get("check_count", 0),
            status.get("total_services", 0),
            status.get("healthy_services", 0),
            status.get("unhealthy_services", 0),
            status.get("network_health", 0),
            json.dumps(status.get("details", {}))
        ))
        
        # 记录每个服务状态
        details = status.get("details", {})
        service_map = {
            8089: "api-gateway",
            8090: "secure-channel", 
            8091: "identity-auth",
            8095: "collaboration-scheduler",
            8096: "agent-task-executor",
            18232: "orchestration-dashboard"
        }
        
        service_records = []
        for port, result in details.items():
            service_records.append((
                timestamp,
                int(port),
                service_map.get(int(port), f"service-{port}"),
                result.get("status", "unknown"),
                result.get("response_time_ms"),
                result.get("http_code"),
                result.get("error")
            ))
        
        # 批量插入
        if service_records:
            cursor.executemany("""
                INSERT INTO service_status_logs
                (timestamp, port, service_name, status, response_time_ms, http_code, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, service_records)
        
        conn.commit()
        conn.close()
        
        # 异步更新小时聚合（后台执行）
        try:
            self._update_hourly_stats(timestamp)
        except:
            pass
        
        return True
    
    def log_check_batch(self, status_list: List[Dict]):
        """批量记录健康检查结果（提高写入性能）"""
        if not status_list:
            return True
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        health_records = []
        service_records = []
        service_map = {
            8089: "api-gateway", 8090: "secure-channel", 
            8091: "identity-auth", 8095: "collaboration-scheduler",
            8096: "agent-task-executor", 18232: "orchestration-dashboard"
        }
        
        for status in status_list:
            timestamp = status.get("timestamp", datetime.now().isoformat())
            health_records.append((
                timestamp,
                status.get("check_count", 0),
                status.get("total_services", 0),
                status.get("healthy_services", 0),
                status.get("unhealthy_services", 0),
                status.get("network_health", 0),
                json.dumps(status.get("details", {}))
            ))
            
            for port, result in status.get("details", {}).items():
                service_records.append((
                    timestamp,
                    int(port),
                    service_map.get(int(port), f"service-{port}"),
                    result.get("status", "unknown"),
                    result.get("response_time_ms"),
                    result.get("http_code"),
                    result.get("error")
                ))
        
        # 批量插入
        cursor.executemany("""
            INSERT INTO health_check_logs 
            (timestamp, check_count, total_services, healthy_services, unhealthy_services, network_health, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, health_records)
        
        if service_records:
            cursor.executemany("""
                INSERT INTO service_status_logs
                (timestamp, port, service_name, status, response_time_ms, http_code, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, service_records)
        
        conn.commit()
        conn.close()
        
        return True
    
    def get_recent_logs(self, hours: int = 1, limit: int = 100) -> List[Dict]:
        """获取最近的日志"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute("""
            SELECT * FROM health_check_logs 
            WHERE timestamp >= ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (since, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_statistics(self, hours: int = 24, use_cache: bool = True) -> Dict:
        """获取统计信息
        
        Args:
            hours: 统计时间范围
            use_cache: 是否使用预聚合缓存（加速大数据量查询）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 尝试使用预聚合缓存（针对>1小时的查询）
        if use_cache and hours >= 1:
            try:
                cursor.execute("""
                    SELECT 
                        SUM(total_checks) as total_checks,
                        AVG(avg_health) as avg_health,
                        MIN(min_health) as min_health,
                        MAX(max_health) as max_health,
                        SUM(healthy_count) as healthy_count,
                        SUM(unhealthy_count) as unhealthy_count
                    FROM hourly_health_stats 
                    WHERE hour >= ?
                """, (since[:13],))
                
                row = cursor.fetchone()
                if row and row[0] and row[0] > 0:
                    conn.close()
                    # 仍需查询服务统计
                    conn2 = sqlite3.connect(self.db_path)
                    conn2.row_factory = sqlite3.Row
                    cursor2 = conn2.cursor()
                    cursor2.execute("""
                        SELECT service_name, status, COUNT(*) as count
                        FROM service_status_logs
                        WHERE timestamp >= ?
                        GROUP BY service_name, status
                    """, (since,))
                    
                    service_stats = {}
                    for row2 in cursor2.fetchall():
                        service_name, status, count = row2
                        if service_name not in service_stats:
                            service_stats[service_name] = {}
                        service_stats[service_name][status] = count
                    conn2.close()
                    
                    return {
                        "period_hours": hours,
                        "total_checks": row[0] or 0,
                        "avg_health": round(row[1] or 0, 2),
                        "min_health": row[2] or 0,
                        "max_health": row[3] or 0,
                        "service_stats": service_stats,
                        "cached": True
                    }
            except Exception as e:
                pass  # 回退到直接查询
        
        # 直接查询（无缓存）
        cursor.execute("""
            SELECT 
                COUNT(*) as total_checks,
                AVG(network_health) as avg_health,
                MIN(network_health) as min_health,
                MAX(network_health) as max_health
            FROM health_check_logs 
            WHERE timestamp >= ?
        """, (since,))
        
        row = cursor.fetchone()
        
        # 服务统计 - 优化：只查需要的字段
        cursor.execute("""
            SELECT service_name, status, COUNT(*) as count
            FROM service_status_logs
            WHERE timestamp >= ?
            GROUP BY service_name, status
        """, (since,))
        
        service_stats = {}
        for row2 in cursor.fetchall():
            service_name, status, count = row2
            if service_name not in service_stats:
                service_stats[service_name] = {}
            service_stats[service_name][status] = count
        
        conn.close()
        
        return {
            "period_hours": hours,
            "total_checks": row[0] or 0,
            "avg_health": round(row[1] or 0, 2),
            "min_health": row[2] or 0,
            "max_health": row[3] or 0,
            "service_stats": service_stats,
            "cached": False
        }
    
    def get_latest_status(self) -> Optional[Dict]:
        """获取最新状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM health_check_logs 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "timestamp": row[1],
                "check_count": row[2],
                "total_services": row[3],
                "healthy_services": row[4],
                "unhealthy_services": row[5],
                "network_health": row[6]
            }
        return None
    
    def get_trend_analysis(self, hours: int = 24, window_size: int = 5) -> Dict:
        """趋势分析：检测健康度变化趋势
        
        Args:
            hours: 分析时间窗口（小时）
            window_size: 移动平均窗口大小
        Returns:
            趋势分析结果
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 获取时间序列数据
        cursor.execute("""
            SELECT timestamp, network_health 
            FROM health_check_logs 
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (since,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 3:
            return {
                "status": "insufficient_data",
                "message": f"数据点不足（需要至少3个，当前{len(rows)}个）",
                "data_points": len(rows)
            }
        
        timestamps = [r[0] for r in rows]
        health_values = [r[1] for r in rows]
        
        # 计算移动平均
        moving_avg = []
        for i in range(len(health_values)):
            start = max(0, i - window_size + 1)
            window = health_values[start:i+1]
            moving_avg.append(sum(window) / len(window))
        
        # 检测趋势方向
        if len(moving_avg) >= 2:
            recent_avg = sum(moving_avg[-window_size:]) / min(window_size, len(moving_avg))
            older_avg = sum(moving_avg[:window_size]) / min(window_size, len(moving_avg))
            trend_change = recent_avg - older_avg
        else:
            trend_change = 0
        
        # 确定趋势
        if trend_change > 5:
            trend_direction = "improving"
        elif trend_change < -5:
            trend_direction = "declining"
        else:
            trend_direction = "stable"
        
        # 检测异常点
        anomalies = []
        avg_health = sum(health_values) / len(health_values)
        for i, val in enumerate(health_values):
            if abs(val - avg_health) > 20:  # 偏离平均值20%以上
                anomalies.append({
                    "timestamp": timestamps[i],
                    "health": val,
                    "deviation": round(val - avg_health, 2)
                })
        
        # 计算波动性
        if len(health_values) > 1:
            variance = sum((x - avg_health) ** 2 for x in health_values) / len(health_values)
            volatility = variance ** 0.5
        else:
            volatility = 0
        
        return {
            "status": "success",
            "period_hours": hours,
            "data_points": len(rows),
            "trend_direction": trend_direction,
            "trend_change": round(trend_change, 2),
            "current_health": round(health_values[-1], 2) if health_values else 0,
            "avg_health": round(avg_health, 2),
            "volatility": round(volatility, 2),
            "anomalies": anomalies[-5:],  # 最多返回5个异常点
            "moving_average": {
                "window": window_size,
                "latest": round(moving_avg[-1], 2) if moving_avg else 0
            }
        }
    
    def predict_health(self, hours_ahead: int = 1) -> Dict:
        """简单的健康度预测（基于线性趋势）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        
        cursor.execute("""
            SELECT timestamp, network_health 
            FROM health_check_logs 
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT 20
        """, (since,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 3:
            return {"status": "insufficient_data", "message": "数据不足"}
        
        # 简单线性回归
        n = len(rows)
        x = list(range(n))
        y = [r[1] for r in rows]
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi * xi for xi in x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
        intercept = (sum_y - slope * sum_x) / n
        
        # 预测
        predicted = slope * n + intercept
        predicted = max(0, min(100, predicted))  # 限制在0-100范围
        
        trend = "up" if slope > 0.5 else "down" if slope < -0.5 else "stable"
        
        return {
            "status": "success",
            "current_health": round(y[-1], 2),
            "predicted_health": round(predicted, 2),
            "trend": trend,
            "slope": round(slope, 4),
            "confidence": "low" if n < 10 else "medium" if n < 15 else "high",
            "data_points": n
        }


def log_health_check(status: Dict):
    """便捷函数：记录健康检查"""
    logger = HealthCheckLogger()
    return logger.log_check(status)


class LogCleanup:
    """日志清理器"""
    
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/logs/health_check_log.db"):
        self.db_path = db_path
    
    def cleanup(self, keep_days: int = 7, dry_run: bool = False) -> Dict:
        """清理旧数据
        
        Args:
            keep_days: 保留天数
            dry_run: 仅预览不删除
        Returns:
            清理结果统计
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        
        # 统计将删除的记录数
        cursor.execute("SELECT COUNT(*) FROM health_check_logs WHERE timestamp < ?", (cutoff,))
        health_deleted = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM service_status_logs WHERE timestamp < ?", (cutoff,))
        service_deleted = cursor.fetchone()[0]
        
        if not dry_run:
            cursor.execute("DELETE FROM health_check_logs WHERE timestamp < ?", (cutoff,))
            cursor.execute("DELETE FROM service_status_logs WHERE timestamp < ?", (cutoff,))
            cursor.execute("DELETE FROM hourly_health_stats WHERE hour < ?", (cutoff[:13],))
            conn.commit()
        
        # 收集统计
        cursor.execute("SELECT COUNT(*) FROM health_check_logs")
        remaining = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "dry_run": dry_run,
            "keep_days": keep_days,
            "health_logs_deleted": health_deleted,
            "service_logs_deleted": service_deleted,
            "remaining_records": remaining,
            "space_freed_mb": round((health_deleted * 0.5 + service_deleted * 0.3) / 1024, 2)
        }


if __name__ == "__main__":
    # 测试
    logger = HealthCheckLogger()
    
    # 插入测试数据
    test_status = {
        "timestamp": datetime.now().isoformat(),
        "check_count": 1,
        "total_services": 6,
        "healthy_services": 6,
        "unhealthy_services": 0,
        "network_health": 100.0,
        "details": {
            "8089": {"port": 8089, "status": "healthy", "response_time_ms": 5.0, "http_code": 200, "error": None}
        }
    }
    
    logger.log_check(test_status)
    
    # 查询统计
    stats = logger.get_statistics(hours=1)
    print("统计信息:", json.dumps(stats, indent=2, ensure_ascii=False))