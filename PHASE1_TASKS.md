# Phase 1 开发任务清单

## 任务概述
实现PeakState记忆系统第一阶段：MVP - 核心档案与手动记忆

## 任务优先级

### P0 - 核心功能（本周完成）
- [ ] 创建数据库迁移脚本
  - [ ] user_profiles表
  - [ ] manual_memories表
  
- [ ] 实现MemoryService
  - [ ] get_user_profile()
  - [ ] update_user_profile()
  - [ ] create_manual_memory()
  - [ ] get_recent_memories()
  - [ ] delete_memory()
  - [ ] get_conversation_context()

- [ ] 实现MemoryInstructionParser
  - [ ] parse_instruction()
  - [ ] extract_memory_type()

- [ ] 创建REST API端点
  - [ ] GET /api/v1/memory/profile
  - [ ] PUT /api/v1/memory/profile
  - [ ] POST /api/v1/memory/manual
  - [ ] GET /api/v1/memory/manual/recent
  - [ ] DELETE /api/v1/memory/manual/{id}

### P1 - LLM集成（本周完成）
- [ ] 修改LLM服务集成记忆
  - [ ] 在generate_response中检测记忆指令
  - [ ] 构建记忆上下文
  - [ ] 修改提示词模板

- [ ] 创建提示词格式化函数
  - [ ] format_core_profile()
  - [ ] format_recent_memories()

### P2 - 测试（下周完成）
- [ ] 编写单元测试
  - [ ] MemoryService测试
  - [ ] MemoryInstructionParser测试
  - [ ] API端点测试

- [ ] 集成测试
  - [ ] 完整记忆流程测试

### P3 - 部署（下周完成）
- [ ] 创建部署脚本
- [ ] 生产环境测试
- [ ] 监控集成

## 当前任务
开始P0任务：创建数据库迁移脚本和核心服务代码
