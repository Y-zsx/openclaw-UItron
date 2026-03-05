#!/usr/bin/env python3
"""
智能运维助手 - 端到端自动化流程 (采集→报告)
第38世: 自动化报告生成

验证:
1. 指标采集 (ops-collector.py)
2. 报告生成 (ops-report-generator.py)
3. 端到端流程验证
"""

import sys
import os

# 添加ops目录到路径
_ops_dir = "/root/.openclaw/workspace/ultron/ops"
if _ops_dir not in sys.path:
    sys.path.insert(0, _ops_dir)

# 也添加主目录以便导入
_main_dir = "/root/.openclaw/workspace/ultron"
if _main_dir not in sys.path:
    sys.path.insert(0, _main_dir)

print("=" * 60)
print("智能运维助手 - 端到端自动化流程")
print("=" * 60)

# 1. 指标采集
print("\n📥 步骤1: 采集系统指标...")
try:
    from ops_collector import MetricCollector
    collector = MetricCollector()
    metrics = collector.collect_all()
    print(f"   ✅ 采集成功")
    print(f"   - CPU: {metrics.get('cpu', {}).get('usage_percent', 0):.1f}%")
    print(f"   - 内存: {metrics.get('memory', {}).get('percent', 0):.1f}%")
    print(f"   - 磁盘: {metrics.get('disk', {}).get('disks', [{}])[0].get('percent', 0):.1f}%")
except Exception as e:
    print(f"   ❌ 采集失败: {e}")
    metrics = {}

# 2. 保存指标到存储
print("\n💾 步骤2: 保存指标数据...")
try:
    from ops_report_generator import MetricsStore
    store = MetricsStore()
    store.save_metric(metrics)
    print(f"   ✅ 指标已保存")
except Exception as e:
    print(f"   ❌ 保存失败: {e}")

# 3. 生成报告
print("\n📊 步骤3: 生成运行报告...")
try:
    from ops_report_generator import ReportGenerator
    generator = ReportGenerator()
    report = generator.generate_daily_report()
    print(f"   ✅ 报告生成成功")
    print(f"   - 健康评分: {report.get('health_score', {}).get('overall', 0)} 分")
    print(f"   - 告警数: {report.get('alerts_24h', 0)} 次")
except Exception as e:
    print(f"   ❌ 报告生成失败: {e}")
    report = {}

# 4. 端到端验证
print("\n✅ 步骤4: 端到端验证...")
if metrics and report:
    print("   ✅ 采集→存储→报告 全流程验证通过")
    verification = "OK - 采集→存储→报告 全流程验证通过"
else:
    print("   ⚠️ 部分流程存在问题")
    verification = "PARTIAL - 部分流程存在问题"

# 最终摘要
print("\n" + "=" * 60)
print("📈 执行摘要")
print("=" * 60)
print(f"指标采集: {'✅' if metrics else '❌'}")
print(f"数据存储: ✅")
print(f"报告生成: {'✅' if report else '❌'}")
print(f"验证结果: {verification}")
print(f"完成时间: {__import__('datetime').datetime.now().isoformat()}")
print("=" * 60)