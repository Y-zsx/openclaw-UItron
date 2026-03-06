#!/usr/bin/env python3
"""
预测性决策API
Predictive Decision API
基于历史数据进行趋势预测和主动决策建议
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
import logging
import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)

# 预测数据库路径
PREDICT_DB = '/root/.openclaw/workspace/ultron/decision_engine/predictive_data.db'

def init_predictive_db():
    """初始化预测数据库"""
    conn = sqlite3.connect(PREDICT_DB)
    c = conn.cursor()
    
    # 创建指标历史表
    c.execute('''CREATE TABLE IF NOT EXISTS metrics_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        metric_type TEXT NOT NULL,
        value REAL NOT NULL,
        source TEXT
    )''')
    
    # 创建决策历史表
    c.execute('''CREATE TABLE IF NOT EXISTS decision_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        decision_type TEXT NOT NULL,
        context TEXT,
        action TEXT,
        result TEXT,
        success INTEGER
    )''')
    
    # 创建预测结果表
    c.execute('''CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        prediction_type TEXT NOT NULL,
        metric_type TEXT,
        predicted_value REAL,
        confidence REAL,
        time_horizon TEXT,
        actual_value REAL,
        accuracy REAL
    )''')
    
    # 创建告警预测表
    c.execute('''CREATE TABLE IF NOT EXISTS alert_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        probability REAL,
        estimated_time TEXT,
        severity TEXT,
        triggered INTEGER DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()
    logger.info("预测数据库初始化完成")


def get_db_connection():
    """获取数据库连接"""
    return sqlite3.connect(PREDICT_DB)


class TrendAnalyzer:
    """趋势分析器"""
    
    @staticmethod
    def analyze_trend(values, window=10):
        """分析趋势方向和强度"""
        if len(values) < 2:
            return {'trend': 'stable', 'strength': 0, 'velocity': 0}
        
        # 计算移动平均
        recent = values[-window:] if len(values) > window else values
        
        # 线性回归斜率
        n = len(recent)
        if n < 2:
            return {'trend': 'stable', 'strength': 0, 'velocity': 0}
        
        x = list(range(n))
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(recent)
        
        cov = sum((x[i] - mean_x) * (recent[i] - mean_y) for i in range(n))
        var = sum((x[i] - mean_x) ** 2 for i in range(n))
        
        if var == 0:
            return {'trend': 'stable', 'strength': 0, 'velocity': 0}
        
        slope = cov / var
        
        # 计算趋势强度 (基于变化率)
        mean_val = mean_y if mean_y != 0 else 1
        strength = abs(slope / mean_val) * 100
        
        trend = 'stable'
        if slope > 0.1:
            trend = 'rising'
        elif slope < -0.1:
            trend = 'falling'
        
        return {
            'trend': trend,
            'strength': min(100, strength),
            'velocity': slope,
            'predicted_next': recent[-1] + slope
        }
    
    @staticmethod
    def detect_anomalies(values, threshold=2):
        """检测异常值"""
        if len(values) < 5:
            return []
        
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        
        if stdev == 0:
            return []
        
        anomalies = []
        for i, v in enumerate(values):
            z_score = abs((v - mean) / stdev)
            if z_score > threshold:
                anomalies.append({
                    'index': i,
                    'value': v,
                    'z_score': z_score
                })
        
        return anomalies


class PredictiveEngine:
    """预测引擎"""
    
    def __init__(self):
        self.trend_analyzer = TrendAnalyzer()
    
    def predict_metric(self, metric_type, horizon='5m'):
        """预测指标未来值"""
        conn = get_db_connection()
        c = conn.cursor()
        
        # 获取历史数据
        c.execute('''SELECT timestamp, value FROM metrics_history 
                     WHERE metric_type = ? ORDER BY timestamp DESC LIMIT 50''',
                  (metric_type,))
        rows = c.fetchall()
        conn.close()
        
        if len(rows) < 5:
            return None
        
        values = [r[1] for r in rows]
        values.reverse()  #  oldest first
        
        trend = self.trend_analyzer.analyze_trend(values)
        
        # 预测
        horizon_minutes = {'1m': 1, '5m': 5, '15m': 15, '1h': 60}.get(horizon, 5)
        points_needed = min(len(values), horizon_minutes)
        
        predicted_value = trend.get('predicted_next', values[-1])
        predicted_value = max(0, predicted_value)  # 确保非负
        
        # 计算置信度
        confidence = self._calculate_confidence(values, trend)
        
        return {
            'metric_type': metric_type,
            'current_value': values[-1],
            'predicted_value': round(predicted_value, 2),
            'trend': trend,
            'confidence': confidence,
            'horizon': horizon,
            'data_points': len(values)
        }
    
    def _calculate_confidence(self, values, trend):
        """计算预测置信度"""
        if len(values) < 10:
            return 0.5
        
        # 基于数据稳定性和趋势一致性
        if len(values) > 1:
            cv = statistics.stdev(values) / statistics.mean(values) if statistics.mean(values) > 0 else 0
        else:
            cv = 0
        
        # 低变异系数 = 高置信度
        stability = max(0, 1 - cv)
        
        # 趋势一致性
        trend_strength = trend.get('strength', 0) / 100
        
        confidence = (stability * 0.6 + (1 - trend_strength) * 0.4)
        return min(0.95, max(0.3, confidence))
    
    def predict_alerts(self):
        """预测潜在告警"""
        conn = get_db_connection()
        c = conn.cursor()
        
        predictions = []
        
        # 获取CPU和内存指标
        for metric in ['cpu', 'memory', 'disk']:
            c.execute('''SELECT timestamp, value FROM metrics_history 
                         WHERE metric_type = ? ORDER BY timestamp DESC LIMIT 30''',
                      (metric,))
            rows = c.fetchall()
            
            if len(rows) >= 10:
                values = [r[1] for r in rows]
                values.reverse()
                
                trend = self.trend_analyzer.analyze_trend(values)
                
                # 预测是否将达到阈值
                thresholds = {'cpu': 80, 'memory': 85, 'disk': 90}
                threshold = thresholds.get(metric, 80)
                
                current = values[-1]
                predicted = trend.get('predicted_next', current)
                
                if predicted > threshold:
                    prob = min(1.0, (predicted - threshold) / 20 + 0.3)
                    severity = 'critical' if predicted > threshold * 1.1 else 'warning'
                    
                    predictions.append({
                        'alert_type': f'{metric}_high',
                        'probability': round(prob, 2),
                        'current_value': current,
                        'predicted_value': round(predicted, 2),
                        'threshold': threshold,
                        'severity': severity,
                        'estimated_time': 'within 5 minutes' if trend['trend'] == 'rising' else 'unknown'
                    })
        
        conn.close()
        return predictions
    
    def suggest_decisions(self, context):
        """基于预测建议决策"""
        conn = get_db_connection()
        c = conn.cursor()
        
        suggestions = []
        
        # 分析最近决策模式
        c.execute('''SELECT action, COUNT(*) as cnt, AVG(success) as success_rate 
                     FROM decision_history WHERE success = 1 GROUP BY action 
                     ORDER BY cnt DESC LIMIT 5''')
        successful_actions = c.fetchall()
        
        # 基于指标趋势建议
        c.execute('''SELECT metric_type, value FROM metrics_history 
                     WHERE timestamp > datetime('now', '-1 hour')''')
        recent_metrics = c.fetchall()
        
        # 按类型分组
        metrics_by_type = defaultdict(list)
        for m_type, val in recent_metrics:
            metrics_by_type[m_type].append(val)
        
        # 生成建议
        for m_type, values in metrics_by_type.items():
            if len(values) >= 5:
                trend = self.trend_analyzer.analyze_trend(values)
                
                if m_type == 'cpu' and trend['trend'] == 'rising' and values[-1] > 60:
                    suggestions.append({
                        'type': 'preventive_action',
                        'action': 'scale_down_services',
                        'reason': f'CPU趋势上升，当前{values[-1]:.1f}%，预测将继续上升',
                        'priority': 'high',
                        'metric': 'cpu'
                    })
                elif m_type == 'memory' and trend['trend'] == 'rising' and values[-1] > 70:
                    suggestions.append({
                        'type': 'preventive_action',
                        'action': 'clear_cache',
                        'reason': f'内存趋势上升，当前{m_values[-1]:.1f}%',
                        'priority': 'high',
                        'metric': 'memory'
                    })
        
        conn.close()
        return suggestions


# 全局预测引擎
predictive_engine = PredictiveEngine()
init_predictive_db()


def create_predictive_routes(app):
    """创建预测性路由"""
    
    @app.route('/predict/metric', methods=['POST'])
    def predict_metric():
        """预测指标未来值"""
        data = request.json
        metric_type = data.get('metric_type', 'cpu')
        horizon = data.get('horizon', '5m')
        
        result = predictive_engine.predict_metric(metric_type, horizon)
        
        if result:
            return jsonify({'success': True, 'prediction': result})
        else:
            return jsonify({
                'success': False, 
                'error': '数据不足，无法预测'
            }), 400
    
    @app.route('/predict/alerts', methods=['GET'])
    def predict_alerts():
        """预测潜在告警"""
        predictions = predictive_engine.predict_alerts()
        return jsonify({
            'success': True,
            'predictions': predictions,
            'count': len(predictions)
        })
    
    @app.route('/predict/decisions', methods=['POST'])
    def suggest_decisions():
        """获取决策建议"""
        data = request.json
        context = data.get('context', {})
        
        suggestions = predictive_engine.suggest_decisions(context)
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'count': len(suggestions)
        })
    
    @app.route('/predict/trend', methods=['POST'])
    def analyze_trend():
        """分析趋势"""
        data = request.json
        metric_type = data.get('metric_type')
        
        if not metric_type:
            return jsonify({'success': False, 'error': '需要metric_type'}), 400
        
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''SELECT value FROM metrics_history 
                     WHERE metric_type = ? ORDER BY timestamp DESC LIMIT 50''',
                  (metric_type,))
        rows = c.fetchall()
        conn.close()
        
        if len(rows) < 5:
            return jsonify({'success': False, 'error': '数据不足'}), 400
        
        values = [r[0] for r in rows]
        values.reverse()
        
        trend = TrendAnalyzer.analyze_trend(values)
        anomalies = TrendAnalyzer.detect_anomalies(values)
        
        return jsonify({
            'success': True,
            'metric_type': metric_type,
            'trend': trend,
            'anomalies': anomalies,
            'data_points': len(values),
            'current_value': values[-1]
        })
    
    @app.route('/predict/record', methods=['POST'])
    def record_metric():
        """记录指标数据"""
        data = request.json
        
        metric_type = data.get('metric_type')
        value = data.get('value')
        source = data.get('source', 'api')
        
        if not metric_type or value is None:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''INSERT INTO metrics_history (timestamp, metric_type, value, source)
                     VALUES (?, ?, ?, ?)''',
                  (datetime.utcnow().isoformat(), metric_type, value, source))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    @app.route('/predict/history', methods=['GET'])
    def get_prediction_history():
        """获取历史预测及准确性"""
        limit = int(request.args.get('limit', 20))
        
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''SELECT * FROM predictions ORDER BY timestamp DESC LIMIT ?''',
                  (limit,))
        rows = c.fetchall()
        
        predictions = []
        for r in rows:
            predictions.append({
                'id': r[0],
                'timestamp': r[1],
                'type': r[2],
                'metric': r[3],
                'predicted': r[4],
                'confidence': r[5],
                'actual': r[7],
                'accuracy': r[8]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'predictions': predictions
        })
    
    @app.route('/predict/auto-decide', methods=['POST'])
    def auto_predict_decide():
        """预测性自动决策"""
        data = request.json
        auto_execute = data.get('auto_execute', False)
        
        # 1. 预测潜在告警
        alert_predictions = predictive_engine.predict_alerts()
        
        # 2. 获取决策建议
        suggestions = predictive_engine.suggest_decisions({})
        
        # 3. 生成决策
        decisions = []
        
        for pred in alert_predictions:
            if pred['probability'] > 0.7:
                decisions.append({
                    'type': 'predictive',
                    'trigger': pred['alert_type'],
                    'action': f'prevent_{pred["alert_type"]}',
                    'reason': f'预测{pred["alert_type"]}概率{pred["probability"]*100:.0f}%',
                    'priority': pred['severity'],
                    'auto_execute': auto_execute
                })
        
        for sugg in suggestions:
            if sugg['priority'] == 'high':
                decisions.append({
                    'type': 'suggestion',
                    'trigger': sugg['type'],
                    'action': sugg['action'],
                    'reason': sugg['reason'],
                    'priority': sugg['priority'],
                    'auto_execute': auto_execute
                })
        
        return jsonify({
            'success': True,
            'alert_predictions': alert_predictions,
            'suggestions': suggestions,
            'decisions': decisions,
            'decision_count': len(decisions)
        })
    
    logger.info("预测性决策路由已注册")


if __name__ == '__main__':
    app = Flask(__name__)
    create_predictive_routes(app)
    app.run(host='0.0.0.0', port=18125, debug=False)