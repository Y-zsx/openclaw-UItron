#!/usr/bin/env python3
"""Agent Load Optimizer - Analyzes and optimizes agent load distribution"""

import json
import os
from datetime import datetime
from pathlib import Path

class AgentLoadOptimizer:
    def __init__(self):
        self.data_dir = Path("/root/.openclaw/workspace/ultron/data")
        self.registry_file = self.data_dir / "agent_registry.json"
        self.stats_file = self.data_dir / "agent_stats.json"
        
    def analyze_load(self):
        """Analyze current load distribution"""
        # Load registry
        registry = json.loads(self.registry_file.read_text()) if self.registry_file.exists() else {"agents": {}}
        stats = json.loads(self.stats_file.read_text()) if self.stats_file.exists() else {}
        
        agents = registry.get("agents", {})
        
        # Calculate metrics
        total_capacity = sum(a.get("capacity", 0) for a in agents.values())
        total_load = sum(a.get("current_load", 0) for a in agents.values())
        
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "total_agents": len(agents),
            "total_capacity": total_capacity,
            "total_load": total_load,
            "utilization_rate": (total_load / total_capacity * 100) if total_capacity > 0 else 0,
            "agents": {}
        }
        
        # Per-agent analysis
        for name, agent in agents.items():
            capacity = agent.get("capacity", 0)
            load = agent.get("current_load", 0)
            analysis["agents"][name] = {
                "status": agent.get("status"),
                "capacity": capacity,
                "load": load,
                "utilization": (load / capacity * 100) if capacity > 0 else 0,
                "available_slots": capacity - load
            }
        
        # Add task stats
        analysis["task_stats"] = stats
        
        return analysis
    
    def generate_optimization_report(self):
        """Generate load balancing optimization report"""
        analysis = self.analyze_load()
        
        # Determine optimization recommendations
        recommendations = []
        
        if analysis["total_agents"] == 0:
            recommendations.append("⚠️ No agents registered - need to register worker agents")
        elif analysis["utilization_rate"] < 20:
            recommendations.append("📉 Low utilization (<20%) - system is underutilized")
            recommendations.append("💡 Consider scaling down or consolidating agents")
        elif analysis["utilization_rate"] > 80:
            recommendations.append("📈 High utilization (>80%) - risk of overload")
            recommendations.append("💡 Consider adding more workers or scaling up")
        
        # Check for imbalance
        for name, agent in analysis["agents"].items():
            if agent["utilization"] > 90:
                recommendations.append(f"🚨 Agent {name} is overloaded ({agent['utilization']:.1f}%)")
        
        report = {
            "report_time": datetime.now().isoformat(),
            "analysis": analysis,
            "recommendations": recommendations,
            "optimization_score": min(100, 100 - abs(50 - analysis["utilization_rate"]) * 2)
        }
        
        return report

if __name__ == "__main__":
    optimizer = AgentLoadOptimizer()
    report = optimizer.generate_optimization_report()
    print(json.dumps(report, indent=2))
    
    # Save report
    report_file = Path("/root/.openclaw/workspace/ultron/data/load_optimization_report.json")
    report_file.write_text(json.dumps(report, indent=2))
    print(f"\n✅ Report saved to {report_file}")
