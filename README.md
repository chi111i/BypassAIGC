# AI 学术写作助手

专业论文润色与语言优化系统
<img width="2178" height="1346" alt="图片" src="https://github.com/user-attachments/assets/98bd2aa2-93b7-405e-8edc-aaec76a19b1e" />
<img width="2353" height="1230" alt="图片" src="https://github.com/user-attachments/assets/d9adc168-0cc4-4a8c-b958-3479d881dd4f" />


 ## 效果
 
朱雀AI检测助手官方示例一
<img width="1785" height="654" alt="图片" src="https://github.com/user-attachments/assets/4c96dc66-aa43-432e-90a0-57f7d89dd0f2" />
修改优化后
 <img width="1946" height="672" alt="图片" src="https://github.com/user-attachments/assets/a46f5d62-30ec-4930-b558-18bd24d0e86f" />
朱雀AI检测助手官方示例二
<img width="1958" height="662" alt="图片" src="https://github.com/user-attachments/assets/de871360-c045-46ec-8e96-7b3c100af147" />
修改优化后
<img width="1772" height="665" alt="图片" src="https://github.com/user-attachments/assets/3fd2d052-d62e-41fd-8215-fbc375e0d0e5" />


## 快速开始

### 1. 首次安装

**Windows 系统:**
```powershell
# 一键配置环境
.\setup.ps1
```

**Ubuntu/Linux 系统:**
```bash
# 添加执行权限
chmod +x setup.sh start-backend.sh start-frontend.sh

# 一键配置环境
./setup.sh
```

### 2. 配置文件
#### 考虑到可能存在非法利用的问题（比如一些营销号恶意使用），微调的提示词不公开,可以在ai_service.py替换,自行修改优化Prompt,本项目内置的Prompt只提供简单的例子。

编辑 `backend/.env`:
```properties
# 数据库配置
DATABASE_URL=sqlite:///./ai_polish.db
# 或使用 PostgreSQL: postgresql://user:password@IP/ai_polish

# Redis 配置 (用于并发控制和队列)
REDIS_URL=redis://IP:6379/0

# OpenAI API 配置
OPENAI_API_KEY=KEY
OPENAI_BASE_URL=http://IP:PORT/v1

# 第一阶段模型配置 (论文润色)
POLISH_MODEL=GPT-5
POLISH_API_KEY=KEY
POLISH_BASE_URL=http://IP:PORT/v1

# 第二阶段模型配置 (原创性增强)
ENHANCE_MODEL=GPT-5
ENHANCE_API_KEY=KEY
ENHANCE_BASE_URL=http://IP:PORT/v1
    # 感情文章润色模型配置
EMOTION_MODEL: Optional[str] = GPT-5
EMOTION_API_KEY: Optional[str] = KEY
EMOTION_BASE_URL: Optional[str] = http://IP:PORT/v1
# 并发配置
MAX_CONCURRENT_USERS=7

# 会话压缩配置
HISTORY_COMPRESSION_THRESHOLD=2000
COMPRESSION_MODEL=GPT-5

# JWT 密钥
SECRET_KEY=JWT-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# 管理员账户
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
DEFAULT_USAGE_LIMIT=1
SEGMENT_SKIP_THRESHOLD=15
COMPRESSION_API_KEY=KEY
COMPRESSION_BASE_URL=http://IP:PORT/v1

```

### 3. 启动服务

**数据库说明**: 数据库会在首次启动后端服务时自动创建，无需手动初始化。

**Windows 系统:**
```powershell
# 一键启动（推荐）
.\start-all.ps1

# 或分别启动
.\start-backend.ps1  # 后端 http://localhost:8000
.\start-frontend.ps1 # 前端 http://localhost:3000
```

**Ubuntu/Linux 系统:**
```bash
# 分别启动（建议使用两个终端）
./start-backend.sh   # 后端 http://localhost:8000
./start-frontend.sh  # 前端 http://localhost:3000

# 或配置 systemd 服务实现开机自启，详见 DEPLOY.md
```

## 功能特性

- **双阶段优化**: 论文润色 + 学术增强
- **智能分段**: 自动识别标题，跳过短段落
- **使用限制**: 卡密系统，可配置使用次数
- **并发控制**: 队列管理，动态调整并发数
- **实时配置**: 修改配置无需重启服务
- **数据管理**: 可视化数据库管理界面

## 管理后台

访问 `http://localhost:3000/admin` 使用管理员账户登录

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
4. 阅读安全审计报告并应用关键修复

## 常见问题

**Q: 端口被占用？**  
A: 修改启动脚本中的端口号，或停止占用进程

**Q: 配置修改后未生效？**  
A: 检查后端日志，配置应自动重载。如仍无效请重启后端

**Q: 登录失败？**  
A: 检查 `.env` 中的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`


**Q: AI 调用失败？**  
A: 检查 API Key 和 Base URL 配置是否正确

## License

MIT License











