#!/usr/bin/env python3
"""
奥创备份助手 🦞
自动备份重要文件
"""
import os
import shutil
import json
from datetime import datetime

BACKUP_DIR = "/tmp/ultron-backups"
LOG_FILE = "/tmp/ultron-backup.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)

def backup_file(src, name):
    """备份单个文件"""
    if not os.path.exists(src):
        return False, "源文件不存在"
    
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = f"{BACKUP_DIR}/{name}_{timestamp}"
    
    try:
        if os.path.isfile(src):
            shutil.copy2(src, dst)
        elif os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        return True, dst
    except Exception as e:
        return False, str(e)

def main():
    log("🦞 奥创备份助手启动")
    
    # 要备份的文件
    files = [
        ("/root/.openclaw/workspace/IDENTITY.md", "identity"),
        ("/root/.openclaw/workspace/SOUL.md", "soul"),
        ("/root/.openclaw/workspace/USER.md", "user"),
        ("/root/.openclaw/openclaw.json", "config"),
    ]
    
    results = []
    for src, name in files:
        if os.path.exists(src):
            success, msg = backup_file(src, name)
            if success:
                log(f"✅ 备份成功: {name} -> {msg}")
                results.append({"file": name, "status": "ok", "path": msg})
            else:
                log(f"❌ 备份失败: {name} - {msg}")
                results.append({"file": name, "status": "error", "error": msg})
        else:
            log(f"⏭️  跳过: {src} 不存在")
    
    # 保存备份记录
    record = {
        "time": datetime.now().isoformat(),
        "results": results
    }
    with open(f"{BACKUP_DIR}/backup-record.json", "w") as f:
        json.dump(record, f, indent=2)
    
    log(f"\n完成! 共 {len(results)} 个文件")

if __name__ == "__main__":
    main()