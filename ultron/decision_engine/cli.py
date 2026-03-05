#!/usr/bin/env python3
"""
决策引擎CLI工具
Usage: python cli.py <command> [options]
"""

import argparse
import json
import sys
import requests
import sqlite3
from datetime import datetime
from pathlib import Path

# 配置
API_BASE = "http://localhost:18120"
DB_PATH = Path(__file__).parent / "decisions.db"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_warning(text):
    print(f"⚠️  {text}")

# ============ 统计命令 ============

def cmd_stats(args):
    """显示决策引擎统计信息"""
    print_header("决策引擎统计")
    
    try:
        resp = requests.get(f"{API_BASE}/stats", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"📊 总决策数: {data.get('total_decisions', 0)}")
            print(f"📈 今日决策: {data.get('today_decisions', 0)}")
            print(f"✅ 自动审批: {data.get('auto_approved', 0)}")
            print(f"🎯 已执行行动: {data.get('executed_actions', 0)}")
            if 'success_rate' in data:
                print(f"📈 成功率: {data.get('success_rate', 0):.1f}%")
        else:
            print_error(f"API错误: {resp.status_code}")
    except requests.exceptions.RequestException as e:
        # 尝试从本地数据库获取
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM decisions")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM decisions WHERE DATE(created_at) = DATE('now')")
            today = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM decisions WHERE auto_approved = 1")
            auto = cur.fetchone()[0]
            conn.close()
            print(f"📊 总决策数: {total}")
            print(f"📈 今日决策: {today}")
            print(f"✅ 自动审批: {auto}")
        except Exception as db_err:
            print_error(f"API和本地数据库都不可用: {e}")

# ============ 决策命令 ============

def cmd_decide(args):
    """发起新决策"""
    print_header("发起决策")
    
    # 收集上下文
    context = {}
    if args.context:
        for pair in args.context:
            if '=' in pair:
                k, v = pair.split('=', 1)
                context[k] = v
    
    payload = {
        "context": context,
        "auto_approve": args.auto_approve
    }
    
    try:
        resp = requests.post(f"{API_BASE}/decide", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print_success(f"决策ID: {data.get('decision_id')}")
            print(f"风险等级: {data.get('risk_level')}/10")
            print(f"决策结果: {data.get('decision')}")
            if data.get('action'):
                print(f"建议行动: {data.get('action')}")
            if data.get('auto_approved'):
                print_success("已自动审批")
            else:
                print_warning("需要人工审批")
        else:
            print_error(f"决策失败: {resp.text}")
    except requests.exceptions.RequestException as e:
        print_error(f"连接失败: {e}")

def cmd_decisions(args):
    """列出决策历史"""
    print_header("决策历史")
    
    limit = args.limit or 10
    try:
        resp = requests.get(f"{API_BASE}/decisions/recent?limit={limit}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            decisions = data.get('decisions', [])
            if not decisions:
                print("暂无决策记录")
                return
            for d in decisions:
                status = "✅" if d.get('executed') else "⏳"
                auto = "🤖" if d.get('auto_approved') else "👤"
                print(f"{status} [{d.get('id')[:8]}] {d.get('context', {}).get('trigger', 'N/A')} | 风险:{d.get('risk_level')}/10 {auto}")
        else:
            # 从本地数据库获取
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT id, context, risk_level, decision, auto_approved, executed FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,))
            for row in cur.fetchall():
                status = "✅" if row[5] else "⏳"
                auto = "🤖" if row[4] else "👤"
                ctx = json.loads(row[1]) if row[1] else {}
                print(f"{status} [{row[0][:8]}] {ctx.get('trigger', 'N/A')} | 风险:{row[2]}/10 {auto}")
            conn.close()
    except Exception as e:
        print_error(f"获取失败: {e}")

# ============ 风险评估命令 ============

def cmd_risk(args):
    """执行风险评估"""
    print_header("风险评估")
    
    payload = {}
    if args.cpu:
        payload['cpu'] = args.cpu
    if args.memory:
        payload['memory'] = args.memory
    if args.disk:
        payload['disk'] = args.disk
    if args.error_rate:
        payload['error_rate'] = args.error_rate
    
    if not payload:
        print_warning("未提供评估参数，使用默认检查")
        # 获取系统当前状态
        import psutil
        payload = {
            'cpu': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'error_rate': 0
        }
        print(f"系统状态: CPU={payload['cpu']}% MEM={payload['memory']}% DISK={payload['disk']}%")
    
    try:
        resp = requests.post(f"{API_BASE}/risk/assess", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            level = data.get('risk_level', 0)
            if level >= 7:
                print_error(f"风险等级: {level}/10 (高风险)")
            elif level >= 4:
                print_warning(f"风险等级: {level}/10 (中风险)")
            else:
                print_success(f"风险等级: {level}/10 (低风险)")
            
            print(f"评估详情: {data.get('details', {})}")
            if data.get('recommendations'):
                print("建议:")
                for r in data.get('recommendations', []):
                    print(f"  - {r}")
        else:
            print_error(f"评估失败: {resp.text}")
    except requests.exceptions.RequestException as e:
        print_error(f"连接失败: {e}")

# ============ 规则命令 ============

def cmd_rules(args):
    """管理规则"""
    if args.list:
        print_header("规则列表")
        try:
            resp = requests.get(f"{API_BASE}/rules", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                rules = data.get('rules', [])
                if not rules:
                    print("暂无规则")
                    return
                for r in rules:
                    enabled = "✅" if r.get('enabled') else "❌"
                    print(f"{enabled} [{r.get('id')}] {r.get('name')}")
                    print(f"   类型: {r.get('type')} | 条件: {r.get('condition', 'N/A')}")
            else:
                print_error(f"获取失败: {resp.status_code}")
        except Exception as e:
            print_error(f"错误: {e}")
    
    elif args.enable:
        try:
            resp = requests.post(f"{API_BASE}/rules/{args.enable}/enable", timeout=5)
            if resp.status_code == 200:
                print_success(f"规则 {args.enable} 已启用")
            else:
                print_error(f"启用失败: {resp.text}")
        except Exception as e:
            print_error(f"错误: {e}")
    
    elif args.disable:
        try:
            resp = requests.post(f"{API_BASE}/rules/{args.disable}/disable", timeout=5)
            if resp.status_code == 200:
                print_success(f"规则 {args.disable} 已禁用")
            else:
                print_error(f"禁用失败: {resp.text}")
        except Exception as e:
            print_error(f"错误: {e}")

# ============ 行动命令 ============

def cmd_execute(args):
    """执行决策行动"""
    print_header("执行行动")
    
    decision_id = args.decision_id
    if not decision_id:
        print_error("需要提供决策ID (--id)")
        return
    
    try:
        resp = requests.post(f"{API_BASE}/decisions/{decision_id}/execute", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            print_success(f"执行成功")
            print(f"结果: {data.get('result')}")
            print(f"输出: {data.get('output', 'N/A')}")
        else:
            print_error(f"执行失败: {resp.text}")
    except requests.exceptions.RequestException as e:
        print_error(f"连接失败: {e}")

# ============ 自动化命令 ============

def cmd_automation(args):
    """管理自动化"""
    if args.list:
        print_header("自动化规则")
        try:
            resp = requests.get(f"http://localhost:18128/automations", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                automations = data.get('automations', [])
                for a in automations:
                    enabled = "✅" if a.get('enabled') else "❌"
                    print(f"{enabled} [{a.get('id')}] {a.get('name')}")
                    print(f"   触发: {a.get('trigger_type')} | 目标: {a.get('target')}")
            else:
                print_error(f"获取失败: {resp.status_code}")
        except Exception as e:
            print_error(f"错误: {e}")
    
    elif args.trigger:
        print_header("手动触发自动化")
        try:
            resp = requests.post(f"http://localhost:18128/automations/{args.trigger}/trigger", timeout=10)
            if resp.status_code == 200:
                print_success(f"自动化 {args.trigger} 已触发")
            else:
                print_error(f"触发失败: {resp.text}")
        except Exception as e:
            print_error(f"错误: {e}")

# ============ 健康检查 ============

def cmd_health(args):
    """检查服务健康状态"""
    print_header("服务健康检查")
    
    services = [
        ("决策引擎API", "http://localhost:18120/health"),
        ("Web仪表盘", "http://localhost:18121/health"),
        ("自动化引擎", "http://localhost:18128/health"),
    ]
    
    all_healthy = True
    for name, url in services:
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                print_success(f"{name}: 健康")
            else:
                print_error(f"{name}: 异常 ({resp.status_code})")
                all_healthy = False
        except:
            print_error(f"{name}: 离线")
            all_healthy = False
    
    if all_healthy:
        print("\n🎉 所有服务运行正常")
    else:
        print("\n⚠️  部分服务异常")


def cmd_learn(args):
    """增强学习与预测命令"""
    # 动态导入增强模块
    try:
        from feedback import EnhancedFeedbackLoop, FeedbackLoop
    except ImportError:
        print_error("无法导入反馈模块")
        return
    
    # 初始化增强反馈系统
    efb = EnhancedFeedbackLoop()
    
    if args.stats:
        print_header("增强学习统计")
        stats = efb.get_enhanced_stats()
        
        print(f"\n📊 基础统计:")
        print(f"   总反馈: {stats.get('total_feedback', 0)}")
        print(f"   成功: {stats.get('successful', 0)}")
        print(f"   失败: {stats.get('failed', 0)}")
        print(f"   成功率: {stats.get('success_rate', 0):.1%}")
        
        lr = stats.get('learning_rate', {})
        print(f"\n📈 学习率:")
        print(f"   当前: {lr.get('current_rate', 0):.4f}")
        print(f"   连续成功: {lr.get('success_streak', 0)}")
        print(f"   连续失败: {lr.get('failure_streak', 0)}")
        
        print(f"\n🎯 模式聚类:")
        print(f"   聚类数: {stats.get('pattern_clusters', 0)}")
        
        insights = stats.get('cluster_insights', [])
        for i, insight in enumerate(insights[:3]):
            print(f"   聚类{i}: 成功率 {insight.get('success_rate', 0):.1%}, 最佳动作: {insight.get('best_action', 'N/A')}")
        
        print(f"\n🔮 预测:")
        print(f"   失败序列数: {stats.get('predictor_predictions', 0)}")
        
        opt = stats.get('optimization', {})
        print(f"\n⚡ 优化:")
        print(f"   总优化次数: {opt.get('total_optimizations', 0)}")
        print(f"   活跃调整: {opt.get('active_adjustments', 0)}")
        
    elif args.predict:
        print_header("预测潜在问题")
        
        # 解析上下文
        context = {}
        if args.context:
            for kv in args.context:
                if '=' in kv:
                    key, value = kv.split('=', 1)
                    try:
                        context[key] = float(value)
                    except:
                        context[key] = value
        
        if not context:
            # 使用默认上下文
            context = {'cpu_percent': 85, 'memory_percent': 80, 'error_count': 2}
            
        print(f"📊 输入上下文: {context}")
        
        predictions = efb.get_predictions(context)
        
        if predictions:
            print(f"\n⚠️  检测到 {len(predictions)} 个潜在问题:")
            for i, p in enumerate(predictions, 1):
                print(f"\n   [{i}] {p.get('type', 'unknown')}")
                print(f"       置信度: {p.get('confidence', 0):.1%}")
                print(f"       消息: {p.get('message', '')}")
                print(f"       建议: {p.get('suggested_action', 'N/A')}")
        else:
            print_success("未检测到潜在问题")
            
    elif args.optimize:
        print_header("规则优化")
        
        # 获取当前规则
        try:
            resp = requests.get(f"{API_BASE}/rules", timeout=5)
            if resp.status_code == 200:
                rules = resp.json()
            else:
                rules = []
        except:
            rules = []
            print_warning("无法获取规则，使用示例规则")
            rules = [
                {'id': 'cpu_high', 'action': 'scale_up', 'threshold': 80, 'type': 'upper'},
                {'id': 'mem_high', 'action': 'alert', 'threshold': 85, 'type': 'upper'}
            ]
        
        if not rules:
            print_warning("没有可优化的规则")
            return
            
        print(f"📋 分析 {len(rules)} 条规则...")
        
        optimizations = efb.optimize_rules(rules)
        
        if optimizations:
            print(f"\n⚡ 生成 {len(optimizations)} 条优化建议:")
            for i, opt in enumerate(optimizations, 1):
                print(f"\n   [{i}] {opt.get('rule_id', 'N/A')}")
                print(f"       当前值: {opt.get('current_value', 'N/A')}")
                print(f"       建议: {opt.get('suggested_adjustment', {}).get('direction', 'N/A')}")
                print(f"       新值: {opt.get('suggested_adjustment', {}).get('new_value', 'N/A')}")
                print(f"       原因: {opt.get('reason', '')}")
        else:
            print_success("所有规则表现良好，无需优化")
            
    else:
        print("使用 --stats, --predict, 或 --optimize")
        print("示例:")
        print("  python cli.py learn --stats")
        print("  python cli.py learn --predict --context cpu_percent=90 memory_percent=85")
        print("  python cli.py learn --optimize")

# ============ 多智能体协作命令 ============

def cmd_collab(args):
    """多智能体协作"""
    from multi_agent import get_collaboration_engine, AgentRole
    
    engine = get_collaboration_engine()
    
    if args.collab_status:
        # 查看智能体状态
        print_header("多智能体状态")
        agents = engine.get_agent_status()
        for agent in agents:
            status_emoji = {
                "idle": "💤",
                "thinking": "🤔",
                "executing": "⚡",
                "waiting": "⏳",
                "blocked": "🚫",
                "error": "❌"
            }
            emoji = status_emoji.get(agent['status'], "❓")
            print(f"{emoji} {agent['name']} ({agent['role']}) - {agent['status']}")
            if agent.get('current_task'):
                print(f"   任务: {agent['current_task']}")
                
    elif args.collab_decide:
        # 发起协作决策
        print_header("发起协作决策")
        
        # 解析上下文
        context = {}
        if args.context:
            for kv in args.context:
                if '=' in kv:
                    key, val = kv.split('=', 1)
                    # 尝试转换为数字
                    try:
                        context[key] = float(val)
                    except:
                        context[key] = val
        else:
            context = {"trigger": "manual", "data": {"source": "cli"}}
            
        result = engine.collaborative_decide(context)
        
        print(f"\n📋 决策ID: {result['decision_id']}")
        print(f"\n🔍 分析结果:")
        analysis = result.get('analysis', {})
        print(f"   置信度: {analysis.get('confidence', 0):.0%}")
        print(f"   识别模式: {', '.join(analysis.get('patterns_identified', []))}")
        
        print(f"\n⚠️  风险评估:")
        risk = result.get('risk_assessment', {})
        print(f"   风险等级: {risk.get('risk_level', 'N/A')}")
        print(f"   风险分数: {risk.get('risk_score', 0)}/10")
        
        print(f"\n✅ 验证结果:")
        validation = result.get('validation', {})
        print(f"   验证状态: {'通过' if validation.get('is_valid') else '未通过'}")
        
        print(f"\n🎯 最终决策: {result.get('final_decision', {}).get('action', 'N/A')}")
        print(f"   摘要: {result.get('final_decision', {}).get('summary', '')}")
        
    elif args.collab_history:
        # 查看协作历史
        print_header("协作决策历史")
        history = engine.get_collaboration_history(limit=args.limit or 10)
        if history:
            for item in history:
                decision = item.get('final_decision', {})
                print(f"\n📌 {item['decision_id']}")
                print(f"   决策: {decision.get('action', 'N/A')}")
                print(f"   风险: {item.get('risk_assessment', {}).get('risk_level', 'N/A')}")
                print(f"   时间: {item.get('timestamp', '')}")
        else:
            print_warning("暂无协作历史")
            
    elif args.collab_task:
        # 创建任务
        print_header("创建协作任务")
        task_type = args.task_type or "general"
        description = args.description or "CLI创建的协作任务"
        
        task = engine.create_task(
            task_type=task_type,
            description=description,
            context={"source": "cli"},
            priority=args.priority or 2
        )
        print_success(f"任务已创建: {task.id}")
        
        # 自动分配
        available = engine.registry.get_available()
        if available:
            agent_ids = [a.id for a in available[:3]]
            engine.assign_task(task.id, agent_ids)
            print_success(f"任务已分配给 {len(agent_ids)} 个智能体")
            
    else:
        print("使用 --status, --decide, --history, 或 --task")
        print("示例:")
        print("  python cli.py collab --status          # 查看智能体状态")
        print("  python cli.py collab --decide          # 发起协作决策")
        print("  python cli.py collab --decide --context trigger=error")
        print("  python cli.py collab --history         # 查看协作历史")
        print("  python cli.py collab --task --type health --desc '健康检查任务'")

# ============ 主入口 ============

def main():
    parser = argparse.ArgumentParser(
        description="决策引擎CLI工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cli.py stats                    # 查看统计
  python cli.py decide                   # 发起决策
  python cli.py decisions                # 查看决策历史
  python cli.py risk --cpu 90            # 风险评估
  python cli.py rules --list             # 列出规则
  python cli.py rules --enable rule1     # 启用规则
  python cli.py execute --id <id>        # 执行决策
  python cli.py automation --list        # 列出自动化
  python cli.py health                   # 健康检查
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # stats命令
    subparsers.add_parser('stats', help='查看统计信息')
    
    # decide命令
    decide_parser = subparsers.add_parser('decide', help='发起决策')
    decide_parser.add_argument('--context', '-c', nargs='+', help='上下文键值对 (key=value)')
    decide_parser.add_argument('--auto-approve', action='store_true', help='自动审批')
    
    # decisions命令
    decisions_parser = subparsers.add_parser('decisions', help='查看决策历史')
    decisions_parser.add_argument('--limit', '-n', type=int, help='显示数量')
    
    # risk命令
    risk_parser = subparsers.add_parser('risk', help='风险评估')
    risk_parser.add_argument('--cpu', type=float, help='CPU使用率(%%)')
    risk_parser.add_argument('--memory', type=float, help='内存使用率(%%)')
    risk_parser.add_argument('--disk', type=float, help='磁盘使用率(%%)')
    risk_parser.add_argument('--error-rate', type=float, help='错误率(%%)')
    
    # rules命令
    rules_parser = subparsers.add_parser('rules', help='管理规则')
    rules_parser.add_argument('--list', '-l', action='store_true', help='列出所有规则')
    rules_parser.add_argument('--enable', metavar='ID', help='启用规则')
    rules_parser.add_argument('--disable', metavar='ID', help='禁用规则')
    
    # execute命令
    exec_parser = subparsers.add_parser('execute', help='执行决策')
    exec_parser.add_argument('--id', dest='decision_id', required=True, help='决策ID')
    
    # automation命令
    auto_parser = subparsers.add_parser('automation', help='管理自动化')
    auto_parser.add_argument('--list', '-l', action='store_true', help='列出所有自动化')
    auto_parser.add_argument('--trigger', metavar='ID', help='手动触发自动化')
    
    # health命令
    subparsers.add_parser('health', help='服务健康检查')
    
    # learn命令 - 增强学习统计
    learn_parser = subparsers.add_parser('learn', help='增强学习与预测')
    learn_parser.add_argument('--stats', action='store_true', help='查看学习统计')
    learn_parser.add_argument('--predict', action='store_true', help='预测潜在问题')
    learn_parser.add_argument('--context', '-c', nargs='+', help='上下文键值对 (key=value)')
    learn_parser.add_argument('--optimize', action='store_true', help='优化规则')
    
    # collab命令 - 多智能体协作
    collab_parser = subparsers.add_parser('collab', help='多智能体协作')
    collab_parser.add_argument('--status', dest='collab_status', action='store_true', help='查看智能体状态')
    collab_parser.add_argument('--decide', dest='collab_decide', action='store_true', help='发起协作决策')
    collab_parser.add_argument('--history', dest='collab_history', action='store_true', help='查看协作历史')
    collab_parser.add_argument('--task', dest='collab_task', action='store_true', help='创建协作任务')
    collab_parser.add_argument('--context', '-c', nargs='+', help='上下文键值对')
    collab_parser.add_argument('--type', dest='task_type', help='任务类型')
    collab_parser.add_argument('--desc', dest='description', help='任务描述')
    collab_parser.add_argument('--priority', type=int, help='任务优先级')
    collab_parser.add_argument('--limit', '-n', type=int, help='显示数量')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 分发命令
    commands = {
        'stats': cmd_stats,
        'decide': cmd_decide,
        'decisions': cmd_decisions,
        'risk': cmd_risk,
        'rules': cmd_rules,
        'execute': cmd_execute,
        'automation': cmd_automation,
        'health': cmd_health,
        'learn': cmd_learn,
        'collab': cmd_collab,
    }
    
    if args.command in commands:
        commands[args.command](args)
    else:
        print_error(f"未知命令: {args.command}")

if __name__ == '__main__':
    main()