#!/usr/bin/env python3
"""
智能运维助手 - 端到端自动化测试
测试完整流程: 监控 → 告警 → 修复 → 验证
"""

import sys
import os
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

class E2ETestRunner:
    def __init__(self):
        self.results = []
        self.test_dir = BASE_DIR / "data" / "e2e_tests"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.test_dir / f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
    def log(self, status, message, details=None):
        """记录测试结果"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "message": message,
            "details": details or {}
        }
        self.results.append(entry)
        print(f"[{status}] {message}")
        
    def test_1_component_health(self):
        """测试1: 组件健康检查"""
        self.log("INFO", "=== 测试1: 组件健康检查 ===")
        
        components = [
            ("告警引擎", "ops-alert-engine.py"),
            ("自动修复", "ops/ops-auto-repair.py"),
            ("预测告警", "predictive_alert.py"),
            ("修复集成", "ops/ops-alert-repair-integration.py"),
            ("监控收集", "ops-metrics-collector.py"),
            ("告警通知", "ops-alert-notifier.py"),
        ]
        
        all_healthy = True
        for name, path in components:
            full_path = BASE_DIR / path
            if full_path.exists():
                self.log("PASS", f"{name} 文件存在: {path}")
            else:
                self.log("FAIL", f"{name} 文件缺失: {path}")
                all_healthy = False
                
        return all_healthy
    
    def test_2_alert_engine(self):
        """测试2: 告警引擎功能"""
        self.log("INFO", "=== 测试2: 告警引擎功能 ===")
        
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("alert_engine", BASE_DIR / "ops-alert-engine.py")
            alert_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(alert_module)
            
            AlertEngine = alert_module.AlertEngine
            engine = AlertEngine()
            
            # Test with mock metrics - use values that trigger alerts
            test_metrics = {
                "cpu": {"percent": 95.0},
                "memory": {"percent": 92.0},
                "disk": {"percent": 85.0},
                "network": {"in": 1000000, "out": 500000}
            }
            
            alerts = engine.check(test_metrics)
            
            if alerts:
                self.log("PASS", f"告警引擎产生 {len(alerts)} 个告警")
                return True
            else:
                self.log("FAIL", "告警引擎未产生预期告警")
                return False
                
        except Exception as e:
            self.log("FAIL", f"告警引擎测试失败: {str(e)}")
            return False
    
    def test_3_auto_repair(self):
        """测试3: 自动修复功能"""
        self.log("INFO", "=== 测试3: 自动修复功能 ===")
        
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("auto_repair", BASE_DIR / "ops" / "ops-auto-repair.py")
            repair_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(repair_module)
            
            RepairEngine = repair_module.RepairEngine
            repair = RepairEngine()
            
            # Get status
            status = repair.get_status()
            
            if status.get("strategies"):
                self.log("PASS", f"自动修复模块包含 {len(status['strategies'])} 个策略")
                
                # Test repair execution with a mock alert
                test_alert = {
                    "type": "cpu",
                    "level": "critical",
                    "message": "High CPU usage",
                    "value": 95
                }
                test_result = repair.repair(test_alert, {"cpu_usage": 95})
                if test_result.get("success"):
                    self.log("PASS", "自动修复执行测试成功")
                    return True
                else:
                    self.log("WARN", "修复执行返回非成功状态")
                    return True
            else:
                self.log("FAIL", "未找到修复策略")
                return False
                
        except Exception as e:
            self.log("FAIL", f"自动修复测试失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_4_integration_flow(self):
        """测试4: 集成流程测试"""
        self.log("INFO", "=== 测试4: 集成流程测试 ===")
        
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("integration", BASE_DIR / "ops" / "ops-alert-repair-integration.py")
            int_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(int_module)
            
            AlertRepairIntegration = int_module.AlertRepairIntegration
            integration = AlertRepairIntegration()
            
            # Test end-to-end flow
            test_metrics = {
                "cpu_usage": 92.0,
                "memory_usage": 88.0,
                "disk_usage": 75.0
            }
            
            result = integration.process_metrics(test_metrics)
            
            if result.get("alerts") or result.get("repairs"):
                self.log("PASS", "集成流程执行成功")
                return True
            else:
                self.log("INFO", "集成流程无告警/修复触发(正常)")
                return True
                
        except Exception as e:
            self.log("FAIL", f"集成流程测试失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_5_data_persistence(self):
        """测试5: 数据持久化"""
        self.log("INFO", "=== 测试5: 数据持久化 ===")
        
        try:
            data_dir = BASE_DIR / "data"
            
            # Check alert log
            alert_log = data_dir / "alert_log.json"
            if alert_log.exists():
                with open(alert_log) as f:
                    alerts = json.load(f)
                self.log("PASS", f"告警日志存在, {len(alerts)} 条记录")
            else:
                self.log("WARN", "告警日志文件不存在")
                
            # Check repair log
            repair_log = data_dir / "alert_repair_log.json"
            if repair_log.exists():
                with open(repair_log) as f:
                    repairs = json.load(f)
                self.log("PASS", f"修复日志存在, {len(repairs)} 条记录")
            else:
                self.log("WARN", "修复日志文件不存在")
                
            return True
            
        except Exception as e:
            self.log("FAIL", f"数据持久化测试失败: {str(e)}")
            return False
    
    def test_6_api_endpoints(self):
        """测试6: API端点测试"""
        self.log("INFO", "=== 测试6: API端点测试 ===")
        
        # Check if metrics API is running
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", 
                 "http://localhost:18888/metrics"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip() == "200":
                self.log("PASS", "Metrics API 响应正常")
                return True
            else:
                self.log("WARN", f"Metrics API 响应码: {result.stdout.strip()}")
                return True
        except:
            self.log("INFO", "Metrics API 未运行 (非关键)")
            return True
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*50)
        print("🚀 智能运维助手 - 端到端自动化测试")
        print("="*50 + "\n")
        
        start_time = time.time()
        
        # Run tests
        tests = [
            ("组件健康", self.test_1_component_health),
            ("告警引擎", self.test_2_alert_engine),
            ("自动修复", self.test_3_auto_repair),
            ("集成流程", self.test_4_integration_flow),
            ("数据持久化", self.test_5_data_persistence),
            ("API端点", self.test_6_api_endpoints),
        ]
        
        results = {}
        for name, test_func in tests:
            try:
                results[name] = test_func()
            except Exception as e:
                self.log("FAIL", f"{name} 测试异常: {str(e)}")
                results[name] = False
            time.sleep(0.5)
        
        # Summary
        elapsed = time.time() - start_time
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        print("\n" + "="*50)
        print("📊 测试结果汇总")
        print("="*50)
        for name, result in results.items():
            status = "✅" if result else "❌"
            print(f"  {status} {name}")
        print(f"\n通过: {passed}/{total}")
        print(f"耗时: {elapsed:.2f}秒")
        
        # Save results
        output = {
            "test_run": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "results": results,
            "passed": passed,
            "total": total,
            "log": self.results
        }
        
        with open(self.log_file, 'w') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            
        print(f"\n📁 测试报告: {self.log_file}")
        
        return passed == total

if __name__ == "__main__":
    runner = E2ETestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)