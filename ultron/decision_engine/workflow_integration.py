#!/usr/bin/env python3
"""
决策引擎与工作流系统集成
Decision Engine and Workflow System Integration
"""
import requests
import logging

logger = logging.getLogger(__name__)

# 使用端口 18135 的 Agent Orchestration API
WORKFLOW_API = "http://localhost:18135"

class WorkflowIntegration:
    """工作流集成器"""
    
    def __init__(self, workflow_api=WORKFLOW_API):
        self.workflow_api = workflow_api
        
    def trigger_workflow(self, workflow_id, context=None):
        """触发工作流"""
        try:
            response = requests.post(
                f"{self.workflow_api}/workflows/run",
                json={"workflow_id": workflow_id, "params": context or {}},
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                logger.info(f"工作流 {workflow_id} 触发成功")
                return result
            else:
                logger.error(f"工作流触发失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"工作流触发异常: {e}")
            return None
    
    def list_workflows(self):
        """列出所有工作流"""
        try:
            response = requests.get(f"{self.workflow_api}/", timeout=10)
            if response.status_code == 200:
                return response.json().get('workflows', [])
            return []
        except Exception as e:
            logger.error(f"列出工作流异常: {e}")
            return []
    
    def get_workflow_status(self, workflow_id):
        """获取工作流状态"""
        # 简单实现：列出工作流并查找
        workflows = self.list_workflows()
        for wf in workflows:
            if wf.get('workflow_id') == workflow_id:
                return wf
        return None

# 全局实例
workflow_integration = WorkflowIntegration()
