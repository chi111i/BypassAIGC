## AI 学术写作助手

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
gptzero
<img width="2224" height="547" alt="图片" src="https://github.com/user-attachments/assets/b5daf3cb-6e3f-401c-bdc2-a9a88dcbdb35" />

## 快速开始

### 使用 Windows 可执行文件 (推荐 Windows 用户)

如果你是 Windows 用户，可以直接下载预编译的可执行文件，无需安装 Python 环境：

1. 从 [Releases](https://github.com/chi111i/BypassAIGC/releases) 页面下载最新的 `BypassAIGC-Backend.exe`
2. 在可执行文件所在目录创建 `.env` 配置文件（参考下面的配置文件部分）
3. 双击运行 `BypassAIGC-Backend.exe` 启动后端服务
4. 按照下面的步骤安装和启动前端

详细的构建说明请参考 [backend/BUILD.md](backend/BUILD.md)

### 1. 使用统一启动脚本

所有系统现已整合为统一的交互式脚本，通过菜单选择所需功能：

**macOS 系统:**
```bash
# 添加执行权限
chmod +x start-macos.sh

# 运行统一脚本
./start-macos.sh
```

**Windows 系统:**
```powershell
# 运行统一脚本（自动检测 PowerShell 7+ 以避免兼容性问题）
.\start.ps1
```

**Ubuntu/Linux 系统:**
```bash
# 添加执行权限
chmod +x start.sh

# 运行统一脚本
./start.sh
```

**菜单功能包括:**
- 1. 环境安装配置
- 2. 启动所有服务
- 3. 仅启动后端服务
- 4. 仅启动前端服务
- 5. 停止所有服务
- 6. 验证安装
- 7. 验证数据库
- 8. 故障排查（Linux/macOS）
- 9. 清理环境（Linux/macOS）

### 2. 配置文件

首次运行统一脚本并选择"环境安装配置"后，会自动生成 `backend/.env` 配置文件模板。

编辑 `backend/.env` 填入你的配置信息:
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

### 3. 使用命令行安装和部署（不使用启动脚本）

如果你不想使用统一启动脚本，也可以直接使用命令行进行安装和部署：

#### Linux/Ubuntu 系统

**步骤 1: 安装后端依赖**
```bash
# 进入后端目录
cd backend

# 创建 Python 虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 返回项目根目录
cd ..
```

**步骤 2: 安装前端依赖**
```bash
# 进入前端目录
cd frontend

# 安装 Node.js 依赖
npm install

# 返回项目根目录
cd ..
```

**步骤 3: 配置环境变量**
```bash
# 创建并编辑 backend/.env 文件
nano backend/.env
# 或使用你喜欢的编辑器（vim, gedit 等）
```

配置文件内容参考"配置文件"部分。

**步骤 4: 启动服务**

启动后端（在一个终端）：
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动前端（在另一个终端）：
```bash
cd frontend
npm run dev
```

#### macOS 系统

**步骤 1: 安装后端依赖**
```bash
# 进入后端目录
cd backend

# 创建 Python 虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 返回项目根目录
cd ..
```

**步骤 2: 安装前端依赖**
```bash
# 进入前端目录
cd frontend

# 安装 Node.js 依赖
npm install

# 返回项目根目录
cd ..
```

**步骤 3: 配置环境变量**
```bash
# 创建并编辑 backend/.env 文件
nano backend/.env
# 或使用其他编辑器
```

配置文件内容参考"配置文件"部分。

**步骤 4: 启动服务**

启动后端（在一个终端）：
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动前端（在另一个终端）：
```bash
cd frontend
npm run dev
```

#### Windows 系统

**步骤 1: 安装后端依赖**
```powershell
# 进入后端目录
cd backend

# 创建 Python 虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1
# 如果遇到执行策略问题，运行: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 安装依赖
pip install -r requirements.txt

# 返回项目根目录
cd ..
```

**步骤 2: 安装前端依赖**
```powershell
# 进入前端目录
cd frontend

# 安装 Node.js 依赖
npm install

# 返回项目根目录
cd ..
```

**步骤 3: 配置环境变量**
```powershell
# 创建并编辑 backend\.env 文件
notepad backend\.env
# 或使用其他编辑器
```

配置文件内容参考"配置文件"部分。

**步骤 4: 启动服务**

启动后端（在一个 PowerShell 窗口）：
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动前端（在另一个 PowerShell 窗口）：
```powershell
cd frontend
npm run dev
```

**访问地址:**
- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 管理后台: http://localhost:3000/admin

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

## 验证和测试

### 验证安装

使用统一脚本菜单选项 6 检查环境配置：

```bash
# Linux/Ubuntu
./start.sh
# 选择选项 6

# macOS
./start-macos.sh
# 选择选项 6

# Windows
.\start.ps1
# 选择选项 6
```

验证功能会检查：
- Python 和 Node.js 版本
- 依赖包安装情况
- 配置文件完整性
- 数据库初始化状态
- 端口占用情况

### 验证数据库

使用统一脚本菜单选项 7 单独验证数据库配置：

```bash
# Linux/Ubuntu
./start.sh
# 选择选项 7

# macOS
./start-macos.sh
# 选择选项 7

# Windows
.\start.ps1
# 选择选项 7
```

## 常见问题

**Q: 端口被占用？**  
A: 使用统一脚本的菜单选项 5 停止所有服务，或修改启动脚本中的端口号

**Q: 配置修改后未生效？**  
A: 检查后端日志，配置应自动重载。如仍无效请使用统一脚本重启后端

**Q: 登录失败？**  
A: 检查 `.env` 中的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`

**Q: 数据库初始化失败？**  
A: 使用统一脚本的菜单选项 7 查看详细错误信息

**Q: AI 调用失败？**  
A: 检查 API Key 和 Base URL 配置是否正确

## License
未经允许禁止商业使用

Creative Commons (CC BY-NC-SA 4.0)

[![Star History Chart](https://api.star-history.com/svg?repos=chi111i/BypassAIGC&type=Date)](https://star-history.com/#chi111i/BypassAIGC)



















