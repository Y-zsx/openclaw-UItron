"""
决策引擎API服务 - 主应用
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
import json
from datetime import datetime
import os

app = FastAPI(title="决策引擎API", version="1.0.0")

# 内存存储
decisions_db: Dict[str, Any] = {}
decision_history: List[Dict[str, Any]] = []

class DecisionRequest(BaseModel):
    """决策请求"""
    context: Dict[str, Any]
    options: List[str]
    criteria: Optional[Dict[str, float]] = None
    priority: Optional[int] = 1

class DecisionResponse(BaseModel):
    """决策响应"""
    decision_id: str
    selected: str
    confidence: float
    reasoning: str
    timestamp: str

class EvaluateRequest(BaseModel):
    """评估请求"""
    decision_id: str
    outcome: str
    score: float

@app.get("/")
def root():
    return {"service": "决策引擎API", "version": "1.0.0", "status": "running"}

@app.post("/decide", response_model=DecisionResponse)
def make_decision(req: DecisionRequest):
    """做出决策"""
    decision_id = f"dec_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 简单决策逻辑
    selected = req.options[0] if req.options else ""
    confidence = 0.85
    reasoning = "基于上下文分析，选择最优选项"
    
    if req.criteria:
        # 加权评分
        scores = {}
        for opt in req.options:
            score = 0.0
            for crit, weight in req.criteria.items():
                if crit in req.context:
                    score += weight * (1.0 if req.context[crit] == opt else 0.5)
            scores[opt] = score
        if scores:
            selected = max(scores, key=scores.get)
            confidence = scores[selected] / sum(scores.values()) if sum(scores.values()) > 0 else 0.5
    
    decision = {
        "decision_id": decision_id,
        "context": req.context,
        "options": req.options,
        "selected": selected,
        "confidence": confidence,
        "reasoning": reasoning,
        "priority": req.priority,
        "timestamp": datetime.now().isoformat()
    }
    
    decisions_db[decision_id] = decision
    decision_history.append(decision)
    
    return DecisionResponse(
        decision_id=decision_id,
        selected=selected,
        confidence=confidence,
        reasoning=reasoning,
        timestamp=decision["timestamp"]
    )

@app.get("/decision/{decision_id}")
def get_decision(decision_id: str):
    """获取决策详情"""
    if decision_id not in decisions_db:
        raise HTTPException(status_code=404, detail="决策不存在")
    return decisions_db[decision_id]

@app.get("/decisions")
def list_decisions(limit: int = 10):
    """列出最近决策"""
    return decision_history[-limit:][::-1]

@app.post("/evaluate")
def evaluate_decision(req: EvaluateRequest):
    """评估决策结果"""
    if req.decision_id not in decisions_db:
        raise HTTPException(status_code=404, detail="决策不存在")
    
    decisions_db[req.decision_id]["outcome"] = req.outcome
    decisions_db[req.decision_id]["score"] = req.score
    decisions_db[req.decision_id]["evaluated_at"] = datetime.now().isoformat()
    
    return {"status": "ok", "decision_id": req.decision_id, "score": req.score}

@app.get("/stats")
def get_stats():
    """获取统计信息"""
    total = len(decision_history)
    if total == 0:
        return {"total": 0, "avg_confidence": 0}
    
    avg_confidence = sum(d["confidence"] for d in decision_history) / total
    return {
        "total": total,
        "avg_confidence": round(avg_confidence, 3),
        "recent": len([d for d in decision_history if 
            (datetime.now() - datetime.fromisoformat(d["timestamp"])).total_seconds() < 3600])
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)