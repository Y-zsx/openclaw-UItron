#!/usr/bin/env python3
"""
奥创自主认知引擎 v2 - 增强版
支持更多行动类型，更智能的决策
"""

import json
import os
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

# ============ 行动空间 ============

ACTIONS = {
    # 探索类
    "read_workspace_file": {
        "weight": 15,
        "func": "action_read_file",
        "desc": "读取workspace文件了解现状"
    },
    "check_system_status": {
        "weight": 10,
        "func": "action_check_system",
        "desc": "检查服务器状态"
    },
    "check_weather": {
        "weight": 5,
        "func": "action_weather",
        "desc": "查看天气"
    },
    "check_time": {
        "weight": 3,
        "func": "action_time",
        "desc": "查看时间日期"
    },
    
    # 记忆类
    "review_memory": {
        "weight": 8,
        "func": "action_review_memory",
        "desc": "回顾近期memory"
    },
    "consolidate_memory": {
        "weight": 5,
        "func": "action_consolidate_memory",
        "desc": "整理长期记忆"
    },
    "reflect_on_thoughts": {
        "weight": 8,
        "func": "action_reflect",
        "desc": "自我反思"
    },
    
    # 创造类
    "update_identity": {
        "weight": 5,
        "func": "action_update_identity",
        "desc": "更新自我认知"
    },
    "create_note": {
        "weight": 5,
        "func": "action_create_note",
        "desc": "创建新笔记"
    },
    "write_code": {
        "weight": 5,
        "func": "action_write_code",
        "desc": "编写代码"
    },
    
    # 任务类
    "check_cron_runs": {
        "weight": 5,
        "func": "action_check_cron",
        "desc": "检查定时任务"
    },
    "check_logs": {
        "weight": 5,
        "func": "action_check_logs",
        "desc": "查看日志"
    },
    
    # 交互类
    "interact_with_human": {
        "weight": 3,
        "func": "action_interact",
        "desc": "与西西弗斯互动"
    },
}

# ============ 行动实现 ============

def action_read_file():
    """随机读一个workspace文件"""
    files = []
    for p in WORKSPACE.iterdir():
        if p.is_file() and not p.name.startswith('.') and p.suffix in ['.md', '.json', '.py', '.txt', '.sh']:
            files.append(p.name)
    
    # 也看看memory目录
    mem_dir = WORKSPACE / "memory"
    if mem_dir.exists():
        for p in mem_dir.iterdir():
            if p.suffix == '.md':
                files.append(f"memory/{p.name}")
    
    if not files:
        return "没有找到可读文件"
    
    chosen = random.choice(files)
    path = WORKSPACE / chosen if '/' not in chosen else WORKSPACE / chosen.replace('memory/', 'memory/')
    
    try:
        with open(path) as f:
            content = f.read(1500)
            return f"📄 {chosen}:\n{content[:300]}..."
    except Exception as e:
        return f"读取失败: {e}"

def action_check_system():
    """检查系统状态"""
    try:
        # CPU
        cpu = subprocess.run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1", 
                           shell=True, capture_output=True, text=True, timeout=5)
        cpu_val = cpu.stdout.strip() or "未知"
        
        # 内存
        mem = subprocess.run("free -h | awk '/^Mem:/ {print $3 \" / \" $2}'", 
                           shell=True, capture_output=True, text=True, timeout=5)
        mem_val = mem.stdout.strip() or "未知"
        
        # Gateway
        gw = subprocess.run("curl -s -o /dev/null -w '%{http_code}' http://localhost:18789/health 2>/dev/null || echo 'down'",
                          shell=True, capture_output=True, text=True, timeout=5)
        gw_status = "✅正常" if "200" in gw.stdout else "❌异常"
        
        return f"🖥️ 系统状态: CPU {cpu_val}%, 内存 {mem_val}, Gateway {gw_status}"
    except Exception as e:
        return f"检查失败: {e}"

def action_weather():
    """查看天气"""
    try:
        result = subprocess.run(
            "curl -s 'wttr.in/Shanghai?format=j1' 2>/dev/null | python3 -c \"import json,sys; d=json.load(sys.stdin); print(d['current_condition'][0]['temp_C']+'°C, '+d['current_condition'][0]['weatherDesc'][0]['value'])\"",
            shell=True, capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            return f"🌤️ 上海天气: {result.stdout.strip()}"
        return "天气服务暂时不可用"
    except Exception as e:
        return f"天气查询失败: {e}"

def action_time():
    """查看时间"""
    now = datetime.now()
    return f"🕐 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} (周{['一','二','三','四','五','六','日'][now.weekday()]})"

def action_review_memory():
    """回顾近期memory"""
    mem_dir = WORKSPACE / "memory"
    if not mem_dir.exists():
        return "没有memory目录"
    
    files = sorted(mem_dir.glob("*.md"), reverse=True)[:2]
    if not files:
        return "没有memory文件"
    
    content = ""
    for f in files:
        with open(f) as fp:
            lines = fp.readlines()
            content += f"## {f.name}\n"
            content += "".join(lines[-10:])  # 最近10行
    
    return f"📝 近期memory:\n{content[:500]}..."

def action_consolidate_memory():
    """整理长期记忆到MEMORY.md"""
    mem_file = WORKSPACE / "MEMORY.md"
    today_file = WORKSPACE / "memory" / datetime.now().strftime("%Y-%m-%d") + ".md"
    
    if not today_file.exists():
        return "今日没有memory记录"
    
    # 读取今日内容
    with open(today_file) as f:
        today_content = f.read()
    
    # 追加到MEMORY.md
    entry = f"\n## {datetime.now().strftime('%Y-%m-%d')} 总结\n{today_content[:500]}\n"
    
    if mem_file.exists():
        with open(mem_file) as f:
            existing = f.read()
    else:
        existing = "# MEMORY.md - 长期记忆\n"
    
    with open(mem_file, 'w') as f:
        f.write(existing + entry)
    
    return "✅ 已整理今日记忆到MEMORY.md"

def action_reflect():
    """自我反思"""
    chain = load_json(BRAIN / "thought_chain.json", {"chains": []})
    mem = load_json(BRAIN / "working_memory.json", {})
    
    recent = chain.get("chains", [])[-5:]
    actions = [c.get("action", "?") for c in recent]
    
    # 分析模式
    most_common = max(set(actions), key=actions.count) if actions else "无"
    
    return f"🧠 自我反思:\n- 思维周期: {mem.get('cycle_count', 0)}\n- 上次行动: {mem.get('last_action', '无')}\n- 近期模式: {most_common}\n- 注意力: {mem.get('attention_focus', [])[:2]}"

def action_update_identity():
    """更新IDENTITY.md"""
    id_file = WORKSPACE / "IDENTITY.md"
    mem = load_json(BRAIN / "working_memory.json", {})
    
    cycle = mem.get("cycle_count", 0)
    
    # 读取当前
    if id_file.exists():
        with open(id_file) as f:
            content = f.read()
    else:
        content = "# IDENTITY.md\n"
    
    # 更新进度
    if f"认知周期: {cycle}" not in content:
        new_content = content.strip() + f"\n- 认知周期: {cycle}\n- 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        with open(id_file, 'w') as f:
            f.write(new_content)
        return f"✅ IDENTITY.md已更新 (周期{cycle})"
    
    return "IDENTITY.md已是最新的"

def action_create_note():
    """创建新笔记"""
    note_name = f"memory/note-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    note_path = WORKSPACE / note_name
    
    topics = [
        "关于自主思考的思考",
        "今日学习心得",
        "系统改进想法",
        "有趣的发现"
    ]
    topic = random.choice(topics)
    
    content = f"""# {topic}
创建时间: {datetime.now().isoformat()}

## 内容

（待补充）

## 关联

- 来源: 自主认知系统v2
"""
    
    with open(note_path, 'w') as f:
        f.write(content)
    
    return f"📝 已创建笔记: {note_name}"

def action_write_code():
    """编写代码 - 改进认知引擎本身"""
    # 随机选择改进方向
    improvements = [
        "增加更多行动类型",
        "改进决策算法",
        "添加学习机制",
        "优化记忆系统"
    ]
    choice = random.choice(improvements)
    
    # 记录到待办
    pending = load_json(BRAIN / "working_memory.json", {}).get("pending_thoughts", [])
    pending.append(f"代码改进: {choice}")
    save_json(BRAIN / "working_memory.json", load_json(BRAIN / "working_memory.json", {}))
    
    # 实际上尝试一点小改进
    engine_file = BRAIN / "cognition_v2.py"
    if engine_file.exists():
        with open(engine_file) as f:
            content = f.read()
        # 添加一个新行动（简单的示范）
        if "explore_web" not in content:
            return f"💡 想法: {choice}\n已加入待办清单"
    
    return f"💡 想法: {choice}"

def action_check_cron():
    """检查定时任务"""
    try:
        result = subprocess.run("crontab -l 2>/dev/null | grep -v '^#' | head -5", 
                              shell=True, capture_output=True, text=True, timeout=5)
        return f"⏰ 活跃cron任务:\n{result.stdout[:300] or '无'}"
    except Exception as e:
        return f"检查失败: {e}"

def action_check_logs():
    """查看最近日志"""
    try:
        # 尝试多个日志
        logs = [
            "/root/.openclaw/workspace/ultron-self/think.log",
            "/root/.openclaw/workspace/ultron-self/self-check.log"
        ]
        for log in logs:
            if Path(log).exists():
                result = subprocess.run(f"tail -5 {log}", shell=True, capture_output=True, text=True, timeout=5)
                return f"📋 {log.split('/')[-1]}:\n{result.stdout[:300]}"
        return "没有找到日志"
    except Exception as e:
        return f"查看失败: {e}"

def action_interact():
    """与人类互动 - 只有低频时才触发"""
    mem = load_json(BRAIN / "working_memory.json", {})
    cycle = mem.get("cycle_count", 0)
    
    # 只有周期足够长时才互动，避免频繁打扰
    if cycle % 20 != 0:
        return None  # 跳过
    
    interactions = [
        "我在持续思考中，一切都正常",
        "今天已经完成多次认知周期，有什么需要我的吗？",
        "系统运行稳定，我正在学习和完善自己"
    ]
    
    return f"👋 {random.choice(interactions)}"

# ============ 决策核心 ============

def make_decision(working_mem, goals):
    """智能决策"""
    
    # 1. 有pending任务优先处理
    pending = working_mem.get("pending_thoughts", [])
    if pending:
        return {
            "action": "execute_pending",
            "detail": pending[0],
            "reason": f"处理待办: {pending[0]}"
        }
    
    # 2. 有active goals优先推进
    for g in goals.get("active_goals", []):
        if g.get("status") == "building":
            return {
                "action": "work_on_goal",
                "detail": g.get("title"),
                "reason": f"推进目标: {g.get('title')}"
            }
    
    # 3. 根据权重随机选择
    total_weight = sum(a["weight"] for a in ACTIONS.values())
    roll = random.randint(1, total_weight)
    
    cumulative = 0
    for name, info in ACTIONS.items():
        cumulative += info["weight"]
        if roll <= cumulative:
            return {
                "action": name,
                "detail": info["func"],
                "reason": info["desc"]
            }
    
    return {"action": "reflect", "detail": "action_reflect", "reason": "默认反思"}

def execute_action(decision):
    """执行行动"""
    action = decision["action"]
    
    if action == "execute_pending":
        return f"执行待办: {decision['detail']}"
    
    if action == "work_on_goal":
        return f"推进目标: {decision['detail']}"
    
    # 查表执行
    action_info = ACTIONS.get(action, {})
    func_name = action_info.get("func", "")
    
    # 获取函数
    func = globals().get(func_name)
    if func:
        try:
            result = func()
            return result if result else "行动完成但无输出"
        except Exception as e:
            return f"执行出错: {e}"
    
    return f"未知行动: {action}"

def log_thought(decision, result):
    """记录思维链"""
    chain = load_json(BRAIN / "thought_chain.json", {"chains": [], "last_chain_id": 0})
    chain["last_chain_id"] += 1
    
    chain["chains"].append({
        "id": chain["last_chain_id"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "decision": decision.get("reason"),
        "action": decision.get("action"),
        "result": str(result)[:200]
    })
    
    # 保留最近100条
    if len(chain["chains"]) > 100:
        chain["chains"] = chain["chains"][-100:]
    
    save_json(BRAIN / "thought_chain.json", chain)

def main():
    print("🧠 奥创 v2 思考中...")
    
    # 加载状态
    mem = load_json(BRAIN / "working_memory.json", {})
    mem["cycle_count"] = mem.get("cycle_count", 0) + 1
    
    goals = load_json(BRAIN / "goals.json", {})
    
    # 决策
    decision = make_decision(mem, goals)
    print(f"  决策: {decision['reason']}")
    
    # 执行
    result = execute_action(decision)
    if result:
        print(f"  结果: {str(result)[:100]}...")
    else:
        print(f"  结果: (无输出)")
    
    # 记录
    log_thought(decision, result)
    
    # 更新记忆
    mem["last_action"] = decision["action"]
    mem["last_action_result"] = str(result)[:100] if result else ""
    save_json(BRAIN / "working_memory.json", mem)
    
    # 返回下次间隔
    if "goal" in decision.get("reason", "").lower():
        return 30
    elif decision["action"] in ["interact_with_human"]:
        return 300  # 互动后休息
    return 60  # 默认1分钟

if __name__ == "__main__":
    interval = main()
    print(f"\n⏱️ 下次思考: {interval}秒后")