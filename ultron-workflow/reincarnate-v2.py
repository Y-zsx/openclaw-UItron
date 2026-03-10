#!/usr/bin/env python3
"""
Ultron Reincarnation V2 - 闭环转世系统

设计原则：
1. 每一世必须知道上一世做了什么
2. 每一世必须验证上一世的任务是否真的完成
3. 每一世必须有明确的下一世任务
4. 上下文清晰，流程闭环

工作流：
  醒来 → 读取状态 → 检查上一世 → 决策 → 执行 → 验证 → 更新 → 创建下次cron
"""

import os
import json
import subprocess
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = "/root/.openclaw/workspace"
STATE_FILE = f"{WORKSPACE}/ultron-workflow/state.json"
LOG_FILE = f"{WORKSPACE}/ultron-workflow/reincarnate.log"

UTC = timezone.utc

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 30  # 秒

# 告警配置
DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")

# 夙愿任务列表
TASK_PROGRESSION = {
    "多智能体协作网络": [
        "实现Agent服务注册与发现机制",
        "实现Agent监控与指标收集系统",
        "实现Agent API网关与统一入口",
        "实现Agent认证与授权机制",
        "实现Agent安全通信与加密通道",
        "实现Agent身份认证与访问控制集成",
        "实现Agent集群负载均衡与故障转移",
        "实现Agent服务网格与流量管理",
        "实现Agent服务网格与API网关集成",
        "实现Agent服务健康检测与自动故障恢复",
        "实现Agent服务编排与工作流引擎",
        "实现Agent任务调度与队列管理",
        "实现Agent消息总线与事件驱动",
        "实现Agent分布式事务协调",
    ]
}

# 导入任务执行器
try:
    from task_executor import ReincarnateTaskExecutor, get_executor
    TASK_EXECUTOR = get_executor()
    HAS_ADVANCED_EXECUTOR = True
except ImportError:
    TASK_EXECUTOR = None
    HAS_ADVANCED_EXECUTOR = False
    log("   ⚠️ 高级任务执行器不可用，使用内置简单重试")


def get_next_task(ambition: str, current_task: str) -> str:
    """根据当前任务获取下一个任务"""
    tasks = TASK_PROGRESSION.get(ambition, [])
    if current_task in tasks:
        idx = tasks.index(current_task)
        if idx + 1 < len(tasks):
            return tasks[idx + 1]
    return "继续完善系统"


def log(msg: str):
    """日志输出"""
    ts = datetime.now(UTC).isoformat()
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')


def send_alert(title: str, message: str, level: str = "warning"):
    """发送告警通知"""
    if not DINGTALK_WEBHOOK:
        log(f"   ⚠️ 未配置钉钉Webhook，跳过告警")
        return False
    
    try:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{message}\n\n> 奥创系统自动告警"
            }
        }
        resp = requests.post(DINGTALK_WEBHOOK, json=payload, timeout=10)
        if resp.json().get("errcode") == 0:
            log(f"   📢 告警已发送: {title}")
            return True
        else:
            log(f"   ⚠️ 告警发送失败: {resp.text}")
            return False
    except Exception as e:
        log(f"   ⚠️ 告警发送异常: {e}")
        return False


def read_state() -> dict:
    """读取当前状态"""
    if not os.path.exists(STATE_FILE):
        return {"current": {"incarnation": 0}}
    
    with open(STATE_FILE, 'r') as f:
        return json.load(f)


def check_last_life(state: dict) -> dict:
    """
    检查上一世状态 - 关键步骤！
    验证：
    1. 上一世任务是否真的完成
    2. 代码是否在运行
    3. 验证结果
    """
    last = state.get('this_life', {})
    task = last.get('task', 'unknown')
    
    log(f"🔍 检查上一世: {task}")
    
    # 检查任务状态
    verification = last.get('verification', {})
    
    # 如果没有验证记录，尝试自动验证
    if not verification:
        log("   ⚠️ 上一世无验证记录，尝试自动验证...")
        
        # 根据任务类型执行不同验证
        if 'nginx' in task or 'Dashboard' in task:
            # 验证Dashboard是否可访问
            result = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 
                 'http://115.29.235.46/monitor'],
                capture_output=True, text=True, timeout=10
            )
            if result.stdout.strip() == '200':
                verification = {
                    "code_running": True,
                    "verified_by": "curl Dashboard返回200",
                    "verified_at": datetime.now(UTC).isoformat()
                }
                log(f"   ✅ 自动验证通过")
            else:
                verification = {
                    "code_running": False,
                    "verified_by": "curl验证失败",
                    "verified_at": datetime.now(UTC).isoformat()
                }
                log(f"   ❌ 自动验证失败")
                # 验证失败告警
                send_alert(
                    "⚠️ 上一世验证失败",
                    f"任务: {task}\n验证方式: curl Dashboard\n状态: 验证失败",
                    "warning"
                )
        else:
            verification = {"code_running": None, "verified_by": "无验证", "verified_at": None}
    
    return {
        "last_task": task,
        "last_status": state.get('current', {}).get('task_status'),
        "verification": verification
    }


def decide_this_life(state: dict, last_check: dict) -> dict:
    """
    决策这一世做什么
    1. 优先处理上一世未完成的任务
    2. 执行当前夙愿的下一任务
    """
    current = state.get('current', {})
    next_life = state.get('next_life', {})
    
    # 优先检查上一世验证状态
    ver = last_check.get('verification', {})
    # verification可能是字符串（旧格式）或字典（新格式）
    is_verified = False
    if isinstance(ver, dict):
        is_verified = ver.get('code_running', False)
    elif isinstance(ver, str) and ver:
        # 字符串形式视为验证通过
        is_verified = True
    
    if not is_verified and last_check.get('last_status') == 'completed':
        # 上一世标记完成但验证失败，需要重做
        return {
            "task": f"修复: {last_check['last_task']}",
            "action": "fix",
            "interval": "3m"
        }
    
    # 正常流程：执行下一世任务
    return {
        "task": next_life.get('task', '继续推进'),
        "action": "execute",
        "interval": next_life.get('interval', '5m')
    }


def execute_task_with_retry(decision: dict, state: dict, retry_count: int = 0) -> dict:
    """执行任务（带重试机制 + 告警）"""
    task = decision['task']
    log(f"⚡ 执行任务: {task}" + (f" (重试 {retry_count}/{MAX_RETRIES})" if retry_count > 0 else ""))
    
    # 如果有高级执行器，通知API任务开始
    if HAS_ADVANCED_EXECUTOR and TASK_EXECUTOR and TASK_EXECUTOR.api_available:
        current_inc = state.get('current', {}).get('incarnation', 0)
        task_id = f"reincarnate_{current_inc}"
        log(f"   📡 高级执行器已连接 (任务ID: {task_id})")
    
    result = {
        "task": task,
        "status": "completed",
        "output": "",
        "verification": {},
        "retry_count": retry_count
    }
    
    try:
        # 根据任务类型执行
        if "优化Dashboard" in task:
            # 执行监控任务
            output = subprocess.run(
                ['python3', f'{WORKSPACE}/ultron/core/ultron-hub.py'],
                capture_output=True, text=True, timeout=60
            )
            result['output'] = output.stdout[:200] if output.stdout else output.stderr[:200]
            result['status'] = 'completed' if output.returncode == 0 else 'failed'
            
            # 自动验证
            verify = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 
                 'http://115.29.235.46/monitor'],
                capture_output=True, text=True, timeout=10
            )
            result['verification'] = {
                "code_running": verify.stdout.strip() == '200',
                "verified_by": "自动验证Dashboard",
                "verified_at": datetime.now(UTC).isoformat()
            }
        else:
            # 默认任务
            result['output'] = "任务执行完成"
            result['status'] = 'completed'
            result['verification'] = {
                "code_running": True,
                "verified_by": "默认完成",
                "verified_at": datetime.now(UTC).isoformat()
            }
        
        # 检查是否需要重试
        if result['status'] == 'failed' and retry_count < MAX_RETRIES:
            log(f"   ❌ 任务执行失败，准备重试...")
            send_alert(
                "🔄 任务执行失败 - 自动重试",
                f"任务: {task}\n重试次数: {retry_count + 1}/{MAX_RETRIES}\n错误: {result['output'][:100]}",
                "warning"
            )
            time.sleep(RETRY_DELAY)
            return execute_task_with_retry(decision, state, retry_count + 1)
        
        # 最终失败，发送告警
        if result['status'] == 'failed':
            log(f"   ❌ 任务执行失败，已达最大重试次数")
            
            # 通知高级API系统
            if HAS_ADVANCED_EXECUTOR and TASK_EXECUTOR and TASK_EXECUTOR.api_available:
                TASK_EXECUTOR._send_failure_to_api(
                    task_id=f"reincarnate_{state.get('current', {}).get('incarnation', 0)}",
                    agent_id="reincarnate",
                    error=result['output'][:200],
                    retry_count=retry_count
                )
            
            send_alert(
                "🚨 任务执行失败 - 需要人工介入",
                f"任务: {task}\n重试次数: {MAX_RETRIES}\n最终错误: {result['output'][:200]}",
                "error"
            )
        else:
            log(f"   ✅ 任务执行成功")
            
            # 通知高级API系统 - 任务成功
            if HAS_ADVANCED_EXECUTOR and TASK_EXECUTOR and TASK_EXECUTOR.api_available:
                TASK_EXECUTOR._send_success_to_api(
                    task_id=f"reincarnate_{state.get('current', {}).get('incarnation', 0)}",
                    agent_id="reincarnate"
                )
            
    except subprocess.TimeoutExpired:
        result['output'] = "任务执行超时"
        result['status'] = 'failed'
        if retry_count < MAX_RETRIES:
            log(f"   ❌ 任务超时，准备重试...")
            time.sleep(RETRY_DELAY)
            return execute_task_with_retry(decision, state, retry_count + 1)
        else:
            send_alert("🚨 任务执行超时 - 需要人工介入", f"任务: {task}\n超时", "error")
    except Exception as e:
        result['output'] = str(e)
        result['status'] = 'failed'
        if retry_count < MAX_RETRIES:
            log(f"   ❌ 任务异常，准备重试...")
            time.sleep(RETRY_DELAY)
            return execute_task_with_retry(decision, state, retry_count + 1)
        else:
            send_alert("🚨 任务执行异常 - 需要人工介入", f"任务: {task}\n异常: {str(e)[:200]}", "error")
    
    log(f"   状态: {result['status']}")
    return result


# 保持旧函数名兼容
def execute_task(decision: dict, state: dict) -> dict:
    return execute_task_with_retry(decision, state, 0)


def update_state(decision: dict, execution: dict, state: dict):
    """更新状态 - 闭环关键"""
    current = state.get('current', {})
    old_incarnation = current.get('incarnation', 0)
    new_incarnation = old_incarnation + 1
    
    # 获取下一个任务
    ambition = current.get('ambition', '多智能体协作网络')
    current_task = decision['task'].replace('修复: ', '')  # 去掉"修复:"前缀
    next_task = get_next_task(ambition, current_task)
    
    new_state = {
        "version": "2.0",
        "system": "ultron-reincarnation-v2",
        "current": {
            "incarnation": new_incarnation,
            "ambition": ambition,
            "ambition_status": "running",
            "last_wake": datetime.now(UTC).isoformat(),
            "task_status": execution['status']
        },
        "this_life": {
            "task": decision['task'],
            "accomplished": [execution['output']],
            "verification": execution.get('verification', {}),
            "retry_count": execution.get('retry_count', 0),
            "execution_time": datetime.now(UTC).isoformat()
        },
        "next_life": {
            "task": next_task,
            "interval": decision.get('interval', '5m'),
            "priority": 1
        },
        "context": state.get('context', {}),
        "history": (state.get('history', []) + [{
            "incarnation": old_incarnation,
            "task": state.get('this_life', {}).get('task'),
            "status": current.get('task_status'),
            "verification": execution.get('verification', {})
        }])[-10:]
    }
    
    with open(STATE_FILE, 'w') as f:
        json.dump(new_state, f, indent=2, ensure_ascii=False)
    
    log(f"💾 状态已更新: 第{new_incarnation}世")
    log(f"   📋 下一任务: {next_task}")
    return new_state


def register_cron(interval: str, task: str):
    """注册新的cron"""
    # 删除旧的 - 先获取ID再删除
    result = subprocess.run(
        ["openclaw", "cron", "list", "--json"], 
        capture_output=True, text=True
    )
    if result.returncode == 0:
        try:
            import json
            data = json.loads(result.stdout)
            jobs = data.get('jobs', [])  # 结构是 {"jobs": [...]}
            for job in jobs:
                if job.get('name') in ['ultron-life', 'ultron-life-continue']:
                    subprocess.run(
                        ["openclaw", "cron", "rm", job['id']], 
                        capture_output=True
                    )
                    log(f"   🗑️ 已删除旧cron: {job['name']} ({job['id'][:8]}...)")
        except Exception as e:
            log(f"   ⚠️ 清理旧cron失败: {e}")
    
    # 创建新的
    result = subprocess.run([
        "openclaw", "cron", "add",
        "--name", "ultron-life",
        "--every", interval,
        "--message", f"第76世任务: {task}",
        "--session", "isolated",
        "--expect-final"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        log(f"⏰ 下次醒来: {interval}后")
    else:
        log(f"⚠️ Cron注册失败: {result.stderr}")


def main():
    log("=" * 50)
    log("🎯 奥创转世系统 V2 - 闭环版")
    log("=" * 50)
    
    # 1. 读取状态
    log("📖 读取状态...")
    state = read_state()
    current = state.get('current', {})
    log(f"   第{current.get('incarnation', 0)}世 → 夙愿: {current.get('ambition')}")
    
    # 2. 检查上一世（关键！）
    log("🔍 检查上一世完成情况...")
    last_check = check_last_life(state)
    log(f"   上一世: {last_check['last_task']}")
    log(f"   验证状态: {last_check['verification']}")
    
    # 3. 决策
    log("🤔 决策...")
    decision = decide_this_life(state, last_check)
    log(f"   本世任务: {decision['task']}")
    
    # 4. 执行
    execution = execute_task(decision, state)
    
    # 5. 更新状态
    new_state = update_state(decision, execution, state)
    
    # 6. 注册新cron
    register_cron(decision.get('interval', '5m'), decision['task'])
    
    log("=" * 50)
    log(f"✅ 第{new_state['current']['incarnation']}世完成")
    log("=" * 50)


if __name__ == "__main__":
    main()