"""MemoryExtractor 单元测试。

使用 mock 替代实际的 Claude API 调用。
"""

import pytest

from app.models.memory import MemoryCategory
from app.services.memory_extractor import MemoryExtractor


@pytest.fixture
def extractor():
    return MemoryExtractor()


class TestFormatConversation:
    """对话格式化测试。"""

    def test_basic_formatting(self, extractor):
        messages = [
            {"role": "user", "content": "我喜欢跑步"},
            {"role": "assistant", "content": "很好的爱好！"},
        ]
        result = extractor._format_conversation(messages)
        assert "用户: 我喜欢跑步" in result
        assert "助手: 很好的爱好！" in result

    def test_empty_messages(self, extractor):
        result = extractor._format_conversation([])
        assert result == ""

    def test_skip_empty_content(self, extractor):
        messages = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "你好"},
        ]
        result = extractor._format_conversation(messages)
        assert "用户: 你好" in result
        assert result.count("用户:") == 1


class TestParseResponse:
    """LLM 响应解析测试。"""

    def test_parse_valid_json(self, extractor):
        response = '{"memories": [{"category": "preference", "content": "喜欢跑步", "importance": 7, "source_role": "user"}]}'
        items = extractor._parse_response(response)
        assert len(items) == 1
        assert items[0].category == MemoryCategory.PREFERENCE
        assert items[0].content == "喜欢跑步"
        assert items[0].importance == 7

    def test_parse_json_with_code_block(self, extractor):
        response = '```json\n{"memories": [{"category": "health", "content": "对花生过敏", "importance": 9}]}\n```'
        items = extractor._parse_response(response)
        assert len(items) == 1
        assert items[0].category == MemoryCategory.HEALTH
        assert items[0].content == "对花生过敏"

    def test_parse_empty_memories(self, extractor):
        response = '{"memories": []}'
        items = extractor._parse_response(response)
        assert len(items) == 0

    def test_parse_invalid_json(self, extractor):
        response = "这不是有效的 JSON"
        items = extractor._parse_response(response)
        assert len(items) == 0

    def test_parse_unknown_category_falls_back_to_general(self, extractor):
        response = '{"memories": [{"category": "unknown_type", "content": "测试", "importance": 5}]}'
        items = extractor._parse_response(response)
        assert len(items) == 1
        assert items[0].category == MemoryCategory.GENERAL

    def test_parse_clamps_importance(self, extractor):
        response = '{"memories": [{"category": "general", "content": "测试1", "importance": 15}, {"category": "general", "content": "测试2", "importance": -3}]}'
        items = extractor._parse_response(response)
        assert items[0].importance == 10
        assert items[1].importance == 1

    def test_parse_multiple_items(self, extractor):
        response = """{"memories": [
            {"category": "preference", "content": "喜欢跑步", "importance": 6},
            {"category": "relationship", "content": "妻子叫小美", "importance": 9},
            {"category": "goal", "content": "计划每天冥想10分钟", "importance": 7}
        ]}"""
        items = extractor._parse_response(response)
        assert len(items) == 3
        assert items[0].category == MemoryCategory.PREFERENCE
        assert items[1].category == MemoryCategory.RELATIONSHIP
        assert items[2].category == MemoryCategory.GOAL
