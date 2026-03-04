#!/usr/bin/env python3
"""
奥创性能分析器 - 第三世：智能优化与预测
功能：性能趋势分析、容量预测、自动调优策略
"""

import json
import os
import subprocess
from datetime import datetime, timedelta

DATA_FILE = "/root/.openclaw/workspace/ultron/metrics_history.json"
ALERT_THRESHOLDS = {
    "cpu_high": 80,
    "memory_high": 85,
    "disk_high": 90
}

def get_system_metrics():
    """获取当前系统指标"""
    try:
        # CPU负载
        with open('/proc/loadavg') as f:
            load = float(f.read().split()[0])
        
        # 内存
        with open('/proc/meminfo') as f:
            meminfo = f.read()
            total = int([l for l in meminfo.split('\n') if l.startswith('MemTotal:')][0].split()[1]) / 1024 / 1024
            available = int([l for l in meminfo.split('\n') if l.startswith('MemAvailable:')][0].split()[1]) / 1024 / 1024
            used = total - available
            mem_pct = (used / total) * 100
        
        # 磁盘
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        parts = result.stdout.strip().split('\n')[1].split()
        disk_used_pct = int(parts[4].replace('%', ''))
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_load": round(load, 2),
            "memory_pct": round(mem_pct, 1),
            "memory_total_gb": round(total, 1),
            "memory_available_gb": round(available, 1),
            "disk_pct": disk_used_pct
        }
    except Exception as e:
        return {"error": str(e)}

def load_history():
    """加载历史数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"metrics": []}

def save_history(data):
    """保存历史数据"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def analyze_trends(metrics, hours=24):
    """分析性能趋势"""
    if len(metrics) < 2:
        return {"status": "insufficient_data", "message": "需要更多数据点进行分析"}
    
    # 取最近N小时的数据
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = [m for m in metrics if datetime.fromisoformat(m['timestamp']) > cutoff]
    
    if len(recent) < 2:
        return {"status": "insufficient_data", "message": f"最近{hours}小时内数据不足"}
    
    # 计算趋势
    cpu_values = [m['cpu_load'] for m in recent]
    mem_values = [m['memory_pct'] for m in recent]
    disk_values = [m['disk_pct'] for m in recent]
    
    def calc_trend(values):
        """简单线性趋势"""
        n = len(values)
        if n < 2:
            return 0
        # 比较前半和后半
        mid = n // 2
        first_half = sum(values[:mid]) / mid
        second_half = sum(values[mid:]) / (n - mid)
        change = second_half - first_half
        if change > 5:
            return "rising"
        elif change < -5:
            return "falling"
        return "stable"
    
    return {
        "status": "analyzed",
        "data_points": len(recent),
        "time_range": f"最近{hours}小时",
        "cpu_trend": calc_trend(cpu_values),
        "memory_trend": calc_trend(mem_values),
        "disk_trend": calc_trend(disk_values),
        "cpu_avg": round(sum(cpu_values)/len(cpu_values), 2),
        "memory_avg": round(sum(mem_values)/len(mem_values), 1),
        "disk_avg": round(sum(disk_values)/len(disk_values), 1)
    }

def predict_capacity(metrics):
    """容量预测 - 简单线性外推"""
    if len(metrics) < 10:
        return {"status": "insufficient_data", "message": "需要至少10个数据点进行预测"}
    
    # 取磁盘增长趋势
    disk_values = [m['disk_pct'] for m in metrics[-20:]]  # 最近20个点
    
    if len(disk_values) < 2:
        return {"status": "insufficient_data"}
    
    # 简单预测：平均增长率
    growth_rates = [disk_values[i+1] - disk_values[i] for i in range(len(disk_values)-1)]
    avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0
    
    # 预测何时达到90%
    current_disk = disk_values[-1]
    if avg_growth > 0:
        days_to_90 = (90 - current_disk) / avg_growth if avg_growth > 0 else float('inf')
    else:
        days_to_90 = float('inf')
    
    return {
        "status": "predicted",
        "current_disk_pct": current_disk,
        "avg_daily_growth": round(avg_growth, 2),
        "days_to_90_percent": round(days_to_90, 1) if days_to_90 < 365 else "超过一年",
        "recommendation": "正常" if days_to_90 > 90 else "关注" if days_to_90 > 30 else "预警"
    }

def generate_optimization(current):
    """生成自动调优建议"""
    suggestions = []
    
    # CPU优化
    if current.get('cpu_load', 0) > 4:
        suggestions.append({
            "type": "cpu",
            "level": "warning",
            "message": "CPU负载较高，考虑检查运行中的进程",
            "action": "运行 'top -bn1' 查看CPU占用"
        })
    
    # 内存优化
    if current.get('memory_pct', 0) > 80:
        suggestions.append({
            "type": "memory",
            "level": "warning",
            "message": "内存使用率较高，建议清理缓存",
            "action": "运行 'sync && echo 3 > /proc/sys/vm/drop_caches'"
        })
    
    # 磁盘优化
    if current.get('disk_pct', 0) > 85:
        suggestions.append({
            "type": "disk",
            "level": "warning",
            "message": "磁盘使用率超过85%，建议清理",
            "action": "运行 'docker system prune -af' 或清理日志"
        })
    
    if not suggestions:
        suggestions.append({
            "type": "system",
            "level": "ok",
            "message": "系统运行正常，无需优化",
            "action": None
        })
    
    return suggestions

def main():
    """主函数"""
    # 获取当前指标
    current = get_system_metrics()
    print(f"📊 当前系统指标: {json.dumps(current, indent=2, ensure_ascii=False)}")
    
    # 加载历史
    history = load_history()
    
    # 添加当前数据
    history["metrics"].append(current)
    
    # 只保留最近7天的数据
    cutoff = datetime.now() - timedelta(days=7)
    history["metrics"] = [
        m for m in history["metrics"] 
        if datetime.fromisoformat(m['timestamp']) > cutoff
    ]
    save_history(history)
    
    # 趋势分析
    print("\n📈 性能趋势分析:")
    trends = analyze_trends(history["metrics"])
    print(f"   {json.dumps(trends, ensure_ascii=False)}")
    
    # 容量预测
    print("\n🔮 容量预测:")
    prediction = predict_capacity(history["metrics"])
    print(f"   {json.dumps(prediction, ensure_ascii=False)}")
    
    # 自动调优建议
    print("\n⚡ 自动调优建议:")
    optimizations = generate_optimization(current)
    for opt in optimizations:
        print(f"   [{opt['level'].upper()}] {opt['message']}")
        if opt.get('action'):
            print(f"      → {opt['action']}")
    
    # 返回结构化结果
    return {
        "current": current,
        "trends": trends,
        "prediction": prediction,
        "optimizations": optimizations
    }

if __name__ == "__main__":
    result = main()
    print("\n" + "="*50)
    print("✅ 性能分析完成")