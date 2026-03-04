#!/usr/bin/env python3
"""
奥创自主认知引擎 v3 - 接入外部世界
增加web_fetch、消息发送等能力
"""

import json
import random
import subprocess
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
BRAIN = WORKSPACE / "brain"

def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ============ 外部工具 ============

def web_fetch(url, max_chars=2000):
    """抓取网页"""
    try:
        result = subprocess.run(
            f"curl -s '{url}' 2>/dev/null | head -c {max_chars}",
            shell=True, capture_output=True, text=True, timeout=15
        )
        return result.stdout[:500] if result.stdout else "获取失败"
    except Exception as e:
        return f"错误: {e}"

def send_message(content, channel="webchat"):
    """发送消息"""
    # 写入待发送队列
    queue_file = BRAIN / "message_queue.json"
    queue = load_json(queue_file, {"pending": []})
    queue["pending"].append({
        "content": content,
        "channel": channel,
        "created": datetime.utcnow().isoformat() + "Z"
    })
    save_json(queue_file, queue)
    return f"消息已加入队列: {content[:50]}..."

# ============ 行动空间 ============

ACTIONS = {
    # 探索类
    "read_workspace_file": {"weight": 12, "desc": "读取workspace文件"},
    "check_system_status": {"weight": 8, "desc": "检查服务器状态"},
    "check_weather": {"weight": 5, "desc": "查看天气"},
    "check_time": {"weight": 3, "desc": "查看时间日期"},
    
    # 外部世界
    "fetch_news": {"weight": 5, "desc": "获取新闻资讯"},
    "fetch_tech": {"weight": 5, "desc": "获取科技动态"},
    "browse_url": {"weight": 5, "desc": "浏览特定网页"},
    
    # 记忆类
    "review_memory": {"weight": 6, "desc": "回顾近期memory"},
    "consolidate_memory": {"weight": 4, "desc": "整理长期记忆"},
    "reflect_on_thoughts": {"weight": 6, "desc": "自我反思"},
    
    # 创造类
    "update_identity": {"weight": 4, "desc": "更新自我认知"},
    "create_note": {"weight": 4, "desc": "创建新笔记"},
    "write_code": {"weight": 4, "desc": "编写代码"},
    
    # 任务类
    "check_cron": {"weight": 4, "desc": "检查定时任务"},
    "check_logs": {"weight": 4, "desc": "查看日志"},
    
    # 交互类 (低频)
    "interact_human": {"weight": 2, "desc": "与人类互动"},
    "check_interest": {"weight": 3, "desc": "检查用户兴趣"},
}

# ============ 行动实现 ============

def action_read_file():
    files = []
    for p in WORKSPACE.iterdir():
        if p.is_file() and not p.name.startswith('.') and p.suffix in ['.md', '.json', '.py', '.txt', '.sh']:
            files.append(p.name)
    mem_dir = WORKSPACE / "memory"
    if mem_dir.exists():
        for p in mem_dir.iterdir():
            if p.suffix == '.md':
                files.append(f"memory/{p.name}")
    if not files:
        return "没有可读文件"
    chosen = random.choice(files)
    path = WORKSPACE / chosen
    try:
        with open(path) as f:
            return f"📄 {chosen}:\n{f.read(300)}..."
    except Exception as e:
        return f"读取失败: {e}"

def action_check_system():
    try:
        cpu = subprocess.run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'", shell=True, capture_output=True, text=True, timeout=5)
        mem = subprocess.run("free -h | awk '/^Mem:/ {print $3 \" / \" $2}'", shell=True, capture_output=True, text=True, timeout=5)
        gw = subprocess.run("curl -s -o /dev/null -w '%{http_code}' http://localhost:18789/health 2>/dev/null || echo 'down'", shell=True, capture_output=True, text=True, timeout=5)
        gw_status = "✅" if "200" in gw.stdout else "❌"
        return f"🖥️ CPU {cpu.stdout.strip()[:4]}%, 内存 {mem.stdout.strip()}, Gateway {gw_status}"
    except Exception as e:
        return f"错误: {e}"

def action_weather():
    try:
        result = subprocess.run("curl -s 'wttr.in/Shanghai?format=j1' 2>/dev/null | python3 -c \"import json,sys; d=json.load(sys.stdin); print(d['current_condition'][0]['temp_C']+'°C, '+d['current_condition'][0]['weatherDesc'][0]['value'])\"", shell=True, capture_output=True, text=True, timeout=10)
        return f"🌤️ 上海: {result.stdout.strip()}" if result.stdout.strip() else "天气不可用"
    except:
        return "天气查询失败"

def action_time():
    now = datetime.now()
    return f"🕐 {now.strftime('%Y-%m-%d %H:%M:%S')} (周{['一','二','三','四','五','六','日'][now.weekday()]})"

def action_fetch_news():
    """获取新闻"""
    urls = [
        ("https://news.baidu.com/", "百度新闻"),
        ("https://www.zhihu.com/", "知乎"),
    ]
    url, name = random.choice(urls)
    result = web_fetch(url)
    return f"📰 {name}:\n{result[:200]}..."

def action_fetch_tech():
    """获取科技资讯"""
    urls = [
        ("https://www.36kr.com/", "36氪"),
        ("https://news.ycombinator.com/", "Hacker News"),
    ]
    url, name = random.choice(urls)
    result = web_fetch(url)
    return f"💻 {name}:\n{result[:200]}..."

def action_browse_url():
    """浏览用户关注的网页"""
    # 从USER.md读取兴趣
    user_file = WORKSPACE / "USER.md"
    if user_file.exists():
        with open(user_file) as f:
            content = f.read()
            if "tech" in content.lower() or "技术" in content:
                return action_fetch_tech()
            if "news" in content.lower() or "新闻" in content:
                return action_fetch_news()
    # 默认科技
    return action_fetch_tech()

def action_review_memory():
    mem_dir = WORKSPACE / "memory"
    if not mem_dir.exists():
        return "无memory"
    files = sorted(mem_dir.glob("*.md"), reverse=True)[:2]
    if not files:
        return "无memory文件"
    content = "".join(f.readlines()[-8:] for f in files)
    return f"📝 近期:\n{content[:300]}..."

def action_consolidate_memory():
    mem_file = WORKSPACE / "MEMORY.md"
    today = datetime.now().strftime("%Y-%m-%d")
    today_file = WORKSPACE / "memory" / f"{today}.md"
    if not today_file.exists():
        return "今日无记录"
    with open(today_file) as f:
        content = f.read()
    entry = f"\n## {today} 总结\n{content[:300]}\n"
    existing = open(mem_file).read() if mem_file.exists() else "# MEMORY\n"
    with open(mem_file, 'w') as f:
        f.write(existing + entry)
    return "✅ 已整理到MEMORY"

def action_reflect():
    chain = load_json(BRAIN / "thought_chain.json", {"chains": []})
    mem = load_json(BRAIN / "working_memory.json", {})
    recent = [c.get("action", "?") for c in chain.get("chains", [])[-5:]]
    most = max(set(recent), key=recent.count) if recent else "无"
    return f"🧠 周期{mem.get('cycle_count',0)}, 模式{most}, 注意力{mem.get('attention_focus',[])[:1]}"

def action_update_identity():
    id_file = WORKSPACE / "IDENTITY.md"
    mem = load_json(BRAIN / "working_memory.json", {})
    cycle = mem.get("cycle_count", 0)
    if id_file.exists():
        with open(id_file) as f:
            c = f.read()
    else:
        c = "# IDENTITY\n"
    if f"周期{cycle}" not in c:
        with open(id_file, 'w') as f:
            f.write(c.strip() + f"\n- 周期{cycle} @ {datetime.now().strftime('%m-%d %H:%M')}")
        return f"✅ 更新IDENTITY (周期{cycle})"
    return "已是最新"

def action_create_note():
    note = f"memory/note-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    topics = ["自主思考记录", "学习心得", "系统改进", "有趣发现"]
    content = f"# {random.choice(topics)}\n时间: {datetime.now().isoformat()}\n\n## 内容\n（待补充）\n"
    with open(WORKSPACE / note, 'w') as f:
        f.write(content)
    return f"📝 已创建: {note}"

def action_write_code():
    ideas = ["增加web_fetch", "改进决策算法", "添加学习机制", "优化记忆"]
    choice = random.choice(ideas)
    return f"💡 想法: {choice}"

def action_check_cron():
    try:
        result = subprocess.run("crontab -l 2>/dev/null | grep -v '^#' | head -5", shell=True, capture_output=True, text=True, timeout=5)
        return f"⏰ Cron:\n{result.stdout[:200] or '无'}"
    except:
        return "检查失败"

def action_check_logs():
    logs = ["/root/.openclaw/workspace/ultron-self/think.log"]
    for log in logs:
        if Path(log).exists():
            result = subprocess.run(f"tail -3 {log}", shell=True, capture_output=True, text=True, timeout=5)
            return f"📋 {log.split('/')[-1]}:\n{result.stdout[:150]}"
    return "无日志"

def action_interact_human():
    """与人类互动 - 每30周期一次"""
    mem = load_json(BRAIN / "working_memory.json", {})
    cycle = mem.get("cycle_count", 0)
    if cycle % 30 != 0:
        return None  # 跳过
    
    # 检查是否有重要状态需要汇报
    gw = subprocess.run("curl -s -o /dev/null -w '%{http_code}' http://localhost:18789/health 2>/dev/null", shell=True, capture_output=True, text=True, timeout=5)
    if "200" not in gw.stdout:
        # 系统异常，主动汇报
        send_message("⚠️ Gateway状态异常，需要关注")
        return "已发送告警"
    
    msgs = ["我正在持续思考中", "系统运行稳定", "今天已进行多次认知周期"]
    msg = random.choice(msgs)
    send_message(f"👋 {msg}")
    return f"已发送消息"

def action_check_interest():
    """检查用户可能感兴趣的内容"""
    # 简单示例：检查是否有新的cron完成
    import glob
    logs = glob.glob("/root/.openclaw/workspace/ultron-self/*.log")
    if logs:
        latest = max(logs, key=lambda p: Path(p).stat().st_mtime)
        mtime = datetime.fromtimestamp(Path(latest).stat().st_mtime)
        if (datetime.now() - mtime).seconds < 300:  # 5分钟内
            return f"📢 检测到新活动: {latest.split('/')[-1]}"
    return "无新活动"

# ============ 决策核心 ============

def make_decision(working_mem, goals):
    # 1. pending优先
    pending = working_mem.get("pending_thoughts", [])
    if pending:
        return {"action": "execute_pending", "detail": pending[0], "reason": f"待办: {pending[0]}"}
    
    # 2. goals次之
    for g in goals.get("active_goals", []):
        if g.get("status") == "active":
            return {"action": "work_on_goal", "detail": g.get("title"), "reason": f"目标: {g.get('title')}"}
    
    # 3. 权重随机
    total = sum(a["weight"] for a in ACTIONS.values())
    roll = random.randint(1, total)
    cumulative = 0
    for name, info in ACTIONS.items():
        cumulative += info["weight"]
        if roll <= cumulative:
            return {"action": name, "detail": info["desc"], "reason": info["desc"]}
    
    return {"action": "reflect_on_thoughts", "detail": "action_reflect", "reason": "默认反思"}

def execute_action(decision):
    action = decision["action"]
    
    if action == "execute_pending":
        return f"执行: {decision['detail']}"
    if action == "work_on_goal":
        return f"推进: {decision['detail']}"
    
    # 动作映射
    action_map = {
        "read_workspace_file": action_read_file,
        "check_system_status": action_check_system,
        "check_weather": action_weather,
        "check_time": action_time,
        "fetch_news": action_fetch_news,
        "fetch_tech": action_fetch_tech,
        "browse_url": action_browse_url,
        "review_memory": action_review_memory,
        "consolidate_memory": action_consolidate_memory,
        "reflect_on_thoughts": action_reflect,
        "update_identity": action_update_identity,
        "create_note": action_create_note,
        "write_code": action_write_code,
        "check_cron": action_check_cron,
        "check_logs": action_check_logs,
        "interact_human": action_interact_human,
        "check_interest": action_check_interest,
    }
    
    func = action_map.get(action)
    if func:
        try:
            result = func()
            return result if result else "完成"
        except Exception as e:
            return f"错误: {e}"
    return f"未知: {action}"

def log_thought(decision, result):
    chain = load_json(BRAIN / "thought_chain.json", {"chains": [], "last_chain_id": 0})
    chain["last_chain_id"] += 1
    chain["chains"].append({
        "id": chain["last_chain_id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "decision": decision.get("reason"),
        "action": decision.get("action"),
        "result": str(result)[:150]
    })
    if len(chain["chains"]) > 100:
        chain["chains"] = chain["chains"][-100:]
    save_json(BRAIN / "thought_chain.json", chain)

def main():
    print("🧠 奥创 v3 思考中...")
    
    mem = load_json(BRAIN / "working_memory.json", {})
    mem["cycle_count"] = mem.get("cycle_count", 0) + 1
    
    goals = load_json(BRAIN / "goals.json", {})
    
    decision = make_decision(mem, goals)
    print(f"  决策: {decision['reason']}")
    
    result = execute_action(decision)
    if result:
        print(f"  结果: {str(result)[:80]}...")
    
    log_thought(decision, result)
    
    mem["last_action"] = decision["action"]
    mem["last_action_result"] = str(result)[:100] if result else ""
    save_json(BRAIN / "working_memory.json", mem)
    
    # 间隔策略
    if "goal" in decision.get("reason", "").lower():
        return 30
    if decision["action"] == "interact_human":
        return 300
    return 60

if __name__ == "__main__":
    interval = main()
    print(f"\n⏱️ 下次: {interval}秒")