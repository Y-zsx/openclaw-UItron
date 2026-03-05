#!/usr/bin/env python3
"""
审计系统CLI工具
"""

import sys
import os
import argparse
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_logger import get_logger
from compliance import ComplianceChecker

def cmd_query(args):
    logger = get_logger()
    logs = logger.query(
        event_type=args.type,
        agent_id=args.agent,
        start_time=args.since,
        limit=args.limit
    )
    print(json.dumps(logs, indent=2, ensure_ascii=False))

def cmd_stats(args):
    logger = get_logger()
    stats = logger.get_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

def cmd_compliance(args):
    checker = ComplianceChecker()
    results = checker.run_all_checks()
    print(json.dumps(results, indent=2, ensure_ascii=False))

def cmd_log(args):
    logger = get_logger()
    if args.category == "auth":
        log_id = logger.log_auth(args.agent, args.action, args.status)
    elif args.category == "task":
        log_id = logger.log_task(args.agent, args.resource, args.action, args.status)
    elif args.category == "api":
        log_id = logger.log_api(args.agent, args.resource, args.action, args.status)
    else:
        log_id = logger.log(args.category, args.action, args.status, args.agent)
    print(f"Logged: {log_id}")

def main():
    parser = argparse.ArgumentParser(description="审计系统CLI")
    subparsers = parser.add_subparsers()
    
    # query
    p_query = subparsers.add_parser("query", help="查询日志")
    p_query.add_argument("--type", "-t")
    p_query.add_argument("--agent", "-a")
    p_query.add_argument("--since", "-s")
    p_query.add_argument("--limit", "-l", type=int, default=50)
    p_query.set_defaults(func=cmd_query)
    
    # stats
    p_stats = subparsers.add_parser("stats", help="统计信息")
    p_stats.set_defaults(func=cmd_stats)
    
    # compliance
    p_comp = subparsers.add_parser("compliance", help="合规检查")
    p_comp.set_defaults(func=cmd_compliance)
    
    # log
    p_log = subparsers.add_parser("log", help="记录日志")
    p_log.add_argument("category", choices=["auth", "task", "api", "comm", "general"])
    p_log.add_argument("--agent", "-a")
    p_log.add_argument("--action", default="LOG")
    p_log.add_argument("--status", default="INFO")
    p_log.add_argument("--resource", "-r")
    p_log.set_defaults(func=cmd_log)
    
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()