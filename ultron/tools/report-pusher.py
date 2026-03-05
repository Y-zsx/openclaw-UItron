#!/usr/bin/env python3
"""
报告推送模块 - Report Pusher
将生成的报告推送到钉钉/其他渠道
"""
import json
import os
import sys
from datetime import datetime

REPORTS_DIR = "/root/.openclaw/workspace/ultron/reports"

def get_latest_report():
    """获取最新生成的报告"""
    reports = []
    for f in os.listdir(REPORTS_DIR):
        if f.startswith("report_") and f.endswith(".json"):
            path = os.path.join(REPORTS_DIR, f)
            reports.append((os.path.getmtime(path), path))
    
    if not reports:
        return None
    
    latest = sorted(reports, reverse=True)[0][1]
    with open(latest, 'r') as f:
        return json.load(f)

def format_for_dingtalk(report):
    """将报告格式化为钉钉消息"""
    # 解析实际报告结构
    generated_at = report.get("generated_at", "")
    health = report.get("health_score", {})
    current = report.get("current_status", {})
    stats = report.get("statistics_24h", {})
    
    score = health.get("overall", 0)
    grade = health.get("grade", "N/A")
    alerts = report.get("alerts_24h", 0)
    
    # 获取24小时统计
    cpu = stats.get("cpu", {})
    mem = stats.get("memory", {})
    
    cpu_avg = cpu.get("avg", 0)
    cpu_max = cpu.get("max", 0)
    mem_avg = mem.get("avg", 0)
    mem_max = mem.get("max", 0)
    
    disk = current.get("disk_percent", 0)
    cpu_now = current.get("cpu_percent", 0)
    mem_now = current.get("memory_percent", 0)
    
    # 格式化消息 - 使用markdown
    message = f"""## 📊 奥创运维报告

**生成时间**: {generated_at}

### 🟢 健康状态
- **综合评分**: {score} 分 ({grade})
- **24h告警数**: {alerts}

### 📈 实时指标
| 指标 | 当前 | 24h平均 | 24h峰值 |
|------|------|---------|---------|
| CPU | {cpu_now}% | {cpu_avg:.1f}% | {cpu_max}% |
| 内存 | {mem_now}% | {mem_avg:.1f}% | {mem_max}% |
| 磁盘 | {disk}% | - | - |

### 📋 详细评分
- CPU: {health.get('details', {}).get('cpu', 0)}分
- 内存: {health.get('details', {}).get('memory', 0)}分  
- 磁盘: {health.get('details', {}).get('disk', 0)}分
- 网络: {health.get('details', {}).get('network', 0)}分

---
*🤖 奥创智能运维系统 v2.0* 🔥
"""
    return message

def push_to_dingtalk(message):
    """推送到钉钉 - 写入队列供cron读取发送"""
    queue_file = "/root/.openclaw/workspace/ultron/reports/push_queue.json"
    queue_data = {
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "channel": "dingtalk",
        "ready": True
    }
    with open(queue_file, 'w') as f:
        json.dump(queue_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 报告已加入推送队列")
    return True

def main():
    print("=" * 50)
    print("📨 报告推送模块启动")
    print("=" * 50)
    
    # 获取最新报告
    report = get_latest_report()
    if not report:
        print("❌ 未找到报告文件")
        sys.exit(1)
    
    print(f"📄 已加载报告: {report.get('generated_at', 'unknown')}")
    
    # 格式化
    message = format_for_dingtalk(report)
    print(f"✅ 消息已格式化 ({len(message)} 字符)")
    
    # 推送
    push_to_dingtalk(message)
    
    # 输出消息供外部调用
    print("\n" + "=" * 50)
    print("📨 推送消息内容:")
    print("=" * 50)
    print(message)
    
    return message

if __name__ == "__main__":
    main()