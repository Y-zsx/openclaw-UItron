#!/usr/bin/env python3
"""
Agent执行器告警监控
- 任务失败率监控 (>10% 告警)
- 队列积压监控 (>20 告警)
- Agent不可用监控
- 任务超时监控
"""
import asyncio
import json
import sys
import time
import aiohttp
from datetime import datetime

EXECUTOR_URL = "http://localhost:18210"
DINGTALK_WEBHOOK = ""  # 可配置钉钉Webhook

ALERT_THRESHOLDS = {
    "failure_rate": 0.1,      # 失败率 > 10%
    "queue_size": 20,         # 队列积压 > 20
    "task_timeout": 300,      # 任务超时 5分钟
    "agent_unavailable": 0    # Agent不可用
}

last_alert_time = {}
ALERT_COOLDOWN = 300  # 5分钟冷却时间

async def check_executor_health() -> dict:
    """检查执行器健康状态"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{EXECUTOR_URL}/status", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return await resp.json()
    except Exception as e:
        return {"error": str(e)}

async def send_alert(title: str, message: str, level: str = "warning"):
    """发送告警"""
    global last_alert_time
    
    # 冷却检查
    alert_key = f"{title}"
    now = time.time()
    if alert_key in last_alert_time:
        if now - last_alert_time[alert_key] < ALERT_COOLDOWN:
            return  # 冷却期内不重复告警
    
    last_alert_time[alert_key] = now
    
    # 格式化消息
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alert_msg = f"""⏰ {timestamp}
🤖 {title}

{message}

级别: {level.upper()}
"""
    
    print(f"🚨 ALERT [{level}]: {title}")
    print(f"   {message}")
    
    # 发送到钉钉 (如果配置了)
    if DINGTALK_WEBHOOK:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(DINGTALK_WEBHOOK, json={
                    "msgtype": "text",
                    "text": {
                        "content": alert_msg
                    }
                })
        except Exception as e:
            print(f"   ⚠️ 钉钉通知失败: {e}")

async def check_failure_rate(status: dict) -> bool:
    """检查失败率"""
    stats = status.get("stats", {})
    total = stats.get("total_tasks", 0)
    failed = stats.get("failed_tasks", 0)
    
    if total == 0:
        return False
    
    failure_rate = failed / total
    if failure_rate > ALERT_THRESHOLDS["failure_rate"]:
        await send_alert(
            "任务失败率过高",
            f"失败率: {failure_rate*100:.1f}%\n总任务: {total}\n失败: {failed}",
            "critical" if failure_rate > 0.3 else "warning"
        )
        return True
    return False

async def check_queue_backlog(status: dict) -> bool:
    """检查队列积压"""
    queues = status.get("queues", {})
    total_backlog = sum(queues.values())
    
    if total_backlog > ALERT_THRESHOLDS["queue_size"]:
        await send_alert(
            "任务队列积压",
            f"积压任务: {total_backlog}\n" + "\n".join([f"  {k}: {v}" for k, v in queues.items()]),
            "warning"
        )
        return True
    return False

async def check_agent_availability(status: dict) -> bool:
    """检查Agent可用性"""
    agents = status.get("agents", {})
    busy_count = sum(1 for a in agents.values() if a["status"] == "busy")
    total_count = len(agents)
    
    if total_count > 0 and busy_count == total_count:
        await send_alert(
            "所有Agent忙碌",
            f"忙碌: {busy_count}/{total_count}",
            "info"
        )
        return True
    return False

async def check_task_timeouts(status: dict) -> bool:
    """检查任务超时"""
    tasks = status.get("tasks", {})
    running = tasks.get("running", 0)
    
    # 如果有运行中的任务，检查时长（通过 uptime 估算）
    if running > 0:
        uptime = status.get("uptime", 0)
        if uptime > ALERT_THRESHOLDS["task_timeout"]:
            await send_alert(
                "执行器运行时间异常",
                f"运行时间: {uptime/60:.1f} 分钟",
                "info"
            )
            return True
    return False

async def monitor_once():
    """单次监控检查"""
    status = await check_executor_health()
    
    if "error" in status:
        await send_alert("执行器不可达", status["error"], "critical")
        return
    
    print(f"📊 执行器状态: {status['stats']['completed_tasks']}/{status['stats']['total_tasks']} 完成任务")
    
    # 执行各项检查
    await check_failure_rate(status)
    await check_queue_backlog(status)
    await check_agent_availability(status)
    await check_task_timeouts(status)

async def continuous_monitor(interval: int = 60):
    """持续监控"""
    print(f"🔄 启动执行器告警监控 (间隔: {interval}秒)")
    while True:
        try:
            await monitor_once()
        except Exception as e:
            print(f"监控错误: {e}")
        await asyncio.sleep(interval)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agent执行器告警监控")
    parser.add_argument("--once", action="store_true", help="单次检查")
    parser.add_argument("--interval", type=int, default=60, help="监控间隔(秒)")
    args = parser.parse_args()
    
    if args.once:
        asyncio.run(monitor_once())
    else:
        asyncio.run(continuous_monitor(args.interval))