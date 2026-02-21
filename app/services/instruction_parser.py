import re


# 记忆类型关键词映射
_TYPE_KEYWORDS: dict[str, list[str]] = {
    "preference": [
        "喜欢", "不喜欢", "偏好", "爱好", "习惯",
        "讨厌", "最爱", "口味", "风格",
    ],
    "goal": [
        "目标", "计划", "打算", "想要", "希望",
        "决定", "挑战", "坚持",
    ],
    "health": [
        "过敏", "身体", "健康", "生病", "药",
        "睡眠", "运动", "心率", "血压", "体重",
        "咖啡因", "敏感",
    ],
    "event": [
        "生日", "纪念日", "周年", "约会", "会议",
        "接送", "放学", "上班", "每周", "每天",
        "下周", "明天",
    ],
    "relationship": [
        "妻子", "丈夫", "女儿", "儿子", "父母",
        "朋友", "同事", "老板", "家人", "伴侣",
        "老婆", "老公", "孩子", "宝宝",
    ],
}


class MemoryInstructionParser:
    """记忆指令解析器。

    识别用户消息中的 "楷，请记住..." 等指令，
    提取需要记住的内容并推断记忆类型。
    """

    INSTRUCTION_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"楷[，,]?\s*请记住[：:]?\s*(.+)", re.DOTALL),
        re.compile(r"楷[，,]?\s*记住[：:]?\s*(.+)", re.DOTALL),
        re.compile(r"请记住[：:]?\s*(.+)", re.DOTALL),
        re.compile(r"记住[：:]?\s*(.+)", re.DOTALL),
        re.compile(r"楷[，,]?\s*帮我记[一下住]*[：:]?\s*(.+)", re.DOTALL),
    ]

    def parse_instruction(self, message: str) -> str | None:
        """解析记忆指令，提取需要记住的内容。

        Args:
            message: 用户消息原文。

        Returns:
            如果是记忆指令，返回需要记住的内容（去除首尾空白）；
            否则返回 None。
        """
        message = message.strip()
        for pattern in self.INSTRUCTION_PATTERNS:
            match = pattern.match(message)
            if match:
                content = match.group(1).strip()
                return content if content else None
        return None

    def extract_memory_type(self, content: str) -> str:
        """从内容中推断记忆类型。

        通过关键词匹配确定最可能的记忆类型。
        当多个类型匹配时，返回匹配关键词最多的类型。

        Returns:
            memory_type: general | preference | goal | health | event | relationship
        """
        scores: dict[str, int] = {}
        for memory_type, keywords in _TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[memory_type] = score

        if not scores:
            return "general"

        return max(scores, key=scores.get)  # type: ignore[arg-type]
