"""MemoryInstructionParser 单元测试。

纯逻辑测试，不需要数据库。
"""
import pytest

from app.services.instruction_parser import MemoryInstructionParser

parser = MemoryInstructionParser()


class TestParseInstruction:
    """测试记忆指令解析。"""

    def test_kai_please_remember(self):
        result = parser.parse_instruction("楷，请记住：我每周五下午要接女儿放学")
        assert result == "我每周五下午要接女儿放学"

    def test_kai_remember(self):
        result = parser.parse_instruction("楷，记住我对咖啡因过敏")
        assert result == "我对咖啡因过敏"

    def test_please_remember_without_kai(self):
        result = parser.parse_instruction("请记住：我喜欢跑步")
        assert result == "我喜欢跑步"

    def test_remember_without_kai(self):
        result = parser.parse_instruction("记住我的生日是3月15号")
        assert result == "我的生日是3月15号"

    def test_kai_help_remember(self):
        result = parser.parse_instruction("楷，帮我记一下明天下午3点有会议")
        assert result == "明天下午3点有会议"

    def test_kai_with_comma_variants(self):
        # 中文逗号
        result = parser.parse_instruction("楷，请记住我的目标是每天冥想10分钟")
        assert result == "我的目标是每天冥想10分钟"

        # 英文逗号
        result = parser.parse_instruction("楷,请记住我的目标是每天冥想10分钟")
        assert result == "我的目标是每天冥想10分钟"

    def test_kai_without_comma(self):
        result = parser.parse_instruction("楷请记住我不喜欢吃辣")
        assert result == "我不喜欢吃辣"

    def test_non_instruction_returns_none(self):
        assert parser.parse_instruction("今天天气怎么样") is None
        assert parser.parse_instruction("你好楷") is None
        assert parser.parse_instruction("帮我分析一下数据") is None

    def test_empty_content_returns_none(self):
        assert parser.parse_instruction("请记住：") is None
        assert parser.parse_instruction("请记住  ") is None

    def test_whitespace_handling(self):
        result = parser.parse_instruction("  楷，请记住：  我喜欢早起  ")
        assert result == "我喜欢早起"

    def test_multiline_content(self):
        result = parser.parse_instruction("楷，请记住：我的日程安排\n周一开会\n周三健身")
        assert "我的日程安排" in result
        assert "周一开会" in result


class TestExtractMemoryType:
    """测试记忆类型推断。"""

    def test_preference_type(self):
        assert parser.extract_memory_type("我喜欢跑步和游泳") == "preference"
        assert parser.extract_memory_type("我不喜欢吃辣的食物") == "preference"

    def test_goal_type(self):
        assert parser.extract_memory_type("我的目标是每天冥想10分钟") == "goal"
        assert parser.extract_memory_type("我计划下个月开始减肥") == "goal"

    def test_health_type(self):
        assert parser.extract_memory_type("我对花生过敏") == "health"
        assert parser.extract_memory_type("我的咖啡因敏感度很高") == "health"

    def test_event_type(self):
        assert parser.extract_memory_type("我女儿的生日是5月20号") == "event"
        assert parser.extract_memory_type("每周五下午要接孩子放学") == "event"

    def test_relationship_type(self):
        assert parser.extract_memory_type("我妻子叫小美") == "relationship"
        assert parser.extract_memory_type("我儿子今年3岁") == "relationship"

    def test_general_type_fallback(self):
        assert parser.extract_memory_type("今天的项目进展不错") == "general"
        assert parser.extract_memory_type("明天要出差") == "general"

    def test_mixed_type_picks_highest_score(self):
        # "每周五接女儿放学" 同时匹配 event(每周) 和 relationship(女儿)
        result = parser.extract_memory_type("每周五下午接女儿放学")
        assert result in ("event", "relationship")
