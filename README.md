## AI 学术写作助手

专业论文润色与语言优化系统
<img width="2080" height="1361" alt="图片" src="https://github.com/user-attachments/assets/c11abdc9-4bc4-4d61-bea0-13071dba01cd" />

<img width="2103" height="1337" alt="图片" src="https://github.com/user-attachments/assets/523da9c2-899d-4739-932e-84af881a1dfd" />


 ## 效果
 
示例一
<img width="1785" height="654" alt="图片" src="https://github.com/user-attachments/assets/4c96dc66-aa43-432e-90a0-57f7d89dd0f2" />
修改优化后
 <img width="1946" height="672" alt="图片" src="https://github.com/user-attachments/assets/a46f5d62-30ec-4930-b558-18bd24d0e86f" />
例二
<img width="1958" height="662" alt="图片" src="https://github.com/user-attachments/assets/de871360-c045-46ec-8e96-7b3c100af147" />
修改优化后
<img width="1772" height="665" alt="图片" src="https://github.com/user-attachments/assets/3fd2d052-d62e-41fd-8215-fbc375e0d0e5" />
gptzero
<img width="2224" height="547" alt="图片" src="https://github.com/user-attachments/assets/b5daf3cb-6e3f-401c-bdc2-a9a88dcbdb35" />

## 快速开始

无需安装任何开发环境，下载即可使用！

1. 从 [Releases](https://github.com/chi111i/BypassAIGC/releases) 页面下载对应平台的可执行文件：
   - Windows: `AI学术写作助手-Windows-vX.X.X.zip`
   - macOS: `AI学术写作助手-macOS-vX.X.X.tar.gz`
   - Linux: `AI学术写作助手-Linux-vX.X.X.tar.gz`

2. 解压到任意目录

3. 首次运行会自动创建 `.env` 配置文件模板，编辑配置文件填入：
   - API Key（POLISH_API_KEY、ENHANCE_API_KEY 等）
   - 管理员密码（ADMIN_PASSWORD）
   - JWT 密钥（SECRET_KEY）

4. 再次运行程序，将自动打开浏览器

5. 访问管理后台创建卡密

> 💡 提示：数据库文件 `ai_polish.db` 和配置文件 `.env` 都保存在可执行文件同目录，方便备份和迁移。

### 配置文件说明

`.env` 配置文件包含以下重要配置项：

```properties
# 数据库配置
DATABASE_URL=sqlite:///./ai_polish.db
# 或使用 PostgreSQL: postgresql://user:password@IP/ai_polish

# Redis 配置 (用于并发控制和队列)
REDIS_URL=redis://IP:6379/0

# OpenAI API 配置
OPENAI_API_KEY=KEY
OPENAI_BASE_URL=http://IP:PORT/v1

# 第一阶段模型配置 (论文润色) - 推荐使用 gemini-2.5-pro
POLISH_MODEL=gemini-2.5-pro
POLISH_API_KEY=KEY
POLISH_BASE_URL=http://IP:PORT/v1

# 第二阶段模型配置 (原创性增强) - 推荐使用 gemini-2.5-pro
ENHANCE_MODEL=gemini-2.5-pro
ENHANCE_API_KEY=KEY
ENHANCE_BASE_URL=http://IP:PORT/v1

# 感情文章润色模型配置 - 推荐使用 gemini-2.5-pro
EMOTION_MODEL=gemini-2.5-pro
EMOTION_API_KEY=KEY
EMOTION_BASE_URL=http://IP:PORT/v1

# 并发配置
MAX_CONCURRENT_USERS=7

# 会话压缩配置
HISTORY_COMPRESSION_THRESHOLD=2000
COMPRESSION_MODEL=gemini-2.5-pro
COMPRESSION_API_KEY=KEY
COMPRESSION_BASE_URL=http://IP:PORT/v1

# 流式输出配置（推荐保持默认值）
USE_STREAMING=false  # 默认禁用，避免某些API（如Gemini）返回阻止错误

# JWT 密钥
SECRET_KEY=JWT-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# 管理员账户
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
DEFAULT_USAGE_LIMIT=1
SEGMENT_SKIP_THRESHOLD=15
```

**注意:** 
- 推荐使用 Google Gemini 2.5 Pro 模型以获得更好的性能和成本效益
- BASE_URL 使用 OpenAI 兼容格式，需要配置支持 OpenAI API 格式的代理服务
- **流式输出默认禁用**：为避免某些 API（如 Gemini）返回阻止错误，系统默认使用非流式模式。可在管理后台的"系统配置"中切换

### 访问地址

- 用户界面: http://localhost:8000
- 管理后台: http://localhost:8000/admin
- API 文档: http://localhost:8000/docs

## 功能特性

- **双阶段优化**: 论文润色 + 学术增强
- **智能分段**: 自动识别标题，跳过短段落
- **使用限制**: 卡密系统，可配置使用次数
- **并发控制**: 队列管理，动态调整并发数
- **实时配置**: 修改配置无需重启服务
- **数据管理**: 可视化数据库管理界面

## 管理后台

访问 `http://localhost:8000/admin` 使用管理员账户登录

### 功能模块
- 📊 **数据面板**: 用户统计、会话分析
- 👥 **用户管理**: 卡密生成、使用次数控制
- 📡 **会话监控**: 实时会话状态监控
- 💾 **数据库管理**: 查看、编辑、删除数据记录
- ⚙️ **系统配置**: 模型配置、并发设置、使用限制

## 核心配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `MAX_CONCURRENT_USERS` | 最大并发用户数 | 5 |
| `DEFAULT_USAGE_LIMIT` | 新用户默认使用次数 | 1 |
| `SEGMENT_SKIP_THRESHOLD` | 段落跳过阈值（字符数） | 15 |
| `HISTORY_COMPRESSION_THRESHOLD` | 历史压缩阈值 | 5000 |
| `USE_STREAMING` | 启用流式输出模式 | false（推荐）|

## 项目结构

```
AI_GC/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── routes/      # API 路由
│   │   ├── services/    # 业务逻辑
│   │   ├── models/      # 数据模型
│   │   └── utils/       # 工具函数
│   └── .env             # 环境配置
├── frontend/             # React 前端
│   └── src/
│       ├── pages/       # 页面组件
│       └── components/  # 通用组件
└── README.md            # 本文件
```



**⚠️ 重要提示**: 生产环境部署前，请务必:
1. 修改 `.env` 中的默认管理员密码
2. 生成强 SECRET_KEY (至少 32 字节随机字符串)
3. 填写有效的 OPENAI_API_KEY

## 常见问题

**Q: 端口被占用？**  
A: 关闭其他占用 8000 端口的程序

**Q: 配置修改后未生效？**  
A: 重启程序使配置生效

**Q: 登录失败？**  
A: 检查 `.env` 中的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`

**Q: AI 调用失败？**  
A: 检查 API Key 和 Base URL 配置是否正确

**Q: Gemini API 返回 "Your request was blocked" 错误？**  
A: 这是因为 Gemini API 可能阻止流式请求。解决方法：
1. 登录管理后台 (`http://localhost:8000/admin`)
2. 进入"系统配置"标签页
3. 找到"流式输出模式"开关，确保它是**禁用**状态（推荐）
4. 点击"保存配置"按钮
5. 重新运行优化任务

默认配置已经禁用了流式输出，如果仍然遇到此问题，请检查 `.env` 文件中的 `USE_STREAMING` 设置是否为 `false`

## 自行构建可执行文件

如果需要自行构建可执行文件，请参考 [package/README.md](package/README.md)。

### 本地构建

```bash
# Linux/macOS
cd package
chmod +x build.sh
./build.sh

# Windows
cd package
.\build.ps1
```

### GitHub Actions 自动构建

推送以 `v` 开头的标签会自动触发构建：
```bash
git tag v1.0.0
git push origin v1.0.0
```

构建完成后，可在 Releases 页面下载各平台的可执行文件。

## License
未经允许禁止商业使用

Creative Commons (CC BY-NC-SA 4.0)

[![Star History Chart](https://star-history.dera.page/svg?repos=chi111i/BypassAIGC&type=Date)](https://star-history.dera.page/#chi111i/BypassAIGC&type=Date)




























