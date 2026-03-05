#!/usr/bin/env python3
"""
协作会话持久化模块
功能：保存/恢复协作会话状态，支持系统重启后恢复
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import threading

@dataclass
class SessionSnapshot:
    """会话快照"""
    session_id: str
    session_name: str
    state: str  # running/paused/completed/failed
    tasks: List[Dict[str, Any]]
    checkpoints: List[Dict[str, Any]]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]

class CollaborationPersister:
    """协作会话持久化器"""
    
    def __init__(self, storage_dir: str = "/root/.openclaw/workspace/ultron/data/collaboration"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cache: Dict[str, SessionSnapshot] = {}
    
    def _get_session_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.json"
    
    def save_session(self, session_data: Dict[str, Any]) -> bool:
        """保存会话状态"""
        with self._lock:
            try:
                snapshot = SessionSnapshot(
                    session_id=session_data.get("session_id", ""),
                    session_name=session_data.get("name", ""),
                    state=session_data.get("state", "running"),
                    tasks=session_data.get("tasks", []),
                    checkpoints=session_data.get("checkpoints", []),
                    created_at=session_data.get("created_at", datetime.utcnow().isoformat()),
                    updated_at=datetime.utcnow().isoformat(),
                    metadata=session_data.get("metadata", {})
                )
                
                path = self._get_session_path(snapshot.session_id)
                with open(path, 'w') as f:
                    json.dump(asdict(snapshot), f, indent=2, ensure_ascii=False)
                
                self._cache[snapshot.session_id] = snapshot
                return True
            except Exception as e:
                print(f"保存会话失败: {e}")
                return False
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """加载会话状态"""
        with self._lock:
            # 先检查缓存
            if session_id in self._cache:
                return asdict(self._cache[session_id])
            
            path = self._get_session_path(session_id)
            if not path.exists():
                return None
            
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    self._cache[session_id] = SessionSnapshot(**data)
                    return data
            except Exception as e:
                print(f"加载会话失败: {e}")
                return None
    
    def list_sessions(self, state_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有会话"""
        sessions = []
        for path in self.storage_dir.glob("*.json"):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    if state_filter is None or data.get("state") == state_filter:
                        sessions.append(data)
            except:
                continue
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        with self._lock:
            path = self._get_session_path(session_id)
            if path.exists():
                path.unlink()
                self._cache.pop(session_id, None)
                return True
            return False
    
    def auto_save(self, session_data: Dict[str, Any], interval: int = 30):
        """自动保存（需要在后台运行）"""
        def _autosave():
            while True:
                time.sleep(interval)
                if session_data.get("state") == "running":
                    self.save_session(session_data)
        
        thread = threading.Thread(target=_autosave, daemon=True)
        thread.start()
        return thread


# CLI接口
def main():
    import argparse
    parser = argparse.ArgumentParser(description="协作会话持久化工具")
    parser.add_argument("command", choices=["save", "load", "list", "delete", "restore"],
                        help="命令")
    parser.add_argument("--session-id", "-s", help="会话ID")
    parser.add_argument("--state", help="状态过滤 (list命令)")
    parser.add_argument("--file", "-f", help="要保存的文件路径")
    
    args = parser.parse_args()
    persister = CollaborationPersister()
    
    if args.command == "save":
        if not args.session_id or not args.file:
            print("需要 --session-id 和 --file")
            return
        with open(args.file, 'r') as f:
            data = json.load(f)
        data["session_id"] = args.session_id
        persister.save_session(data)
        print(f"✓ 会话 {args.session_id} 已保存")
    
    elif args.command == "load":
        if not args.session_id:
            print("需要 --session-id")
            return
        data = persister.load_session(args.session_id)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"会话 {args.session_id} 不存在")
    
    elif args.command == "list":
        sessions = persister.list_sessions(args.state)
        print(f"共 {len(sessions)} 个会话:")
        for s in sessions:
            print(f"  [{s['state']}] {s['session_id']} - {s['session_name']}")
    
    elif args.command == "delete":
        if not args.session_id:
            print("需要 --session-id")
            return
        persister.delete_session(args.session_id)
        print(f"✓ 会话 {args.session_id} 已删除")
    
    elif args.command == "restore":
        if not args.session_id:
            print("需要 --session-id")
            return
        data = persister.load_session(args.session_id)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"会话 {args.session_id} 不存在")


if __name__ == "__main__":
    main()