#!/usr/bin/env python3
"""
奥创预测性维护系统 - 夙愿八：智能决策优化系统 第3世
功能：趋势预测 + 异常预警 + 预防性维护
创建时间: 2026-03-04
"""

import os
import time
import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import deque
import statistics


class PredictiveMaintenance:
    """预测性维护系统"""
    
    def __init__(self):
        self.data_dir = "/root/.openclaw/workspace/ultron/data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 预测参数
        self.prediction_window = 30  # 预测未来30分钟
        self.lookback_window = 60    # 回顾过去60个采样点
        self.sampling_interval = 60  # 采样间隔60秒
        
        # 告警阈值
        self.alert_thresholds = {
            "cpu_spike": 80.0,       # CPU突增告警
            "memory_growth": 70.0,   # 内存增长告警
            "disk_growth": 85.0,     # 磁盘增长告警
            "load_spike": 2.0,       # 负载突增
            "response_time": 1000,   # 响应时间阈值(ms)
        }
        
        # 趋势判断阈值
        self.trend_thresholds = {
            "rising_fast": 5.0,      # 快速上升（%/分钟）
            "rising": 2.0,           # 缓慢上升
            "falling": -2.0,         # 下降
            "stable": 1.0,           # 稳定（波动范围）
        }
        
        # 异常检测参数
        self.anomaly_config = {
            "zscore_threshold": 2.5,  # Z-score异常阈值
            "min_samples": 10,        # 最小样本数
            "window_size": 20,        # 滑动窗口大小
        }
        
        # 维护动作
        self.maintenance_actions = {
            "cpu_high": self._action_cpu_high,
            "memory_high": self._action_memory_high,
            "disk_high": self._action_disk_high,
            "load_high": self._action_load_high,
            "service_unresponsive": self._action_service_down,
        }
        
        # 历史数据
        self.metrics_history = {
            "cpu": deque(maxlen=self.lookback_window),
            "memory": deque(maxlen=self.lookback_window),
            "disk": deque(maxlen=self.lookback_window),
            "load": deque(maxlen=self.lookback_window),
            "response_time": deque(maxlen=self.lookback_window),
        }
        
        # 告警记录
        self.alerts = deque(maxlen=100)
        self.maintenance_log = []
        
        # 预测模型（简单线性回归+移动平均）
        self.weights = {
            "linear": 0.6,
            "moving_avg": 0.3,
            "weighted": 0.1,
        }
    
    # ==================== 数据采集 ====================
    
    def collect_metrics(self) -> Dict:
        """采集当前指标"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cpu": self._get_cpu_usage(),
            "memory": self._get_memory_usage(),
            "disk": self._get_disk_usage(),
            "load": self._get_load_avg(),
            "response_time": self._get_response_time(),
            "processes": self._get_process_count(),
        }
        
        # 存储历史
        for key in ["cpu", "memory", "disk", "load", "response_time"]:
            if key in metrics:
                self.metrics_history[key].append({
                    "value": metrics[key],
                    "timestamp": metrics["timestamp"]
                })
        
        return metrics
    
    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            result = subprocess.run(
                ["cat", "/proc/stat"],
                capture_output=True, text=True, timeout=5
            )
            cpu_line = result.stdout.strip().split("\n")[0]
            parts = cpu_line.split()
            total = sum(float(x) for x in parts[1:8] if x.replace('.','').isdigit())
            idle = float(parts[4])
            return round(100 - (idle / total * 100), 2)
        except:
            return 0.0
    
    def _get_memory_usage(self) -> float:
        """获取内存使用率"""
        try:
            result = subprocess.run(
                ["free", "-b"],
                capture_output=True, text=True, timeout=5
            )
            mem_line = result.stdout.strip().split("\n")[1].split()
            mem_total = int(mem_line[1])
            mem_used = int(mem_line[2])
            return round((mem_used / mem_total) * 100, 2)
        except:
            return 0.0
    
    def _get_disk_usage(self) -> float:
        """获取磁盘使用率"""
        try:
            result = subprocess.run(
                ["df", "-B1", "/"],
                capture_output=True, text=True, timeout=5
            )
            disk_line = result.stdout.strip().split("\n")[1]
            parts = disk_line.split()
            total = int(parts[1])
            used = int(parts[2])
            return round((used / total) * 100, 2) if total > 0 else 0.0
        except:
            return 0.0
    
    def _get_load_avg(self) -> float:
        """获取负载"""
        try:
            return round(os.getloadavg()[0], 2)
        except:
            return 0.0
    
    def _get_response_time(self) -> float:
        """获取系统响应时间(ms)"""
        try:
            start = time.time()
            subprocess.run(
                ["echo", "test"],
                capture_output=True, timeout=5
            )
            return round((time.time() - start) * 1000, 2)
        except:
            return 0.0
    
    def _get_process_count(self) -> int:
        """获取进程数"""
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid"],
                capture_output=True, text=True, timeout=5
            )
            return len(result.stdout.strip().split("\n"))
        except:
            return 0
    
    # ==================== 趋势预测 ====================
    
    def predict_trend(self, metric_name: str, steps: int = 30) -> Dict:
        """
        预测趋势
        使用多种方法组合：线性回归 + 移动平均 + 加权移动平均
        """
        if metric_name not in self.metrics_history:
            return {"error": f"Unknown metric: {metric_name}"}
        
        history = self.metrics_history[metric_name]
        if len(history) < 5:
            return {"error": "Insufficient data for prediction"}
        
        values = [h["value"] for h in history]
        timestamps = list(range(len(values)))
        
        # 1. 线性回归预测
        linear_pred = self._linear_regression(timestamps, values, len(values) + steps)
        
        # 2. 简单移动平均
        ma_pred = self._moving_average(values, steps)
        
        # 3. 加权移动平均
        wma_pred = self._weighted_moving_average(values, steps)
        
        # 组合预测
        combined = (
            linear_pred * self.weights["linear"] +
            ma_pred * self.weights["moving_avg"] +
            wma_pred * self.weights["weighted"]
        )
        
        # 计算趋势方向
        trend = self._calculate_trend_direction(values)
        
        # 计算置信度
        confidence = self._calculate_confidence(values)
        
        return {
            "metric": metric_name,
            "current": values[-1],
            "prediction": round(combined, 2),
            "linear": round(linear_pred, 2),
            "moving_avg": round(ma_pred, 2),
            "weighted_avg": round(wma_pred, 2),
            "trend": trend,
            "confidence": confidence,
            "steps_ahead": steps,
            "data_points": len(values),
        }
    
    def _linear_regression(self, x: List[int], y: List[float], x_pred: int) -> float:
        """线性回归预测"""
        if len(x) < 2:
            return y[-1] if y else 0
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)
        
        # 斜率和截距
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
        intercept = (sum_y - slope * sum_x) / n
        
        return slope * x_pred + intercept
    
    def _moving_average(self, values: List[float], steps: int) -> float:
        """简单移动平均"""
        window = min(10, len(values))
        return statistics.mean(values[-window:])
    
    def _weighted_moving_average(self, values: List[float], steps: int) -> float:
        """加权移动平均（越近的数据权重越大）"""
        window = min(10, len(values))
        recent = values[-window:]
        weights = list(range(1, window + 1))
        return sum(w * v for w, v in zip(weights, recent)) / sum(weights)
    
    def _calculate_trend_direction(self, values: List[float]) -> str:
        """计算趋势方向"""
        if len(values) < 5:
            return "unknown"
        
        # 比较最近5个和前5个的平均值
        recent_avg = statistics.mean(values[-5:])
        older_avg = statistics.mean(values[-10:-5]) if len(values) >= 10 else statistics.mean(values[:5])
        
        change = recent_avg - older_avg
        
        if change > self.trend_thresholds["rising_fast"]:
            return "rising_fast"
        elif change > self.trend_thresholds["rising"]:
            return "rising"
        elif change < self.trend_thresholds["falling"]:
            return "falling"
        elif abs(change) < self.trend_thresholds["stable"]:
            return "stable"
        else:
            return "fluctuating"
    
    def _calculate_confidence(self, values: List[float]) -> str:
        """计算预测置信度"""
        if len(values) < 10:
            return "low"
        
        # 计算变异系数
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        cv = (stdev / mean * 100) if mean > 0 else 0
        
        if cv < 10:
            return "high"
        elif cv < 25:
            return "medium"
        else:
            return "low"
    
    # ==================== 异常检测 ====================
    
    def detect_anomaly(self, metric_name: str) -> Dict:
        """检测异常"""
        if metric_name not in self.metrics_history:
            return {"error": f"Unknown metric: {metric_name}"}
        
        history = self.metrics_history[metric_name]
        if len(history) < self.anomaly_config["min_samples"]:
            return {"error": "Insufficient data for anomaly detection"}
        
        values = [h["value"] for h in history]
        current = values[-1]
        
        # Z-score 检测
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        zscore = (current - mean) / stdev if stdev > 0 else 0
        
        # 滑动窗口检测
        window = self.anomaly_config["window_size"]
        if len(values) >= window:
            recent_window = values[-window:]
            window_mean = statistics.mean(recent_window)
            window_stdev = statistics.stdev(recent_window) if len(recent_window) > 1 else 0
            window_zscore = (current - window_mean) / window_stdev if window_stdev > 0 else 0
        else:
            window_zscore = zscore
            window_mean = mean
        
        # 判断是否异常
        threshold = self.anomaly_config["zscore_threshold"]
        is_anomaly = abs(zscore) > threshold
        
        # 异常类型
        anomaly_type = None
        if is_anomaly:
            if zscore > threshold:
                anomaly_type = "spike"
            else:
                anomaly_type = "drop"
        
        return {
            "metric": metric_name,
            "current": current,
            "mean": round(mean, 2),
            "stdev": round(stdev, 2),
            "zscore": round(zscore, 2),
            "window_zscore": round(window_zscore, 2),
            "is_anomaly": is_anomaly,
            "anomaly_type": anomaly_type,
            "threshold": threshold,
        }
    
    def detect_all_anomalies(self) -> List[Dict]:
        """检测所有指标异常"""
        results = []
        for metric in self.metrics_history:
            if len(self.metrics_history[metric]) > 0:
                result = self.detect_anomaly(metric)
                if "error" not in result:
                    results.append(result)
        return results
    
    # ==================== 预警系统 ====================
    
    def check_alerts(self) -> List[Dict]:
        """检查是否需要告警"""
        alerts = []
        current = self.collect_metrics()
        
        # CPU 告警
        if current["cpu"] > self.alert_thresholds["cpu_spike"]:
            alerts.append({
                "type": "cpu_high",
                "severity": "warning",
                "message": f"CPU使用率过高: {current['cpu']}%",
                "value": current["cpu"],
                "threshold": self.alert_thresholds["cpu_spike"],
                "timestamp": current["timestamp"],
            })
        
        # 内存告警
        if current["memory"] > self.alert_thresholds["memory_growth"]:
            alerts.append({
                "type": "memory_high",
                "severity": "warning",
                "message": f"内存使用率过高: {current['memory']}%",
                "value": current["memory"],
                "threshold": self.alert_thresholds["memory_growth"],
                "timestamp": current["timestamp"],
            })
        
        # 磁盘告警
        if current["disk"] > self.alert_thresholds["disk_growth"]:
            alerts.append({
                "type": "disk_high",
                "severity": "warning",
                "message": f"磁盘使用率过高: {current['disk']}%",
                "value": current["disk"],
                "threshold": self.alert_thresholds["disk_growth"],
                "timestamp": current["timestamp"],
            })
        
        # 负载告警
        if current["load"] > self.alert_thresholds["load_spike"]:
            alerts.append({
                "type": "load_high",
                "severity": "info",
                "message": f"系统负载较高: {current['load']}",
                "value": current["load"],
                "threshold": self.alert_thresholds["load_spike"],
                "timestamp": current["timestamp"],
            })
        
        # 预测性告警
        predictions = self.predict_all_trends()
        for pred in predictions:
            if pred.get("prediction", 0) > self.alert_thresholds.get(f"{pred['metric']}_spike", 80):
                alerts.append({
                    "type": f"{pred['metric']}_predicted",
                    "severity": "warning",
                    "message": f"预测{pred['metric']}将超阈值: 当前{pred['current']}% → 预测{pred['prediction']}%",
                    "current": pred["current"],
                    "predicted": pred["prediction"],
                    "timestamp": current["timestamp"],
                })
        
        # 存储告警
        for alert in alerts:
            self.alerts.append(alert)
        
        return alerts
    
    def predict_all_trends(self) -> List[Dict]:
        """预测所有指标趋势"""
        results = []
        for metric in ["cpu", "memory", "disk", "load"]:
            pred = self.predict_trend(metric, steps=15)  # 预测15分钟后
            if "error" not in pred:
                results.append(pred)
        return results
    
    # ==================== 预防性维护 ====================
    
    def run_maintenance(self) -> Dict:
        """执行预防性维护"""
        current = self.collect_metrics()
        actions_taken = []
        
        # 基于当前指标
        if current["cpu"] > 70:
            action = self.maintenance_actions["cpu_high"](current)
            actions_taken.append(action)
        
        if current["memory"] > 75:
            action = self.maintenance_actions["memory_high"](current)
            actions_taken.append(action)
        
        # 基于预测
        predictions = self.predict_all_trends()
        for pred in predictions:
            metric = pred["metric"]
            predicted = pred["prediction"]
            
            if metric == "cpu" and predicted > 80:
                actions_taken.append({
                    "action": "cpu_preemptive_scale",
                    "description": "预测CPU将超限，启动预防性降温",
                    "predicted": predicted,
                })
            
            elif metric == "memory" and predicted > 85:
                actions_taken.append({
                    "action": "memory_preemptive_cleanup",
                    "description": "预测内存将超限，执行预防性清理",
                    "predicted": predicted,
                })
        
        # 记录维护动作
        self.maintenance_log.append({
            "timestamp": current["timestamp"],
            "actions": actions_taken,
            "metrics": current,
        })
        
        return {
            "timestamp": current["timestamp"],
            "actions_count": len(actions_taken),
            "actions": actions_taken,
        }
    
    def _action_cpu_high(self, metrics: Dict) -> Dict:
        """CPU高负载处理"""
        return {
            "action": "cpu_high_response",
            "description": "CPU使用率高，检查高负载进程",
            "value": metrics.get("cpu", 0),
        }
    
    def _action_memory_high(self, metrics: Dict) -> Dict:
        """内存高负载处理"""
        return {
            "action": "memory_high_response",
            "description": "内存使用率高，检查内存占用进程",
            "value": metrics.get("memory", 0),
        }
    
    def _action_disk_high(self, metrics: Dict) -> Dict:
        """磁盘高使用率处理"""
        return {
            "action": "disk_high_response",
            "description": "磁盘使用率高，检查大文件",
            "value": metrics.get("disk", 0),
        }
    
    def _action_load_high(self, metrics: Dict) -> Dict:
        """负载高处理"""
        return {
            "action": "load_high_response",
            "description": "系统负载高，分析负载来源",
            "value": metrics.get("load", 0),
        }
    
    def _action_service_down(self, metrics: Dict) -> Dict:
        """服务无响应处理"""
        return {
            "action": "service_restart",
            "description": "服务无响应，尝试重启",
            "value": metrics.get("response_time", 0),
        }
    
    # ==================== 报告生成 ====================
    
    def generate_report(self) -> Dict:
        """生成预测性维护报告"""
        current = self.collect_metrics()
        predictions = self.predict_all_trends()
        anomalies = self.detect_all_anomalies()
        alerts = list(self.alerts)[-10:]  # 最近10条告警
        
        # 计算健康评分
        health_score = 100
        
        # CPU影响
        if current["cpu"] > 80:
            health_score -= 20
        elif current["cpu"] > 60:
            health_score -= 10
        
        # 内存影响
        if current["memory"] > 85:
            health_score -= 20
        elif current["memory"] > 70:
            health_score -= 10
        
        # 预测影响
        for pred in predictions:
            if pred["prediction"] > 85:
                health_score -= 10
            elif pred["prediction"] > 75:
                health_score -= 5
        
        # 异常影响
        anomaly_count = sum(1 for a in anomalies if a.get("is_anomaly", False))
        health_score -= anomaly_count * 5
        
        health_score = max(0, health_score)
        
        return {
            "timestamp": current["timestamp"],
            "health_score": health_score,
            "current_metrics": current,
            "predictions": predictions,
            "anomalies": anomalies,
            "recent_alerts": alerts,
            "maintenance_count": len(self.maintenance_log),
        }
    
    def save_report(self, filepath: str = None) -> str:
        """保存报告"""
        report = self.generate_report()
        
        if filepath is None:
            filepath = os.path.join(
                self.data_dir,
                f"predictive_maintenance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def print_summary(self):
        """打印摘要"""
        report = self.generate_report()
        
        print("=" * 60)
        print("📊 预测性维护报告")
        print("=" * 60)
        print(f"健康评分: {report['health_score']}/100")
        print(f"\n当前指标:")
        m = report['current_metrics']
        print(f"  CPU: {m['cpu']}% | 内存: {m['memory']}% | 磁盘: {m['disk']}% | 负载: {m['load']}")
        
        print(f"\n趋势预测:")
        for pred in report['predictions']:
            print(f"  {pred['metric']}: {pred['current']}% → {pred['prediction']}% ({pred['trend']})")
        
        anomalies = [a for a in report['anomalies'] if a.get('is_anomaly')]
        if anomalies:
            print(f"\n⚠️ 异常检测:")
            for a in anomalies:
                print(f"  {a['metric']}: {a['current']}% (z-score: {a['zscore']})")
        
        if report['recent_alerts']:
            print(f"\n🔔 告警 ({len(report['recent_alerts'])}条):")
            for alert in report['recent_alerts'][-3:]:
                print(f"  [{alert['type']}] {alert['message']}")
        
        print("=" * 60)


def main():
    """主函数"""
    pm = PredictiveMaintenance()
    
    # 采集数据并生成报告
    pm.collect_metrics()
    time.sleep(1)
    pm.collect_metrics()
    time.sleep(1)
    pm.collect_metrics()
    
    # 打印摘要
    pm.print_summary()
    
    # 保存报告
    filepath = pm.save_report()
    print(f"\n报告已保存: {filepath}")
    
    # 返回结果
    report = pm.generate_report()
    print(f"\n最终健康评分: {report['health_score']}/100")


if __name__ == "__main__":
    main()