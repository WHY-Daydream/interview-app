"""Coze Workflow API 封装"""
import json
import logging
import time
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # 秒


class CozeClient:
    """Coze Workflow 调用客户端"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (api_key or settings.COZE_API_KEY).strip()
        self.api_url = settings.COZE_API_URL
        self.workflow_id = settings.WORKFLOW_ID

    def run_workflow(self, params: dict, timeout: int = settings.TASK_TIMEOUT) -> dict:
        """同步调用 Coze Workflow（带自动重试）

        Args:
            params: 工作流输入参数
            timeout: 超时秒数

        Returns:
            工作流返回的完整响应 dict

        Raises:
            ValueError: API Key 未配置
            RuntimeError: API 返回业务错误
            ConnectionError: 多次重试后仍无法连接
            httpx.TimeoutException: 请求超时
        """
        if not self.api_key:
            raise ValueError("COZE_API_KEY 未配置，请在 .env 中设置")

        payload = {
            "workflow_id": self.workflow_id,
            "parameters": params,
            "is_async": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_exc = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "调用 Coze Workflow (尝试 %d/%d): workflow_id=%s",
                    attempt, MAX_RETRIES, self.workflow_id,
                )

                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(
                        self.api_url,
                        headers=headers,
                        json=payload,
                    )
                    resp.raise_for_status()
                    result = resp.json()

                if result.get("code") != 0:
                    raise RuntimeError(
                        f"Coze Workflow 返回错误: code={result.get('code')}, msg={result.get('msg')}"
                    )

                logger.info("Coze Workflow 调用成功: execute_id=%s", result.get("execute_id"))
                return result

            except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_exc = e
                err_msg = str(e)
                logger.warning(
                    "连接失败 (尝试 %d/%d): %s", attempt, MAX_RETRIES, err_msg,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    # 判断是否是 Coze 同步超时断开（Server disconnected）
                    if "disconnected" in err_msg.lower() or "remote protocol" in err_msg.lower():
                        raise ConnectionError(
                            f"Coze 工作流执行超时断开。Coze 同步工作流限制约 60 秒执行时间。\n"
                            f"解决办法：\n"
                            f"  1. 登录 www.coze.cn → 工作流「{self.workflow_id}」，检查工作流是否有死循环或耗时过长\n"
                            f"  2. 尝试用 Coze 控制台的「测试运行」功能，输入相同参数看是否正常返回\n"
                            f"  3. 如需长时间执行，升级 Coze Pro 账户后可启用异步模式 (is_async=True)\n"
                            f"原始错误: {err_msg}"
                        ) from e
                    raise ConnectionError(
                        f"无法连接到 Coze API（已重试 {MAX_RETRIES} 次），请检查网络环境和 .env 中的 COZE_API_URL 配置。\n"
                        f"当前 URL: {self.api_url}\n"
                        f"原始错误: {err_msg}"
                    ) from e

            except httpx.TimeoutException as e:
                raise TimeoutError(
                    f"Coze API 请求超时（{timeout}秒），工作流可能执行时间过长。\n"
                    f"可在 .env 中增加 TASK_TIMEOUT（当前 {timeout} 秒）。"
                ) from e

    def parse_output(self, result: dict) -> str:
        """从工作流返回结果中提取 output 文本"""
        raw_data = result.get("data", "")
        if not raw_data:
            return ""

        # data 字段是 JSON 字符串，需要二次解析
        try:
            data_obj = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            return data_obj.get("output", "")
        except (json.JSONDecodeError, AttributeError):
            return raw_data

    def get_debug_url(self, result: dict) -> str:
        """获取 Coze 工作流执行详情页链接"""
        return result.get("debug_url", "")

    def get_execute_id(self, result: dict) -> str:
        return result.get("execute_id", "")
