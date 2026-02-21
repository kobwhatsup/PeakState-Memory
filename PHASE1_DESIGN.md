# PeakState 记忆系统 - 第一阶段技术设计文档

## 版本信息
- 版本: v1.0
- 日期: 2026-02-21
- 阶段: MVP - 核心档案与手动记忆

## 一、概述

第一阶段的目标是构建记忆系统的基础框架，实现用户核心档案管理和手动记忆功能，让用户初步感受到AI"能记住事"。

## 二、功能需求

### 2.1 核心身份档案 (Core Identity Profile)
- 用户可以在设置页面填写和编辑核心信息
- 信息包括：基本信息、核心目标、健康信息、重要日期等
- 数据以结构化格式存储在PostgreSQL中

### 2.2 手动记忆指令
- 用户可以通过"楷，请记住..."指令主动告知需要记住的信息
- 系统识别指令并提取后续内容
- 记忆以时间戳标记并存储

### 2.3 基础记忆注入
- 在AI对话时自动加载用户核心档案
- 注入最近5-10条手动记忆到对话上下文
- 优化提示词模板以支持记忆展示

## 三、数据库设计

### 3.1 用户核心档案表 (user_profiles)

```sql
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 基本信息
    nickname VARCHAR(100),
    gender VARCHAR(20),
    age_range VARCHAR(20),
    occupation VARCHAR(200),
    family_role TEXT[],
    
    -- 核心目标与价值观 (JSONB)
    core_goals JSONB DEFAULT '[]'::jsonb,
    core_values JSONB DEFAULT '[]'::jsonb,
    
    -- 健康信息 (JSONB)
    health_info JSONB DEFAULT '{}'::jsonb,  
    -- 包含: allergies, chronic_conditions, caffeine_sensitivity, 
    --      alcohol_sensitivity, baseline_heart_rate, etc.
    
    -- 重要日期 (JSONB)
    important_dates JSONB DEFAULT '[]'::jsonb,
    -- 包含: event_name, date, type (birthday, anniversary, milestone)
    
    -- 个人偏好 (JSONB)
    preferences JSONB DEFAULT '{}'::jsonb,
    -- 包含: music_preference, exercise_preference, 
    --      communication_style, etc.
    
    -- 元数据
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    
    UNIQUE(user_id)
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
```

### 3.2 手动记忆表 (manual_memories)

```sql
CREATE TABLE manual_memories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 记忆内容
    content TEXT NOT NULL,
    
    -- 记忆类型
    memory_type VARCHAR(50) DEFAULT 'general',
    -- 类型: general, preference, goal, health, event, relationship
    
    -- 重要性评分 (1-10)
    importance_score INTEGER DEFAULT 5,
    
    -- 来源信息
    source VARCHAR(100) DEFAULT 'user_instruction',
    source_message_id VARCHAR(100),
    
    -- 状态
    status VARCHAR(20) DEFAULT 'active',
    -- 状态: active, archived, deleted
    
    -- 元数据
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_accessed_at TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    
    -- 过期时间（可选）
    expires_at TIMESTAMP,
    
    CONSTRAINT check_importance_score CHECK (importance_score BETWEEN 1 AND 10)
);

CREATE INDEX idx_manual_memories_user_id ON manual_memories(user_id);
CREATE INDEX idx_manual_memories_status ON manual_memories(status);
CREATE INDEX idx_manual_memories_created_at ON manual_memories(created_at DESC);
CREATE INDEX idx_manual_memories_importance ON manual_memories(importance_score DESC);
```

## 四、API设计

### 4.1 核心档案API

#### 获取用户核心档案
```
GET /api/v1/memory/profile
Response: {
    "user_id": 123,
    "nickname": "张伟",
    "core_goals": [...],
    "health_info": {...},
    ...
}
```

#### 更新用户核心档案
```
PUT /api/v1/memory/profile
Request: {
    "nickname": "张伟",
    "core_goals": ["提升领导力"],
    "health_info": {
        "caffeine_sensitivity": "high"
    }
}
Response: {
    "success": true,
    "profile": {...}
}
```

### 4.2 手动记忆API

#### 创建记忆
```
POST /api/v1/memory/manual
Request: {
    "content": "用户每周五下午要接女儿放学",
    "memory_type": "event",
    "importance_score": 8
}
Response: {
    "id": 456,
    "content": "...",
    "created_at": "2026-02-21T15:00:00Z"
}
```

#### 获取最近记忆
```
GET /api/v1/memory/manual/recent?limit=10
Response: {
    "memories": [
        {
            "id": 456,
            "content": "...",
            "created_at": "...",
            "importance_score": 8
        }
    ]
}
```

#### 删除记忆
```
DELETE /api/v1/memory/manual/{memory_id}
Response: {
    "success": true
}
```

### 4.3 记忆检索API（内部使用）

#### 获取对话上下文记忆
```
GET /api/v1/memory/context?user_id=123
Response: {
    "core_profile": {...},
    "recent_memories": [...]
}
```

## 五、服务层设计

### 5.1 MemoryService

```python
class MemoryService:
    """记忆管理服务"""
    
    async def get_user_profile(self, user_id: int) -> dict:
        """获取用户核心档案"""
        pass
    
    async def update_user_profile(self, user_id: int, profile_data: dict) -> dict:
        """更新用户核心档案"""
        pass
    
    async def create_manual_memory(
        self, 
        user_id: int, 
        content: str,
        memory_type: str = 'general',
        importance_score: int = 5
    ) -> dict:
        """创建手动记忆"""
        pass
    
    async def get_recent_memories(
        self, 
        user_id: int, 
        limit: int = 10,
        status: str = 'active'
    ) -> List[dict]:
        """获取最近的手动记忆"""
        pass
    
    async def delete_memory(self, memory_id: int, user_id: int) -> bool:
        """删除记忆"""
        pass
    
    async def get_conversation_context(self, user_id: int) -> dict:
        """
        获取对话上下文（用于LLM）
        包含：核心档案 + 最近10条记忆
        """
        pass
```

### 5.2 MemoryInstructionParser

```python
class MemoryInstructionParser:
    """记忆指令解析器"""
    
    INSTRUCTION_PATTERNS = [
        r"楷，?请记住[：:]?(.*)",
        r"楷，?记住[：:]?(.*)",
        r"请记住[：:]?(.*)",
        r"记住[：:]?(.*)",
    ]
    
    def parse_instruction(self, message: str) -> Optional[str]:
        """
        解析记忆指令，提取需要记住的内容
        
        Args:
            message: 用户消息
            
        Returns:
            如果是记忆指令，返回需要记住的内容；否则返回None
        """
        pass
    
    def extract_memory_type(self, content: str) -> str:
        """
        从内容中推断记忆类型
        
        Returns:
            memory_type: general, preference, goal, health, event
        """
        pass
```

## 六、提示词集成

### 6.1 记忆上下文模板

```python
MEMORY_CONTEXT_TEMPLATE = """
# 用户核心信息
{core_profile}

# 最近的重要记忆
{recent_memories}

请在回复中自然地使用这些信息，而不是生硬地复述。
"""

def format_core_profile(profile: dict) -> str:
    """
    格式化核心档案为提示词文本
    
    示例输出:
    - 昵称: 张伟
    - 核心目标: 提升领导力, 平衡工作与生活
    - 健康信息: 对咖啡因高度敏感
    """
    pass

def format_recent_memories(memories: List[dict]) -> str:
    """
    格式化最近记忆为提示词文本
    
    示例输出:
    - [2天前] 用户提到需要照顾生病的女儿
    - [5天前] 用户设定了新目标：每天冥想10分钟
    """
    pass
```

### 6.2 修改现有LLM调用流程

在`app/services/llm_service.py`中：

```python
async def generate_response(
    self, 
    user_id: int, 
    message: str,
    conversation_history: List[dict]
) -> str:
    # 1. 检查是否是记忆指令
    parser = MemoryInstructionParser()
    memory_content = parser.parse_instruction(message)
    
    if memory_content:
        # 保存记忆
        await memory_service.create_manual_memory(
            user_id=user_id,
            content=memory_content,
            memory_type=parser.extract_memory_type(memory_content)
        )
        return "好的，我已经记下了！"
    
    # 2. 获取记忆上下文
    memory_context = await memory_service.get_conversation_context(user_id)
    
    # 3. 构建增强的提示词
    system_prompt = build_system_prompt_with_memory(memory_context)
    
    # 4. 调用LLM
    response = await self.call_llm(system_prompt, message, conversation_history)
    
    return response
```

## 七、前端界面设计（简要）

### 7.1 设置页面 - 核心档案编辑

```
[用户设置]
  ├── 个人信息
  │   ├── 昵称: [     ]
  │   ├── 性别: [ 选择 ]
  │   └── 职业: [     ]
  │
  ├── 核心目标 (可添加多个)
  │   ├── [x] 提升领导力
  │   ├── [x] 平衡工作与生活
  │   └── [+ 添加新目标]
  │
  ├── 健康信息
  │   ├── 过敏史: [     ]
  │   └── 咖啡因敏感度: [低/中/高]
  │
  └── [保存] [取消]
```

### 7.2 记忆管理页面（简化版）

```
[楷的记忆]
  
  我记住的关于你的事情：
  
  📅 2天前
  "你每周五下午要接女儿放学"
  [删除]
  
  🎯 5天前
  "你设定了新目标：每天冥想10分钟"
  [删除]
  
  💡 提示：你可以在对话中说"楷，请记住..."来让我记住重要的事情
```

## 八、实施步骤

### Week 1: 数据库与API
1. 创建数据库迁移脚本
2. 实现MemoryService基础方法
3. 创建REST API端点
4. 编写单元测试

### Week 2: 指令解析与集成
1. 实现MemoryInstructionParser
2. 集成到现有LLM服务
3. 修改提示词模板
4. 测试记忆指令识别

### Week 3: 前端开发
1. 开发核心档案编辑页面
2. 开发记忆管理页面
3. 集成API调用
4. UI/UX优化

### Week 4: 测试与部署
1. 端到端测试
2. 用户体验测试
3. 性能优化
4. 生产环境部署

## 九、测试计划

### 9.1 单元测试
- MemoryService所有方法
- MemoryInstructionParser解析逻辑
- API端点

### 9.2 集成测试
- 记忆指令 -> 存储 -> 检索流程
- LLM调用时的记忆注入
- API与数据库交互

### 9.3 用户测试
- 5-10名内部测试用户
- 收集反馈：记忆识别准确性、UI易用性
- 迭代优化

## 十、成功标准

### 功能完整性
- [x] 用户可以编辑核心档案
- [x] 用户可以使用"记住"指令
- [x] AI能在对话中引用核心档案
- [x] AI能在对话中引用手动记忆

### 性能指标
- 记忆检索延迟 < 100ms
- API响应时间 < 500ms
- 数据库查询优化（使用索引）

### 用户体验
- 至少30%用户尝试使用"记住"功能
- 记忆引用准确率 > 85%
- 用户反馈满意度 > 4/5

## 十一、风险与缓解

### 技术风险
1. **数据库性能**
   - 缓解：使用索引优化查询
   - 监控：集成到Prometheus

2. **LLM提示词长度**
   - 缓解：限制注入的记忆数量（最多10条）
   - 优化：只注入高重要性记忆

### 业务风险
1. **用户不使用功能**
   - 缓解：在对话中主动引导
   - 教育：提供使用示例和提示

2. **记忆内容敏感性**
   - 缓解：数据加密存储
   - 隐私：提供删除功能

## 十二、下一步（第二阶段预告）

第二阶段将实现：
- 对话自动摘要
- 向量数据库集成
- 语义相似度检索
- 记忆管理中心V2

---

**文档状态**: ✅ 已完成
**审批**: 待KOB审阅
**开始时间**: 2026-02-21
