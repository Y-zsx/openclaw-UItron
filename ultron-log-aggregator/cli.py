"""CLI工具 - 命令行界面"""
import argparse
import json
import sys
from datetime import datetime, timedelta

from config import MODULES
from collector import LogCollector, get_collector
from storage import LogStorage, get_storage
from analyzer import LogAnalyzer, get_analyzer


def cmd_collect(args):
    """启动日志收集服务"""
    collector = LogCollector()
    print(f"日志收集服务已启动 (缓冲: {collector.buffer_size}, 刷新间隔: {collector.flush_interval}s)")
    print("按 Ctrl+C 停止")
    
    try:
        import time
        while True:
            # 示例: 每10秒添加一条测试日志
            if args.test:
                collector.add_log(
                    "decision_engine",
                    "INFO",
                    "测试日志条目",
                    {"test": True, "counter": 0}
                )
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n日志收集服务已停止")


def cmd_query(args):
    """查询日志"""
    storage = get_storage()
    module = args.module or MODULES[0]
    
    # 获取日志文件
    log_files = storage.get_log_files(
        module,
        date=args.start  # 简单实现：使用start作为日期过滤
    )
    
    if not log_files:
        print(f"未找到模块 '{module}' 的日志")
        return
    
    # 读取并过滤
    logs = []
    for log_file in log_files:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    
                    # 级别过滤
                    if args.level and entry.get("level") != args.level:
                        continue
                    
                    logs.append(entry)
                except json.JSONDecodeError:
                    continue
    
    # 限制输出数量
    if args.limit:
        logs = logs[-args.limit:]
    
    # 输出
    for log in logs:
        ts = log.get("timestamp", "")[:19]
        level = log.get("level", "INFO")
        msg = log.get("message", "")
        print(f"[{ts}] {level:8s} {msg}")


def cmd_stats(args):
    """统计报表"""
    analyzer = get_analyzer()
    module = args.module or MODULES[0]
    
    # 确定日期范围
    period = args.period or "7d"
    if period == "1d":
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    elif period == "7d":
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "30d":
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        start_date = args.start or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    
    if args.json:
        stats = analyzer.calculate_stats(module, start_date, end_date)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        stats = analyzer.calculate_stats(module, start_date, end_date)
        print(f"\n=== {module} 日志统计 ({start_date} ~ {end_date}) ===\n")
        print(f"总日志数: {stats['total_count']}")
        print(f"错误数: {stats['error_count']}")
        print(f"错误率: {stats['error_rate']}%")
        
        if stats.get("success_rate"):
            print(f"成功率: {stats['success_rate']}%")
        
        if stats.get("avg_duration_ms"):
            print(f"平均响应时间: {stats['avg_duration_ms']}ms")
        
        print("\n级别分布:")
        for level, count in stats.get("by_level", {}).items():
            print(f"  {level}: {count}")


def cmd_export(args):
    """导出日志"""
    analyzer = get_analyzer()
    module = args.module or MODULES[0]
    
    # 日期范围
    start_date = args.start or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    
    # 加载日志
    logs = analyzer.load_logs(module, start_date, end_date)
    
    if not logs:
        print("未找到日志")
        return
    
    # 导出
    if args.format == "json":
        output = json.dumps(logs, ensure_ascii=False, indent=2)
    elif args.format == "csv":
        import csv
        import io
        output = io.StringIO()
        if logs:
            writer = csv.DictWriter(output, fieldnames=["timestamp", "module", "level", "message"])
            writer.writeheader()
            for log in logs:
                writer.writerow({
                    "timestamp": log.get("timestamp", ""),
                    "module": log.get("module", ""),
                    "level": log.get("level", ""),
                    "message": log.get("message", "")
                })
        output = output.getvalue()
    else:
        print(f"不支持的格式: {args.format}")
        return
    
    # 输出或保存
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已导出到: {args.output}")
    else:
        print(output[:5000])  # 限制输出


def cmd_report(args):
    """生成报告"""
    analyzer = get_analyzer()
    module = args.module or MODULES[0]
    
    start_date = args.start or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    format_type = args.format
    
    # 生成报告
    report = analyzer.generate_report(module, start_date, end_date, format_type)
    
    # 输出
    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif format_type == "markdown":
        print(report.get("markdown", ""))
    else:
        stats = report["statistics"]
        patterns = report["patterns"]
        
        print(f"\n=== {module} 日志分析报告 ===")
        print(f"周期: {start_date} ~ {end_date}\n")
        print(f"总日志数: {stats['total_count']}")
        print(f"错误率: {stats['error_rate']}%")
        
        if patterns.get("common_messages"):
            print("\n常见错误:")
            for item in patterns["common_messages"][:5]:
                print(f"  - {item['message']} ({item['count']}次)")
    
    # 保存报告
    if args.save:
        path = analyzer.save_report(module, start_date, end_date, format_type)
        print(f"\n报告已保存: {path}")


def cmd_storage(args):
    """存储管理"""
    storage = get_storage()
    
    if args.clean:
        cleaned = storage.cleanup_old_logs(args.module)
        print(f"已清理 {cleaned} 个过期日志文件")
    
    if args.stats:
        stats = storage.get_storage_stats(args.module)
        print(json.dumps(stats, indent=2))


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="日志聚合平台 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # collect - 启动收集服务
    collect_parser = subparsers.add_parser("collect", help="启动日志收集服务")
    collect_parser.add_argument("--test", action="store_true", help="启用测试模式")
    collect_parser.set_defaults(func=cmd_collect)
    
    # query - 查询日志
    query_parser = subparsers.add_parser("query", help="查询日志")
    query_parser.add_argument("--module", "-m", choices=MODULES, help="模块名称")
    query_parser.add_argument("--level", "-l", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="日志级别")
    query_parser.add_argument("--start", "-s", help="开始日期 (YYYY-MM-DD)")
    query_parser.add_argument("--end", "-e", help="结束日期 (YYYY-MM-DD)")
    query_parser.add_argument("--limit", "-n", type=int, default=100, help="限制输出数量")
    query_parser.set_defaults(func=cmd_query)
    
    # stats - 统计报表
    stats_parser = subparsers.add_parser("stats", help="统计报表")
    stats_parser.add_argument("--module", "-m", choices=MODULES, help="模块名称")
    stats_parser.add_argument("--period", "-p", choices=["1d", "7d", "30d"], default="7d", help="统计周期")
    stats_parser.add_argument("--start", "-s", help="开始日期")
    stats_parser.add_argument("--end", "-e", help="结束日期")
    stats_parser.add_argument("--json", "-j", action="store_true", help="JSON输出")
    stats_parser.set_defaults(func=cmd_stats)
    
    # export - 导出日志
    export_parser = subparsers.add_parser("export", help="导出日志")
    export_parser.add_argument("--module", "-m", choices=MODULES, help="模块名称")
    export_parser.add_argument("--start", "-s", help="开始日期")
    export_parser.add_argument("--end", "-e", help="结束日期")
    export_parser.add_argument("--format", "-f", choices=["json", "csv"], default="json", help="导出格式")
    export_parser.add_argument("--output", "-o", help="输出文件路径")
    export_parser.set_defaults(func=cmd_export)
    
    # report - 生成报告
    report_parser = subparsers.add_parser("report", help="生成分析报告")
    report_parser.add_argument("--module", "-m", choices=MODULES, help="模块名称")
    report_parser.add_argument("--start", "-s", help="开始日期")
    report_parser.add_argument("--end", "-e", help="结束日期")
    report_parser.add_argument("--format", "-f", choices=["json", "markdown"], default="json", help="报告格式")
    report_parser.add_argument("--json-output", "-j", action="store_true", help="JSON完整输出")
    report_parser.add_argument("--save", action="store_true", help="保存报告到文件")
    report_parser.set_defaults(func=cmd_report)
    
    # storage - 存储管理
    storage_parser = subparsers.add_parser("storage", help="存储管理")
    storage_parser.add_argument("--module", "-m", choices=MODULES, help="模块名称")
    storage_parser.add_argument("--clean", "-c", action="store_true", help="清理过期日志")
    storage_parser.add_argument("--stats", "-s", action="store_true", help="显示存储统计")
    storage_parser.set_defaults(func=cmd_storage)
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 执行子命令
    args.func(args)


if __name__ == "__main__":
    main()