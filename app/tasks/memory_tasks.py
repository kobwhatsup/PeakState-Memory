"""记忆系统定时任务。

包含每日总结和周总结的生成逻辑。
由外部调度器（如 cron 或 APScheduler）触发调用。
"""

import json
import logging
from datetime import datetime, timedelta, timezone

import anthropic

from app.config import settings
from app.database import get_mongo_db
from app.models.memory import LongTermMemory
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    """获取 Anthropic 客户端单例。"""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


DAILY_SUMMARY_PROMPT = """请对以下用户当天的记忆项进行总结。
生成一段简洁的自然语言摘要（100-200字），涵盖用户当天的主要活动、情绪和关键事件。

记忆项列表:
{items_text}

请直接输出总结文字，不要加标题或格式标记。"""

WEEKLY_SUMMARY_PROMPT = """请对以下用户一周的每日记忆进行总结分析。

每日记忆:
{daily_text}

请按以下 JSON 格式输出（仅返回 JSON，不要加其他文字）：
```json
{{
  "summary": "一段简洁的周总结（150-300字）",
  "key_themes": ["主题1", "主题2", "..."],
  "notable_changes": ["变化1", "变化2", "..."],
  "emotional_trend": "一句话描述本周情绪趋势"
}}
```"""


async def generate_daily_summaries() -> int:
    """为所有用户生成昨天的每日总结。

    通常在每晚 23:00 由调度器调用。

    Returns:
        处理的用户数量。
    """
    service = MemoryService()
    db = get_mongo_db()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    # 查找昨天有记忆但没有摘要的用户
    cursor = db.daily_memories.find(
        {"date": yesterday, "summary": None, "items": {"$ne": []}}
    )

    count = 0
    async for doc in cursor:
        user_id = doc["user_id"]
        items = doc.get("items", [])
        if not items:
            continue

        try:
            items_text = "\n".join(
                f"- [{item.get('category', 'general')}] {item.get('content', '')}"
                for item in items
            )

            client = _get_client()
            response = await client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=512,
                messages=[
                    {
                        "role": "user",
                        "content": DAILY_SUMMARY_PROMPT.format(items_text=items_text),
                    }
                ],
            )

            summary = response.content[0].text.strip()
            await service.update_daily_summary(user_id, yesterday, summary)
            count += 1
            logger.info("已为用户 %d 生成 %s 每日总结", user_id, yesterday)

        except Exception as e:
            logger.error("为用户 %d 生成每日总结失败: %s", user_id, e)

    logger.info("每日总结任务完成，处理了 %d 个用户", count)
    return count


async def generate_weekly_summaries() -> int:
    """为所有用户生成上周的周总结。

    通常在每周一 01:00 由调度器调用。

    Returns:
        处理的用户数量。
    """
    service = MemoryService()
    db = get_mongo_db()

    today = datetime.now(timezone.utc)
    # 上周一到上周日
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)

    start_date = last_monday.strftime("%Y-%m-%d")
    end_date = last_sunday.strftime("%Y-%m-%d")

    # 找出上周有记忆的所有用户
    user_ids = await db.daily_memories.distinct(
        "user_id",
        {"date": {"$gte": start_date, "$lte": end_date}},
    )

    count = 0
    for user_id in user_ids:
        try:
            # 获取上周每天的记忆
            cursor = db.daily_memories.find({
                "user_id": user_id,
                "date": {"$gte": start_date, "$lte": end_date},
            }).sort("date", 1)

            daily_texts: list[str] = []
            async for doc in cursor:
                date = doc["date"]
                summary = doc.get("summary", "")
                items = doc.get("items", [])

                if summary:
                    daily_texts.append(f"## {date}\n{summary}")
                elif items:
                    items_text = "\n".join(
                        f"- {item.get('content', '')}" for item in items
                    )
                    daily_texts.append(f"## {date}\n{items_text}")

            if not daily_texts:
                continue

            daily_text = "\n\n".join(daily_texts)

            client = _get_client()
            response = await client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": WEEKLY_SUMMARY_PROMPT.format(daily_text=daily_text),
                    }
                ],
            )

            result = _parse_weekly_response(response.content[0].text)

            long_term = LongTermMemory(
                user_id=user_id,
                period_type="weekly",
                period_start=start_date,
                period_end=end_date,
                summary=result.get("summary", ""),
                key_themes=result.get("key_themes", []),
                notable_changes=result.get("notable_changes", []),
                emotional_trend=result.get("emotional_trend"),
            )
            await service.create_long_term_memory(long_term)
            count += 1
            logger.info("已为用户 %d 生成 %s~%s 周总结", user_id, start_date, end_date)

        except Exception as e:
            logger.error("为用户 %d 生成周总结失败: %s", user_id, e)

    logger.info("周总结任务完成，处理了 %d 个用户", count)
    return count


def _parse_weekly_response(text: str) -> dict:
    """解析周总结 LLM 响应。"""
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, KeyError):
        logger.warning("周总结 JSON 解析失败，使用原文作为摘要")
        return {
            "summary": text.strip()[:500],
            "key_themes": [],
            "notable_changes": [],
            "emotional_trend": None,
        }
