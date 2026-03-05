#!/usr/bin/env python3
"""
增强型系统自愈引擎 v2
自动检测、诊断和修复系统问题
"""
import json
import subprocess
import time
import psutil
import requests
from datetime import datetime
from pathlib import Path

# 端口配置
PORTS = {
    18100: "workflow_engine",
    18120: "decision_engine",
    18128: "automation",
    18150: "agent_network",
    18160: "agent_executor",
    18170: "feedback_learning",
    18200: "ops_dashboard",
    18210: "executor_api",
}

# 关键进程
CRITICAL_PROCESSES = [
    "agent_api_gateway.py",
    "workflow_engine.py",
    "decision_engine.py",
    "automation.py",
    "agent_network.py",
    "agent_orchestrator.py",
]

class SelfHealerV2:
    def __init__(self):
        self.data_dir = Path("/root/.openclaw/workspace/ultron/data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.heal_log = []
    
    def log(self, level, message):
        """日志记录"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}"
        self.heal_log.append(entry)
        print(entry)
    
    def check_port(self, port):
        """检查端口是否在监听"""
        try:
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True, text=True, timeout=5
            )
            return f":{port}" in result.stdout
        except:
            return False
    
    def check_process(self, name):
        """检查进程是否运行"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", name],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except:
            return False
    
    def restart_service(self, service_name, port):
        """尝试重启服务"""
        self.log("INFO", f"尝试重启服务: {service_name} (端口 {port})")
        
        # 查找相关进程
        try:
            result = subprocess.run(
                ["pkill", "-f", service_name],
                capture_output=True, text=True, timeout=10
            )
            time.sleep(2)
            
            # 查找启动脚本
            tools_dir = Path("/root/.openclaw/workspace/ultron/tools")
            for script in tools_dir.glob(f"*{service_name}*.py"):
                self.log("INFO", f"找到启动脚本: {script}")
                subprocess.Popen(
                    ["python3", str(script)],
                    cwd=tools_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                time.sleep(3)
                return True
        except Exception as e:
            self.log("ERROR", f"重启失败: {e}")
        return False
    
    def check_system_resources(self):
        """检查系统资源"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        issues = []
        if cpu > 90:
            issues.append(f"CPU过高: {cpu}%")
        if memory.percent > 90:
            issues.append(f"内存过高: {memory.percent}%")
        if disk.percent > 90:
            issues.append(f"磁盘过高: {disk.percent}%")
        
        return {
            "cpu": cpu,
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
            "issues": issues
        }
    
    def run_diagnostics(self):
        """运行完整诊断"""
        self.log("INFO", "=" * 50)
        self.log("INFO", "开始系统诊断...")
        self.log("INFO", "=" * 50)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "ports": {},
            "processes": {},
            "resources": {}
        }
        
        # 端口检查
        self.log("INFO", "\n【端口检查】")
        ports_healthy = 0
        for port, name in PORTS.items():
            is_listening = self.check_port(port)
            results["ports"][name] = is_listening
            status = "✅" if is_listening else "❌"
            self.log("INFO", f"  {status} {name}:{port}")
            if is_listening:
                ports_healthy += 1
        
        # 进程检查
        self.log("INFO", "\n【进程检查】")
        procs_healthy = 0
        for proc in CRITICAL_PROCESSES:
            is_running = self.check_process(proc)
            results["processes"][proc] = is_running
            status = "✅" if is_running else "❌"
            self.log("INFO", f"  {status} {proc}")
            if is_running:
                procs_healthy += 1
        
        # 资源检查
        self.log("INFO", "\n【资源检查】")
        resources = self.check_system_resources()
        results["resources"] = resources
        self.log("INFO", f"  CPU: {resources['cpu']}%")
        self.log("INFO", f"  内存: {resources['memory_percent']}%")
        self.log("INFO", f"  磁盘: {resources['disk_percent']}%")
        if resources['issues']:
            self.log("WARNING", f"  发现问题: {resources['issues']}")
        
        # 计算健康分
        total = len(PORTS) + len(CRITICAL_PROCESSES)
        healthy = ports_healthy + procs_healthy
        health_score = round(healthy / total * 100, 1)
        
        self.log("INFO", "\n" + "=" * 50)
        self.log("INFO", f"健康评分: {health_score}% ({healthy}/{total})")
        self.log("INFO", "=" * 50)
        
        results["health_score"] = health_score
        results["healthy_items"] = healthy
        results["total_items"] = total
        
        # 保存诊断报告
        report_path = self.data_dir / "self_healer_diag.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2)
        
        # 自动修复检查
        if health_score < 80:
            self.log("WARNING", f"健康分低于80%，启动自动修复...")
            self.auto_heal(results)
        
        return results
    
    def auto_heal(self, diag_results):
        """自动修复"""
        self.log("INFO", "\n【自动修复】")
        
        # 端口修复
        for port, name in PORTS.items():
            if not diag_results["ports"].get(name, False):
                self.log("WARNING", f"端口 {port} ({name}) 不通，尝试修复...")
                # 尝试通过systemd或直接启动
                self.restart_service(name, port)
        
        # 进程修复
        for proc in CRITICAL_PROCESSES:
            if not diag_results["processes"].get(proc, False):
                self.log("WARNING", f"进程 {proc} 未运行，尝试启动...")
                self.restart_service(proc.replace(".py", ""), 0)
        
        # 保存修复日志
        heal_path = self.data_dir / "self_healer_log.json"
        with open(heal_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "log": self.heal_log
            }, f, indent=2)

def main():
    healer = SelfHealerV2()
    results = healer.run_diagnostics()
    print(f"\n诊断完成，健康分: {results['health_score']}%")

if __name__ == "__main__":
    main()