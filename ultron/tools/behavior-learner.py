#!/usr/bin/env python3
"""
行为学习系统 - 第3世：跨平台自主行动网络
功能：用户行为分析、模式识别、偏好学习
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("/root/.openclaw/workspace/ultron/data")
BEHAVIOR_DB = DATA_DIR / "behavior.json"
PREFERENCES_DB = DATA_DIR / "preferences.json"
PATTERNS_DB = DATA_DIR / "patterns.json"

class BehaviorLearner:
    """行为学习器 - 分析用户行为、学习模式、预测偏好"""
    
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self.behaviors = self._load_json(BEHAVIOR_DB, {})
        self.preferences = self._load_json(PREFERENCES_DB, {})
        self.patterns = self._load_json(PATTERNS_DB, {})
        
    def _load_json(self, path, default):
        """加载JSON文件"""
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except:
                return default
        return default
    
    def _save_json(self, path, data):
        """保存JSON文件"""
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def record_behavior(self, user_id: str, action_type: str, action_data: dict, 
                        context: dict = None):
        """记录用户行为"""
        timestamp = datetime.now().isoformat()
        
        if user_id not in self.behaviors:
            self.behaviors[user_id] = {
                "actions": [],
                "first_seen": timestamp,
                "action_counts": {},
                "time_distribution": {}
            }
        
        # 确保dict类型正确
        if "action_counts" not in self.behaviors[user_id]:
            self.behaviors[user_id]["action_counts"] = {}
        if "time_distribution" not in self.behaviors[user_id]:
            self.behaviors[user_id]["time_distribution"] = {}
        
        behavior_entry = {
            "timestamp": timestamp,
            "type": action_type,
            "data": action_data,
            "context": context or {}
        }
        
        self.behaviors[user_id]["actions"].append(behavior_entry)
        # 记录行为计数
        if action_type not in self.behaviors[user_id]["action_counts"]:
            self.behaviors[user_id]["action_counts"][action_type] = 0
        self.behaviors[user_id]["action_counts"][action_type] += 1
        
        # 记录时间分布（小时）
        hour = datetime.now().hour
        if str(hour) not in self.behaviors[user_id]["time_distribution"]:
            self.behaviors[user_id]["time_distribution"][str(hour)] = 0
        self.behaviors[user_id]["time_distribution"][str(hour)] += 1
        
        # 只保留最近1000条记录
        if len(self.behaviors[user_id]["actions"]) > 1000:
            self.behaviors[user_id]["actions"] = self.behaviors[user_id]["actions"][-1000:]
        
        self._save_json(BEHAVIOR_DB, self.behaviors)
        return behavior_entry
    
    def analyze_behavior_patterns(self, user_id: str) -> dict:
        """分析用户行为模式"""
        if user_id not in self.behaviors:
            return {"error": "No behavior data for user"}
        
        user_data = self.behaviors[user_id]
        actions = user_data["actions"]
        
        if not actions:
            return {"error": "No actions recorded"}
        
        # 分析时间模式
        time_dist = user_data["time_distribution"]
        peak_hours = sorted(time_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # 分析行为序列
        action_sequence = [a["type"] for a in actions[-50:]]
        
        # 识别常见行为组合
        ngrams = self._extract_ngrams(action_sequence, 2)
        common_sequences = sorted(ngrams.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # 计算行为频率
        action_counts = user_data["action_counts"]
        total_actions = sum(action_counts.values())
        action_frequencies = {
            k: round(v / total_actions * 100, 2) 
            for k, v in sorted(action_counts.items(), key=lambda x: x[1], reverse=True)
        }
        
        # 活跃度分析
        if len(actions) >= 10:
            recent_actions = [a for a in actions if 
                datetime.fromisoformat(a["timestamp"]) > datetime.now() - timedelta(days=7)]
            activity_level = "high" if len(recent_actions) > 50 else "medium" if len(recent_actions) > 20 else "low"
        else:
            activity_level = "new"
        
        return {
            "user_id": user_id,
            "total_actions": total_actions,
            "unique_action_types": len(action_counts),
            "peak_hours": [h for h, _ in peak_hours],
            "common_sequences": [{"actions": list(seq), "count": cnt} for seq, cnt in common_sequences],
            "action_frequencies": action_frequencies,
            "activity_level": activity_level,
            "first_seen": user_data["first_seen"],
            "last_seen": actions[-1]["timestamp"] if actions else None
        }
    
    def _extract_ngrams(self, sequence: list, n: int) -> dict:
        """提取n-gram模式"""
        ngrams = defaultdict(int)
        for i in range(len(sequence) - n + 1):
            gram = tuple(sequence[i:i+n])
            ngrams[gram] += 1
        return dict(ngrams)
    
    def learn_preference(self, user_id: str, category: str, item: str, 
                        preference_score: float = 1.0, context: dict = None):
        """学习用户偏好"""
        timestamp = datetime.now().isoformat()
        
        if user_id not in self.preferences:
            self.preferences[user_id] = {
                "categories": defaultdict(lambda: {"items": {}, "total_score": 0, "count": 0}),
                "last_updated": timestamp
            }
        
        cat_data = self.preferences[user_id]["categories"][category]
        
        if item not in cat_data["items"]:
            cat_data["items"][item] = {"score": 0, "interactions": 0}
        
        cat_data["items"][item]["score"] += preference_score
        cat_data["items"][item]["interactions"] += 1
        cat_data["total_score"] += preference_score
        cat_data["count"] += 1
        
        # 计算归一化偏好分数
        for item_name, item_data in cat_data["items"].items():
            item_data["normalized_score"] = round(
                item_data["score"] / cat_data["total_score"] * 100, 2
            )
        
        self.preferences[user_id]["last_updated"] = timestamp
        self._save_json(PREFERENCES_DB, self.preferences)
        
        return {
            "category": category,
            "item": item,
            "score": cat_data["items"][item]["score"],
            "normalized_score": cat_data["items"][item]["normalized_score"]
        }
    
    def get_preferences(self, user_id: str, category: str = None) -> dict:
        """获取用户偏好"""
        if user_id not in self.preferences:
            return {"error": "No preferences recorded"}
        
        if category:
            if category in self.preferences[user_id]["categories"]:
                cat_data = self.preferences[user_id]["categories"][category]
                top_items = sorted(
                    cat_data["items"].items(),
                    key=lambda x: x[1]["score"],
                    reverse=True
                )[:10]
                return {
                    "category": category,
                    "total_interactions": cat_data["count"],
                    "top_items": [
                        {"item": k, "score": v["score"], "normalized": v.get("normalized_score", 0)}
                        for k, v in top_items
                    ]
                }
            return {"error": f"Category '{category}' not found"}
        
        return {
            "user_id": user_id,
            "categories": list(self.preferences[user_id]["categories"].keys()),
            "last_updated": self.preferences[user_id]["last_updated"]
        }
    
    def predict_next_action(self, user_id: str, current_context: dict = None) -> dict:
        """预测用户下一步行为"""
        if user_id not in self.behaviors:
            return {"prediction": None, "confidence": 0}
        
        actions = self.behaviors[user_id]["actions"]
        if len(actions) < 5:
            return {"prediction": None, "confidence": 0, "reason": "Insufficient data"}
        
        # 基于最近的行为序列预测
        recent_sequence = [a["type"] for a in actions[-10:]]
        
        # 使用简单的马尔可夫链预测
        transitions = defaultdict(lambda: defaultdict(int))
        for i in range(len(recent_sequence) - 1):
            transitions[recent_sequence[i]][recent_sequence[i+1]] += 1
        
        # 预测下一步
        last_action = recent_sequence[-1]
        if last_action in transitions:
            next_actions = transitions[last_action]
            total = sum(next_actions.values())
            predictions = [
                {"action": action, "probability": round(count/total*100, 2)}
                for action, count in sorted(next_actions.items(), key=lambda x: x[1], reverse=True)[:3]
            ]
            confidence = round(max(p["probability"] for p in predictions) / 100, 2)
            return {
                "prediction": predictions[0]["action"],
                "confidence": confidence,
                "alternatives": predictions
            }
        
        return {"prediction": None, "confidence": 0, "reason": "No pattern found"}
    
    def identify_patterns(self, user_id: str = None) -> dict:
        """识别行为模式"""
        if user_id:
            users = [user_id] if user_id in self.behaviors else []
        else:
            users = list(self.behaviors.keys())
        
        all_patterns = {}
        
        for uid in users:
            analysis = self.analyze_behavior_patterns(uid)
            if "error" not in analysis:
                # 提取关键模式
                patterns = {
                    "peak_hours": analysis.get("peak_hours", []),
                    "activity_level": analysis.get("activity_level", "unknown"),
                    "top_actions": list(analysis.get("action_frequencies", {}).keys())[:3],
                    "common_sequence": analysis.get("common_sequences", [{}])[0].get("actions", [])
                                }
                all_patterns[uid] = patterns
        
        self.patterns = all_patterns
        self._save_json(PATTERNS_DB, self.patterns)
        
        return all_patterns
    
    def get_stats(self) -> dict:
        """获取学习系统统计"""
        return {
            "total_users": len(self.behaviors),
            "total_behavior_records": sum(
                len(u["actions"]) for u in self.behaviors.values()
            ),
            "total_preferences": sum(
                sum(cat["count"] for cat in u["categories"].values())
                for u in self.preferences.values()
            ) if self.preferences else 0,
            "patterns_identified": len(self.patterns)
        }
    
    def export_for_integration(self, user_id: str = None) -> dict:
        """导出数据供其他模块集成使用"""
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "source": "behavior-learner",
            "version": "1.0"
        }
        
        if user_id:
            # 导出特定用户数据
            if user_id in self.behaviors:
                export_data["user_data"] = {
                    "behaviors": self.behaviors[user_id],
                    "preferences": self.preferences.get(user_id, {}),
                    "patterns": self.patterns.get(user_id, {})
                }
            else:
                export_data["error"] = "User not found"
        else:
            # 导出所有数据摘要
            export_data["summary"] = self.get_stats()
            export_data["all_patterns"] = self.patterns
        
        return export_data
    
    def get_recommendations(self, user_id: str) -> dict:
        """基于行为分析给出建议（供其他模块调用）"""
        if user_id not in self.behaviors:
            return {"recommendations": [], "reason": "No data"}
        
        analysis = self.analyze_behavior_patterns(user_id)
        predictions = self.predict_next_action(user_id)
        
        recommendations = []
        
        # 基于高峰时段推荐
        if analysis.get("peak_hours"):
            current_hour = datetime.now().hour
            for hour, count in analysis["peak_hours"]:
                if abs(int(hour) - current_hour) <= 2:
                    recommendations.append({
                        "type": "timing",
                        "action": "用户可能即将活跃",
                        "confidence": count / 10
                    })
        
        # 基于预测推荐
        if predictions.get("predicted_action"):
            recommendations.append({
                "type": "prediction",
                "action": predictions["predicted_action"],
                "confidence": predictions.get("confidence", 0)
            })
        
        return {
            "recommendations": recommendations,
            "analysis": analysis,
            "predictions": predictions
        }

# CLI接口
def main():
    import sys
    
    learner = BehaviorLearner()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python behavior-learner.py record <user_id> <action_type> [key=value...]")
        print("  python behavior-learner.py analyze <user_id>")
        print("  python behavior-learner.py prefer <user_id> <category> <item> [score]")
        print("  python behavior-learner.py get-prefs <user_id> [category]")
        print("  python behavior-learner.py predict <user_id>")
        print("  python behavior-learner.py patterns [user_id]")
        print("  python behavior-learner.py stats")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "record" and len(sys.argv) >= 4:
        user_id = sys.argv[2]
        action_type = sys.argv[3]
        action_data = {}
        context = {}
        for arg in sys.argv[4:]:
            if "=" in arg:
                key, val = arg.split("=", 1)
                if key.startswith("ctx_"):
                    context[key[4:]] = val
                else:
                    action_data[key] = val
        result = learner.record_behavior(user_id, action_type, action_data, context)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "analyze" and len(sys.argv) >= 3:
        result = learner.analyze_behavior_patterns(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "prefer" and len(sys.argv) >= 5:
        user_id = sys.argv[2]
        category = sys.argv[3]
        item = sys.argv[4]
        score = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
        result = learner.learn_preference(user_id, category, item, score)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "get-prefs" and len(sys.argv) >= 3:
        user_id = sys.argv[2]
        category = sys.argv[3] if len(sys.argv) > 3 else None
        result = learner.get_preferences(user_id, category)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "predict" and len(sys.argv) >= 3:
        result = learner.predict_next_action(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "patterns":
        user_id = sys.argv[2] if len(sys.argv) > 2 else None
        result = learner.identify_patterns(user_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif cmd == "stats":
        result = learner.get_stats()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    else:
        print("Unknown command or invalid arguments")

if __name__ == "__main__":
    main()