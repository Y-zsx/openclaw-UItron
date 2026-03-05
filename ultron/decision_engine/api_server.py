#!/usr/bin/env python3
"""
决策引擎API服务器
Decision Engine API Server
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
import logging
from core import DecisionEngine, DecisionContext
from rules import RuleEngine
from executor import ActionExecutor
from feedback import FeedbackLoop

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)

# 初始化组件
decision_engine = DecisionEngine()
rule_engine = RuleEngine()
action_executor = ActionExecutor()
feedback_loop = FeedbackLoop()

# 关联规则引擎到决策引擎
for rule in rule_engine.get_rules():
    decision_engine.register_rule(rule)

# 关联反馈到决策引擎
feedback_loop.on_improvement = lambda data: logger.info(f"改进建议: {data}")

logger.info("决策引擎API服务器初始化完成")


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "decision-engine",
        "version": "1.0.0"
    })


@app.route('/decide', methods=['POST'])
def decide():
    """发起决策请求"""
    data = request.json
    
    trigger = data.get('trigger', 'manual')
    source = data.get('source', 'api')
    context_data = data.get('context', {})
    
    # 创建决策上下文
    context = DecisionContext(
        trigger=trigger,
        data=context_data,
        source=source
    )
    
    # 处理决策
    decision = decision_engine.process(context, auto_approve=True)
    
    if decision:
        # 学习
        feedback_loop.learn(
            context_data,
            decision.action,
            decision.status.value == "completed"
        )
        
        return jsonify({
            "success": True,
            "decision": decision.to_dict()
        })
    else:
        return jsonify({
            "success": False,
            "message": "无匹配决策"
        })


@app.route('/evaluate', methods=['POST'])
def evaluate():
    """评估决策上下文"""
    data = request.json
    
    context = DecisionContext(
        trigger=data.get('trigger', 'manual'),
        data=data.get('context', {}),
        source=data.get('source', 'api')
    )
    
    decisions = decision_engine.evaluate(context)
    
    return jsonify({
        "context": context.to_dict(),
        "decisions": [d.to_dict() for d in decisions]
    })


@app.route('/rules', methods=['GET', 'POST'])
def rules():
    """规则管理"""
    if request.method == 'GET':
        tag = request.args.get('tag')
        rules = rule_engine.get_rules(tag=tag, enabled_only=False)
        return jsonify({
            "rules": [r.to_dict() for r in rules],
            "stats": rule_engine.get_stats()
        })
    else:
        # 添加规则
        data = request.json
        # 简化: 返回成功
        return jsonify({"success": True, "message": "规则添加功能简化"})


@app.route('/actions', methods=['GET'])
def actions():
    """获取可用动作"""
    return jsonify({
        "actions": action_executor.get_actions(),
        "stats": action_executor.get_stats()
    })


@app.route('/execute', methods=['POST'])
def execute():
    """直接执行动作"""
    data = request.json
    action_name = data.get('action')
    context = data.get('context', {})
    
    result = action_executor.execute(action_name, context)
    
    return jsonify(result.to_dict())


@app.route('/feedback', methods=['POST', 'GET'])
def feedback():
    """反馈管理"""
    if request.method == 'POST':
        data = request.json
        feedback = feedback_loop.collect(
            decision_id=data.get('decision_id'),
            action_id=data.get('action_id'),
            expected=data.get('expected'),
            actual=data.get('actual'),
            metadata=data.get('metadata', {})
        )
        return jsonify(feedback.to_dict())
    else:
        limit = int(request.args.get('limit', 100))
        return jsonify({
            "history": feedback_loop.get_history(limit),
            "stats": feedback_loop.get_stats()
        })


@app.route('/learn', methods=['GET'])
def learn():
    """学习状态"""
    return jsonify(feedback_loop.export_learnings())


@app.route('/recommend', methods=['POST'])
def recommend():
    """获取优化建议"""
    data = request.json
    recommendations = feedback_loop.get_recommendations(data.get('context', {}))
    return jsonify({"recommendations": recommendations})


@app.route('/risk', methods=['POST'])
def risk_assessment():
    """风险评估接口"""
    data = request.json
    
    metrics = data.get('metrics', {})
    thresholds = data.get('thresholds', {
        'cpu': 80,
        'memory': 85,
        'disk': 90,
        'error_rate': 5
    })
    
    risks = []
    risk_level = 0
    
    # CPU风险评估
    cpu = metrics.get('cpu', 0)
    if cpu > thresholds.get('cpu', 80):
        severity = min(100, (cpu - thresholds['cpu']) * 5)
        risks.append({
            "type": "cpu",
            "level": "high" if cpu > 90 else "medium",
            "value": cpu,
            "threshold": thresholds.get('cpu'),
            "severity": severity
        })
        risk_level += severity * 0.3
    
    # 内存风险评估
    memory = metrics.get('memory', 0)
    if memory > thresholds.get('memory', 85):
        severity = min(100, (memory - thresholds['memory']) * 5)
        risks.append({
            "type": "memory",
            "level": "high" if memory > 95 else "medium",
            "value": memory,
            "threshold": thresholds.get('memory'),
            "severity": severity
        })
        risk_level += severity * 0.25
    
    # 磁盘风险评估
    disk = metrics.get('disk', 0)
    if disk > thresholds.get('disk', 90):
        severity = min(100, (disk - thresholds['disk']) * 10)
        risks.append({
            "type": "disk",
            "level": "high",
            "value": disk,
            "threshold": thresholds.get('disk'),
            "severity": severity
        })
        risk_level += severity * 0.2
    
    # 错误率风险
    error_rate = metrics.get('error_rate', 0)
    if error_rate > thresholds.get('error_rate', 5):
        severity = min(100, error_rate * 10)
        risks.append({
            "type": "error_rate",
            "level": "high" if error_rate > 10 else "medium",
            "value": error_rate,
            "threshold": thresholds.get('error_rate'),
            "severity": severity
        })
        risk_level += severity * 0.25
    
    # 总体风险等级
    overall_level = "low"
    if risk_level > 70:
        overall_level = "critical"
    elif risk_level > 50:
        overall_level = "high"
    elif risk_level > 25:
        overall_level = "medium"
    
    return jsonify({
        "success": True,
        "risk_assessment": {
            "overall_level": overall_level,
            "risk_score": min(100, int(risk_level)),
            "risks": risks,
            "thresholds": thresholds,
            "metrics": metrics
        }
    })


@app.route('/stats', methods=['GET'])
def stats():
    """系统统计"""
    return jsonify({
        "decision_engine": decision_engine.get_stats(),
        "rule_engine": rule_engine.get_stats(),
        "action_executor": action_executor.get_stats(),
        "feedback_loop": feedback_loop.get_stats()
    })


# 导入工作流集成模块
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from workflow_integration import workflow_integration
    WORKFLOW_AVAILABLE = True
except ImportError:
    WORKFLOW_AVAILABLE = False
    workflow_integration = None
    logger.warning("工作流集成模块不可用")


@app.route('/workflow/trigger', methods=['POST'])
def trigger_workflow():
    """触发工作流接口 - 决策引擎联动"""
    if not WORKFLOW_AVAILABLE:
        return jsonify({"success": False, "error": "工作流集成不可用"}), 500
    
    data = request.json
    workflow_id = data.get('workflow_id')
    context = data.get('context', {})
    
    if not workflow_id:
        return jsonify({"success": False, "error": "缺少workflow_id"}), 400
    
    # 添加决策上下文到工作流
    context['_decision_source'] = 'decision-engine'
    context['_trigger'] = data.get('trigger', 'api')
    
    result = workflow_integration.trigger_workflow(workflow_id, context)
    
    if result:
        return jsonify({
            "success": True,
            "workflow_id": workflow_id,
            "execution": result
        })
    else:
        return jsonify({
            "success": False,
            "error": "工作流触发失败"
        }), 500


@app.route('/workflow/list', methods=['GET'])
def list_workflows():
    """列出可用工作流"""
    if not WORKFLOW_AVAILABLE:
        return jsonify({"success": False, "error": "工作流集成不可用"}), 500
    
    workflows = workflow_integration.list_workflows()
    return jsonify({
        "success": True,
        "workflows": workflows,
        "count": len(workflows)
    })


@app.route('/decide-and-act', methods=['POST'])
def decide_and_act():
    """决策并执行工作流 - 一站式接口"""
    data = request.json
    trigger = data.get('trigger', 'auto')
    context_data = data.get('context', {})
    workflow_id = data.get('workflow_id')  # 可选：指定工作流
    
    # 创建决策上下文
    context = DecisionContext(
        trigger=trigger,
        data=context_data,
        source='decide-and-act'
    )
    
    # 处理决策
    decision = decision_engine.process(context, auto_approve=True)
    
    response = {
        "success": True,
        "decision": decision.to_dict() if decision else None,
        "workflow_triggered": False
    }
    
    # 如果决策成功且配置了工作流，则触发工作流
    if decision and workflow_id and WORKFLOW_AVAILABLE:
        # 将决策结果添加到上下文
        workflow_context = {
            **context_data,
            '_decision_action': decision.action,
            '_decision_status': decision.status.value,
            '_decision_id': getattr(decision, 'id', 'unknown')
        }
        
        result = workflow_integration.trigger_workflow(workflow_id, workflow_context)
        if result:
            response["workflow_triggered"] = True
            response["workflow_result"] = result
    
    # 学习
    if decision:
        feedback_loop.learn(
            context_data,
            decision.action,
            decision.status.value == "completed"
        )
    
    return jsonify(response)


if __name__ == '__main__':
    port = 18120
    logger.info(f"启动决策引擎API服务器: 端口 {port}")
    app.run(host='0.0.0.0', port=port, debug=False)