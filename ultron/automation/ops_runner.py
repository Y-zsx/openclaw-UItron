#!/usr/bin/env python3
"""
奥创自动化运维脚本集合 (Ultron Automation Ops Collection)
统一入口，管理所有运维脚本
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

TOOLS_DIR = Path("/root/.openclaw/workspace/ultron/tools")
AUTOMATION_DIR = Path("/root/.openclaw/workspace/ultron/automation")

SCRIPT_CATEGORIES = {
    "health": {
        "name": "健康监控",
        "description": "系统健康检查和监控",
        "scripts": [
            "agent_health_integration.py",
            "agent_health_api.py",
            "agent_health_checker.py",
            "health_monitor.py",
            "health_monitor_api.py",
            "enhanced_health_report.py",
        ]
    },
    "monitor": {
        "name": "Agent监控",
        "description": "Agent状态监控和告警",
        "scripts": [
            "agent_monitor_alert.py",
            "agent_metrics_collector.py",
            "agent_lifecycle_monitor.py",
            "agent_topology_visualizer.py",
        ]
    },
    "alert": {
        "name": "告警系统",
        "description": "告警分析和通知",
        "scripts": [
            "alert_integration_api.py",
            "alert_notification_channels.py",
            "alert_analyzer.py",
            "smart_predictive_alert.py",
            "agent_alert_dingtalk.py",
        ]
    },
    "scaling": {
        "name": "弹性伸缩",
        "description": "资源调度和伸缩",
        "scripts": [
            "agent_scaling_api.py",
            "resource-allocation.py",
            "resource-scheduler.py",
            "agent_load_optimizer.py",
            "capacity_planner.py",
            "adaptive-optimizer.py",
        ]
    },
    "self_healing": {
        "name": "自愈系统",
        "description": "系统自愈和自动修复",
        "scripts": [
            "self_healer_enhanced.py",
            "self_healing_api.py",
        ]
    },
    "collaboration": {
        "name": "协作系统",
        "description": "Agent协作和网络",
        "scripts": [
            "agent_collaboration_hub.py",
            "agent_collaboration_session.py",
            "agent_service_mesh_api.py",
            "agent_orchestration_api.py",
        ]
    },
    "reporting": {
        "name": "报表系统",
        "description": "报告生成和推送",
        "scripts": [
            "auto_report_api.py",
            "auto_report_generator.py",
            "ops_report_generator.py",
            "enhanced_ops_report_api.py",
            "system_summary_api.py",
        ]
    },
    "logs": {
        "name": "日志系统",
        "description": "日志聚合和分析",
        "scripts": [
            "log_aggregator.py",
            "log_analysis_api.py",
            "enhanced_log_analyzer.py",
            "scheduler_log_analyzer.py",
        ]
    },
    "self_improvement": {
        "name": "自我进化",
        "description": "自我优化和学习",
        "scripts": [
            "self-improvement-engine.py",
            "self-optimizer.py",
            "self-organization.py",
            "self-reflection-mechanism.py",
            "behavior-learner.py",
            "meta-cognition.py",
            "meta-learner.py",
        ]
    },
    "capability": {
        "name": "能力系统",
        "description": "能力评估和扩展",
        "scripts": [
            "capability-matrix.py",
            "capability-expander.py",
            "capability-assessment.py",
            "capability-cognition.py",
            "self-evaluator.py",
        ]
    },
    "deployment": {
        "name": "部署管理",
        "description": "部署和生命周期",
        "scripts": [
            "agent_deployment_manager.py",
            "agent-foundation.py",
            "agent-lifecycle.py",
        ]
    },
    "tracing": {
        "name": "分布式追踪",
        "description": "分布式追踪和分析",
        "scripts": [
            "distributed_tracing_api.py",
            "fault_predictor.py",
        ]
    },
    "tasks": {
        "name": "任务管理",
        "description": "任务调度和重试",
        "scripts": [
            "task_scheduler.py",
            "task_retry_manager.py",
            "agent_task_distributor.py",
        ]
    },
}


def list_categories():
    """列出所有脚本分类"""
    print("\n📁 奥创自动化运维脚本集合\n")
    print(f"{'分类':<20} {'脚本数量':<10} {'描述'}")
    print("-" * 70)
    
    total_scripts = 0
    for cat_id, cat_info in SCRIPT_CATEGORIES.items():
        count = len(cat_info["scripts"])
        total_scripts += count
        print(f"{cat_info['name']:<18} {count:<10} {cat_info['description']}")
    
    print("-" * 70)
    print(f"总计: {len(SCRIPT_CATEGORIES)} 个分类, {total_scripts} 个脚本\n")


def list_scripts(category=None):
    """列出指定分类的脚本"""
    if category and category not in SCRIPT_CATEGORIES:
        print(f"❌ 未知分类: {category}")
        print(f"可用分类: {', '.join(SCRIPT_CATEGORIES.keys())}")
        return
    
    if category:
        cats = {category: SCRIPT_CATEGORIES[category]}
    else:
        cats = SCRIPT_CATEGORIES
    
    for cat_id, cat_info in cats.items():
        print(f"\n📂 {cat_info['name']} ({cat_id})")
        print(f"   {cat_info['description']}")
        print("   脚本:")
        for script in cat_info["scripts"]:
            script_path = TOOLS_DIR / script
            status = "✅" if script_path.exists() else "❌"
            print(f"   {status} {script}")


def check_script_status():
    """检查所有脚本状态"""
    print("\n🔍 脚本状态检查\n")
    
    total = 0
    exists = 0
    missing = []
    
    for cat_id, cat_info in SCRIPT_CATEGORIES.items():
        for script in cat_info["scripts"]:
            total += 1
            script_path = TOOLS_DIR / script
            if script_path.exists():
                exists += 1
            else:
                missing.append((cat_id, script))
    
    print(f"总脚本数: {total}")
    print(f"存在: {exists} ✅")
    print(f"缺失: {len(missing)} ❌")
    
    if missing:
        print("\n缺失的脚本:")
        for cat_id, script in missing:
            print(f"  - [{cat_id}] {script}")
    
    return exists, total


def run_script(script_name, args=None):
    """运行指定脚本"""
    script_path = TOOLS_DIR / script_name
    
    if not script_path.exists():
        print(f"❌ 脚本不存在: {script_name}")
        return False
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    print(f"🚀 运行: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, cwd=TOOLS_DIR)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        return False


def find_script(query):
    """搜索脚本"""
    query = query.lower()
    results = []
    
    for cat_id, cat_info in SCRIPT_CATEGORIES.items():
        for script in cat_info["scripts"]:
            if query in script.lower() or query in cat_info["name"].lower():
                results.append((cat_id, cat_info["name"], script))
    
    if results:
        print(f"\n🔍 搜索结果: '{query}'\n")
        for cat_id, cat_name, script in results:
            print(f"  [{cat_id}] {script}")
    else:
        print(f"❌ 未找到匹配脚本: {query}")
    
    return results


def quick_health_check():
    """快速健康检查"""
    print("\n🏥 快速健康检查\n")
    
    # 检查关键端口
    ports_to_check = [
        (18210, "Agent健康API"),
        (18227, "自愈API"),
        (18228, "集成测试"),
    ]
    
    import socket
    for port, name in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        status = "✅ 运行中" if result == 0 else "❌ 未运行"
        print(f"  端口 {port} ({name}): {status}")
    
    # 检查系统资源
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        print(f"\n💻 系统资源:")
        print(f"  CPU: {cpu}%")
        print(f"  内存: {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)")
        print(f"  磁盘: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)")
    except ImportError:
        print("  (psutil未安装)")
    
    # 检查进程
    print(f"\n📋 关键进程:")
    processes = ["agent_health_integration.py", "self_healing_api.py", "system_summary_api.py"]
    for proc in processes:
        result = subprocess.run(["pgrep", "-f", proc], capture_output=True)
        status = "✅ 运行中" if result.returncode == 0 else "❌ 未运行"
        print(f"  {proc}: {status}")


def generate_report():
    """生成运维报告"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "categories": len(SCRIPT_CATEGORIES),
        "total_scripts": sum(len(cat["scripts"]) for cat in SCRIPT_CATEGORIES.values()),
    }
    
    exists, total = check_script_status()
    report["available_scripts"] = exists
    report["missing_scripts"] = total - exists
    
    # 保存报告
    report_path = AUTOMATION_DIR / "ops_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📊 报告已生成: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(
        description="奥创自动化运维脚本集合",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python ops_runner.py list                    列出所有分类
  python ops_runner.py list health             列出健康监控脚本
  python ops_runner.py check                   检查脚本状态
  python ops_runner.py health                  快速健康检查
  python ops_runner.py run agent_health_integration.py  运行脚本
  python ops_runner.py search health           搜索脚本
  python ops_runner.py report                  生成报告
        """
    )
    
    parser.add_argument("command", nargs="?", default="list",
                        help="命令: list, check, health, run, search, report")
    parser.add_argument("args", nargs="*", help="命令参数")
    
    args = parser.parse_args()
    command = args.command
    
    if command == "list":
        if args.args:
            list_scripts(args.args[0])
        else:
            list_categories()
    elif command == "check":
        check_script_status()
    elif command == "health":
        quick_health_check()
    elif command == "run":
        if not args.args:
            print("❌ 请指定要运行的脚本")
            sys.exit(1)
        run_script(args.args[0], args.args[1:])
    elif command == "search":
        if not args.args:
            print("❌ 请指定搜索关键词")
            sys.exit(1)
        find_script(args.args[0])
    elif command == "report":
        generate_report()
    else:
        print(f"❌ 未知命令: {command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()