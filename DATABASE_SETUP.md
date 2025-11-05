# 数据库自动初始化说明

## 概述

本项目的数据库现在完全自动化管理，无需手动创建或初始化数据库文件。

## 自动初始化流程

1. **首次启动**: 当后端服务首次启动时，会自动创建数据库文件 `backend/ai_polish.db`
2. **表结构创建**: 所有必需的数据表会自动创建，包括：
   - `users` - 用户表
   - `optimization_sessions` - 优化会话表
   - `optimization_segments` - 优化段落表
   - `session_history` - 会话历史表
   - `change_logs` - 变更对照记录表
   - `custom_prompts` - 自定义提示词表
   - `queue_status` - 队列状态表
   - `system_settings` - 系统设置表

3. **字段自动更新**: 如果检测到旧数据库缺少新字段，会自动添加

## 数据表结构

### users (用户表)
- `id` - 主键
- `card_key` - 卡密
- `access_link` - 访问链接
- `is_active` - 是否激活
- `created_at` - 创建时间
- `last_used` - 最后使用时间
- `usage_limit` - 使用次数限制
- `usage_count` - 已使用次数

### optimization_sessions (优化会话表)
- `id` - 主键
- `user_id` - 用户ID
- `session_id` - 会话ID
- `original_text` - 原始文本
- `current_stage` - 当前阶段 (polish/emotion_polish/enhance)
- `status` - 状态 (queued/processing/completed/failed)
- `progress` - 进度
- `processing_mode` - 处理模式 (paper_polish/paper_polish_enhance/emotion_polish)
- `polish_model`, `enhance_model`, `emotion_model` - 模型配置
- 以及其他配置和状态字段

### optimization_segments (优化段落表)
- `id` - 主键
- `session_id` - 会话ID
- `segment_index` - 段落序号
- `stage` - 阶段 (polish/emotion_polish/enhance)
- `original_text` - 原始文本
- `polished_text` - 润色后文本
- `enhanced_text` - 增强后文本
- `status` - 状态
- `is_title` - 是否为标题

### change_logs (变更对照记录表)
- `id` - 主键
- `session_id` - 会话ID
- `segment_index` - 段落序号
- `stage` - 阶段 (polish/emotion_polish/enhance)
- `before_text` - 修改前文本
- `after_text` - 修改后文本
- `changes_detail` - 详细变更记录 (JSON)

## 注意事项

1. **数据库文件**: 
   - 位置: `backend/ai_polish.db`
   - 已添加到 `.gitignore`，不会被提交到版本控制

2. **备份建议**: 
   - 生产环境建议定期备份 `ai_polish.db` 文件
   - 可以使用 SQLite 的备份命令或简单复制文件

3. **迁移升级**:
   - 旧版本数据库会自动升级
   - 新字段会自动添加
   - 已有数据不会丢失

4. **数据库位置配置**:
   - 默认: `sqlite:///./ai_polish.db`
   - 可在 `backend/.env` 中修改 `DATABASE_URL`
   - 支持 PostgreSQL 等其他数据库

## 删除的文件

以下文件已从仓库中移除（不再需要）：
- `backend/ai_polish.db` - 旧的数据库文件
- `backend/test_db.py` - 数据库测试脚本
- `backend/migrations/` - 迁移脚本目录
  - `add_processing_mode.py`
  - `add_emotion_and_processing_mode.py`

## 故障排查

如果遇到数据库问题：

1. **删除数据库重新创建**:
   ```bash
   cd backend
   rm ai_polish.db
   # 重新启动后端服务，数据库会自动创建
   ```

2. **检查数据库结构**:
   ```bash
   cd backend
   python3 -c "from app.database import init_db; init_db()"
   ```

3. **查看数据库内容**:
   ```bash
   cd backend
   sqlite3 ai_polish.db ".tables"
   sqlite3 ai_polish.db ".schema users"
   ```
