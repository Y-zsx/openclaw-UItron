#!/usr/bin/env python3
"""
告警引擎API服务器
Alert Engine API Server
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
import logging
from alert_integration import AlertRuleEngine, AlertRule, Alert, alert_engine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "alert-engine",
        "version": "1.0.0"
    })


@app.route('/check', methods=['POST'])
def check_alerts():
    """检查告警 - 传入指标数据，返回触发的告警"""
    data = request.json
    metrics = data.get('metrics', {})
    
    triggered = alert_engine.check_alerts(metrics)
    
    return jsonify({
        "success": True,
        "triggered_count": len(triggered),
        "alerts": [a.__dict__ for a in triggered]
    })


@app.route('/rules', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_rules():
    """告警规则管理"""
    if request.method == 'GET':
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        rules = alert_engine.get_rules(enabled_only)
        return jsonify({
            "rules": [vars(r) for r in rules],
            "stats": alert_engine.get_stats()
        })
    
    elif request.method == 'POST':
        # 添加规则
        data = request.json
        rule = AlertRule(
            id=data.get('id'),
            name=data.get('name'),
            condition=data.get('condition'),
            severity=data.get('severity', 'warning'),
            action=data.get('action', 'notify'),
            cooldown_seconds=data.get('cooldown_seconds', 300),
            metadata=data.get('metadata', {})
        )
        
        if alert_engine.add_rule(rule):
            return jsonify({"success": True, "rule_id": rule.id})
        else:
            return jsonify({"success": False, "error": "规则ID已存在"}), 400
    
    elif request.method == 'PUT':
        # 更新规则
        data = request.json
        rule_id = data.get('id')
        
        if alert_engine.update_rule(rule_id, **data):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "规则不存在"}), 404
    
    else:
        # DELETE
        rule_id = request.args.get('id')
        if alert_engine.delete_rule(rule_id):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "规则不存在"}), 404


@app.route('/rules/<rule_id>', methods=['GET'])
def get_rule(rule_id):
    """获取单个规则"""
    rule = alert_engine.get_rule(rule_id)
    if rule:
        return jsonify({"rule": vars(rule)})
    return jsonify({"error": "规则不存在"}), 404


@app.route('/alerts', methods=['GET'])
def get_alerts():
    """获取告警列表"""
    status = request.args.get('status')
    limit = int(request.args.get('limit', 100))
    
    alerts = alert_engine.get_alerts(status, limit)
    
    return jsonify({
        "alerts": [a.__dict__ for a in alerts],
        "count": len(alerts),
        "stats": alert_engine.get_stats()
    })


@app.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """确认告警"""
    data = request.json or {}
    acknowledged_by = data.get('acknowledged_by', 'api')
    
    if alert_engine.acknowledge_alert(alert_id, acknowledged_by):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "告警不存在"}), 404


@app.route('/alerts/<alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """解决告警"""
    if alert_engine.resolve_alert(alert_id):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "告警不存在"}), 404


@app.route('/stats', methods=['GET'])
def stats():
    """获取统计信息"""
    return jsonify(alert_engine.get_stats())


@app.route('/decide', methods=['POST'])
def alert_decide():
    """告警触发决策 - 自动根据告警做出决策"""
    data = request.json
    metrics = data.get('metrics', {})
    
    # 先检查告警
    triggered = alert_engine.check_alerts(metrics)
    
    if not triggered:
        return jsonify({
            "success": True,
            "decision": None,
            "alerts": []
        })
    
    # 根据告警生成决策建议
    decisions = []
    for alert in triggered:
        # 根据告警级别和动作生成决策
        action_map = {
            "critical": "emergency_response",
            "error": "investigate_and_fix",
            "warning": "monitor_and_alert",
            "info": "log_and_continue"
        }
        
        decisions.append({
            "alert_id": alert.id,
            "rule_name": alert.rule_name,
            "severity": alert.severity,
            "recommended_action": action_map.get(alert.severity, "notify"),
            "metrics": alert.metrics
        })
    
    return jsonify({
        "success": True,
        "alerts_triggered": len(triggered),
        "decisions": decisions
    })


if __name__ == '__main__':
    port = 18122
    logger.info(f"启动告警引擎API服务器: 端口 {port}")
    app.run(host='0.0.0.0', port=port, debug=False)