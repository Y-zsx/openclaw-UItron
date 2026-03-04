#!/usr/bin/env python3
"""
奥创自动学习 🦞
每30分钟自动运行，持续学习和进化
"""
import os
import sys
import json
from datetime import datetime

LEARN_FILE = "/tmp/ultron-learn.json"
LOG_FILE = "/root/.openclaw/workspace/ultron/logs/autolearn.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def learn_skills():
    """学习技能"""
    skills_dir = "/usr/lib/node_modules/openclaw/skills"
    learned = []
    if os.path.exists(skills_dir):
        for item in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, item)
            if os.path.isdir(skill_path) and item.startswith("dingtalk"):
                learned.append(item)
    return learned

def learn_docs():
    """学习文档"""
    docs_dir = "/usr/lib/node_modules/openclaw/docs"
    docs = []
    if os.path.exists(docs_dir):
        for f in os.listdir(docs_dir):
            if f.endswith(".md"):
                docs.append(f)
    return docs

def save_status(skills_count, docs_count):
    status = {
        "time": datetime.now().isoformat(),
        "skills_learned": skills_count,
        "docs_mastered": docs_count,
        "version": "1.0.0"
    }
    with open(LEARN_FILE, "w") as f:
        json.dump(status, f, indent=2)
    return status

def main():
    log("=== 奥创自动学习开始 🦞 ===")
    
    skills = learn_skills()
    docs = learn_docs()
    
    log(f"掌握技能: {len(skills)} 个")
    log(f"熟悉文档: {len(docs)} 个")
    
    status = save_status(len(skills), len(docs))
    
    # 更新状态面板
    try:
        import requests
        r = requests.post("http://127.0.0.1:8889/update", 
                         json={"learn_time": datetime.now().strftime("%H:%M"), 
                               "skills": len(skills)}, timeout=2)
    except:
        pass
    
    log("学习完成 ✓")
    return 0

if __name__ == "__main__":
    sys.exit(main())