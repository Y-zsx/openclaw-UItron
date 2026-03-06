#!/usr/bin/env python3
"""
预测性决策调度器
Predictive Decision Scheduler
定时收集指标、运行预测、生成决策建议
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta
from predictive_api import (
    PredictiveEngine, TrendAnalyzer, get_db_connection, 
    init_predictive_db, PREDICT_DB
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 系统指标收集
METRICS_INTERVAL = 60  # 秒

def collect_system_metrics():
    """收集系统指标"""
    try:
        import psutil
        
        metrics = {
            'cpu': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'load': os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0
        }
        
        conn = get_db_connection()
        c = conn.cursor()
        
        for metric_type, value in metrics.items():
            c.execute('''INSERT INTO metrics_history 
                         (timestamp, metric_type, value, source)
                         VALUES (?, ?, ?, ?)''',
                     (datetime.utcnow().isoformat(), metric_type, value, 'system'))
        
        conn.commit()
        conn.close()
        
        return metrics
    except Exception as e:
        logger.error(f"收集系统指标失败: {e}")
        return {}


def run_predictions():
    """运行预测分析"""
    engine = PredictiveEngine()
    
    predictions = {
        'cpu': engine.predict_metric('cpu', '5m'),
        'memory': engine.predict_metric('memory', '5m'),
        'disk': engine.predict_metric('disk', '15m'),
        'load': engine.predict_metric('load', '5m')
    }
    
    # 告警预测
    alert_preds = engine.predict_alerts()
    
    # 决策建议
    suggestions = engine.suggest_decisions({})
    
    return {
        'predictions': {k: v for k, v in predictions.items() if v},
        'alert_predictions': alert_preds,
        'suggestions': suggestions,
        'timestamp': datetime.utcnow().isoformat()
    }


def check_and_execute_decisions(predictions):
    """检查预测并执行决策"""
    executed = []
    
    for pred in predictions.get('alert_predictions', []):
        if pred.get('probability', 0) > 0.8:
            # 高概率告警，执行预防措施
            action = pred['alert_type']
            
            logger.warning(f"预测到高概率告警: {action}, 执行预防措施")
            
            # 这里可以集成实际的自动化修复
            executed.append({
                'action': action,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'executed'
            })
    
    return executed


def export_predictions():
    """导出预测结果供其他模块使用"""
    result = run_predictions()
    
    # 保存到文件
    output_file = '/root/.openclaw/workspace/ultron/decision_engine/latest_predictions.json'
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    return result


def run_scheduler_cycle():
    """运行一个调度周期"""
    logger.info("开始预测性决策调度周期")
    
    # 1. 收集系统指标
    metrics = collect_system_metrics()
    logger.info(f"收集指标: {metrics}")
    
    # 2. 运行预测
    predictions = run_predictions()
    logger.info(f"生成{len(predictions.get('predictions', {}))}项预测, "
                f"{len(predictions.get('alert_predictions', []))}个告警预测")
    
    # 3. 检查并执行决策
    executed = check_and_execute_decisions(predictions)
    if executed:
        logger.info(f"执行了{len(executed)}项预防决策")
    
    # 4. 导出结果
    export_predictions()
    
    return {
        'metrics': metrics,
        'predictions': predictions,
        'executed': executed
    }


def continuous_scheduler(interval=METRICS_INTERVAL):
    """持续运行调度器"""
    logger.info(f"启动预测性决策调度器 (间隔: {interval}秒)")
    
    while True:
        try:
            run_scheduler_cycle()
        except Exception as e:
            logger.error(f"调度周期出错: {e}")
        
        time.sleep(interval)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='预测性决策调度器')
    parser.add_argument('--once', action='store_true', help='运行一次然后退出')
    parser.add_argument('--interval', type=int, default=60, help='运行间隔(秒)')
    
    args = parser.parse_args()
    
    if args.once:
        run_scheduler_cycle()
    else:
        continuous_scheduler(args.interval)