"""从对话中自动提取记忆的服务。

使用 Claude API 分析对话内容，自动识别并提取用户的关键信息，
包括偏好、目标、健康状况、重要事件、人际关系等。
"""

import json
import logging

import anthropic

from app.config import settings
from app.models.memory import MemoryCategory, MemoryItem

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """你是一个记忆提取专家。请分析以下对话，提取用户透露的关键个人信息。

只提取**事实性信息**，忽略闲聊和无意义内容。每条记忆应该是独立的、有价值的信息片段。

请按以下 JSON 格式返回（仅返回 JSON，不要加任何其他文字）：
```json
{
  "memories": [
    {
      "category": "preference|goal|health|event|relationship|emotion|insight|general",
      "content": "简洁的记忆内容描述",
      "importance": 1-10,
      "source_role": "user"
    }
  ]
}
```

分类说明：
- preference: 个人偏好、喜好、习惯（如：喜欢跑步、不吃辣）
- goal: 目标、计划、愿望（如：想学习冥想、计划减重）
- health: 健康相关（如：对花生过敏、睡眠质量差）
- event: 重要事件、日程（如：女儿生日5月20号、每周五接孩子）
- relationship: 人际关系（如：妻子叫小美、有两个孩子）
- emotion: 情绪状态（如：最近工作压力大、对新项目很兴奋）
- insight: 用户的自我认知或洞察（如：发现自己在压力下会暴饮暴食）
- general: 其他重要信息

重要性评分标准：
- 8-10: 核心身份信息、长期目标、健康禁忌、重要人际关系
- 5-7: 日常偏好、近期计划、情绪状态
- 1-4: 临时信息、一次性提及

如果对话中没有值得提取的信息，返回空列表：{"memories": []}

对话内容：
"""


class MemoryExtractor:
    """从对话中自动提取记忆的服务。"""

    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        """延迟初始化 Anthropic 客户端。"""
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY
            )
        return self._client

    async def extract_from_conversation(
        self, messages: list[dict[str, str]]
    ) -> list[MemoryItem]:
        """从对话消息中提取记忆。

        Args:
            messages: 对话消息列表，每项包含 role 和 content。

        Returns:
            提取的记忆项列表。
        """
        if not messages:
            return []

        # 构建对话文本
        conversation_text = self._format_conversation(messages)
        if not conversation_text.strip():
            return []

        try:
            response = await self.client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": EXTRACTION_PROMPT + conversation_text,
                    }
                ],
            )

            return self._parse_response(response.content[0].text)

        except anthropic.APIError as e:
            logger.error("Claude API 调用失败: %s", e)
            return []
        except Exception as e:
            logger.error("记忆提取失败: %s", e)
            return []

    def _format_conversation(self, messages: list[dict[str, str]]) -> str:
        """将消息列表格式化为对话文本。"""
        lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                label = "用户" if role == "user" else "助手"
                lines.append(f"{label}: {content}")
        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> list[MemoryItem]:
        """解析 LLM 返回的 JSON 响应为 MemoryItem 列表。"""
        try:
            # 处理可能被 ```json 包裹的情况
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            data = json.loads(text)
            memories = data.get("memories", [])

            items: list[MemoryItem] = []
            for mem in memories:
                try:
                    category = MemoryCategory(mem.get("category", "general"))
                except ValueError:
                    category = MemoryCategory.GENERAL

                items.append(
                    MemoryItem(
                        category=category,
                        content=mem.get("content", ""),
                        importance=max(1, min(10, int(mem.get("importance", 5)))),
                        source_role=mem.get("source_role", "user"),
                    )
                )
            return items

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("解析 LLM 响应失败: %s | 原文: %s", e, response_text[:200])
            return []
