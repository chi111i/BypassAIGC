#!/usr/bin/env python3
"""
AI 学术写作助手 - 统一入口
将前后端整合为一个可执行文件
"""

import os
import sys
import webbrowser
import threading
import time
import signal

# 获取应用运行目录
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后的 exe 运行
    APP_DIR = os.path.dirname(sys.executable)
    # 静态文件在 exe 内部的 _internal 目录或与 exe 同级目录
    STATIC_DIR = os.path.join(sys._MEIPASS, 'static')
else:
    # 正常 Python 运行
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(APP_DIR, 'static')

# 设置工作目录为应用目录（确保数据库和配置文件在正确位置）
os.chdir(APP_DIR)

# 设置环境变量指向 exe 同目录的 .env 文件
ENV_FILE = os.path.join(APP_DIR, '.env')
DB_FILE = os.path.join(APP_DIR, 'ai_polish.db')

# 加载环境变量
if os.path.exists(ENV_FILE):
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)

# 设置默认数据库路径到 exe 同目录
if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = f"sqlite:///{DB_FILE}"

# 添加 backend 到 Python 路径
backend_path = os.path.join(APP_DIR, 'backend') if not getattr(sys, 'frozen', False) else APP_DIR
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn

# 导入后端应用组件
from app.config import settings
from app.database import init_db
from app.routes import admin, prompts, optimization
from app.models.models import CustomPrompt
from app.database import SessionLocal
from app.services.ai_service import get_default_polish_prompt, get_default_enhance_prompt

# 检查默认密钥（仅警告，不退出）
if settings.SECRET_KEY == "your-secret-key-change-this-in-production":
    print("\n" + "="*60)
    print("⚠️  安全警告: 检测到默认 SECRET_KEY!")
    print("="*60)
    print("生产环境必须修改 SECRET_KEY,否则 JWT token 可被伪造!")
    print(f"请在 {ENV_FILE} 文件中设置强密钥:")
    print("  使用命令生成: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    print("="*60 + "\n")

if settings.ADMIN_PASSWORD == "admin123":
    print("\n" + "="*60)
    print("⚠️  安全警告: 检测到默认管理员密码!")
    print("="*60)
    print("生产环境必须修改 ADMIN_PASSWORD!")
    print(f"请在 {ENV_FILE} 文件中设置强密码 (建议12位以上)")
    print("="*60 + "\n")

# 创建 FastAPI 应用
app = FastAPI(
    title="AI 论文润色增强系统",
    description="高质量论文润色与原创性学术表达增强",
    version="1.0.0"
)

# 添加 Gzip 压缩中间件以减少响应体积
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由（添加 /api 前缀，与 backend/app/main.py 保持一致）
app.include_router(admin.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(optimization.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    print(f"\n📁 应用目录: {APP_DIR}")
    print(f"📁 配置文件: {ENV_FILE}")
    print(f"📁 数据库文件: {DB_FILE}")
    print(f"📁 静态文件目录: {STATIC_DIR}")
    
    # 初始化数据库
    init_db()
    
    # 创建系统默认提示词
    db = SessionLocal()
    try:
        # 检查是否已存在系统提示词
        polish_prompt = db.query(CustomPrompt).filter(
            CustomPrompt.is_system == True,
            CustomPrompt.stage == "polish"
        ).first()
        
        if not polish_prompt:
            polish_prompt = CustomPrompt(
                name="默认润色提示词",
                stage="polish",
                content=get_default_polish_prompt(),
                is_default=True,
                is_system=True
            )
            db.add(polish_prompt)
        
        enhance_prompt = db.query(CustomPrompt).filter(
            CustomPrompt.is_system == True,
            CustomPrompt.stage == "enhance"
        ).first()
        
        if not enhance_prompt:
            enhance_prompt = CustomPrompt(
                name="默认增强提示词",
                stage="enhance",
                content=get_default_enhance_prompt(),
                is_default=True,
                is_system=True
            )
            db.add(enhance_prompt)
        
        db.commit()
    finally:
        db.close()


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# 挂载静态文件（前端构建产物）
if os.path.exists(STATIC_DIR):
    # 挂载 assets 目录（JS, CSS 等）
    assets_dir = os.path.join(STATIC_DIR, 'assets')
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    # 处理根路径和其他前端路由
    @app.get("/")
    async def serve_root():
        """服务根路径"""
        index_file = os.path.join(STATIC_DIR, 'index.html')
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "AI 论文润色增强系统 API", "version": "1.0.0", "docs": "/docs"}
    
    @app.get("/admin")
    @app.get("/admin/{path:path}")
    async def serve_admin(path: str = ""):
        """服务管理后台页面"""
        index_file = os.path.join(STATIC_DIR, 'index.html')
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"error": "Admin page not found"}
    
    @app.get("/workspace")
    @app.get("/workspace/{path:path}")
    async def serve_workspace(path: str = ""):
        """服务工作区页面"""
        index_file = os.path.join(STATIC_DIR, 'index.html')
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"error": "Workspace page not found"}
    
    @app.get("/session/{session_id}")
    async def serve_session(session_id: str):
        """服务会话详情页面"""
        index_file = os.path.join(STATIC_DIR, 'index.html')
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"error": "Session page not found"}
    
    @app.get("/access/{card_key}")
    async def serve_access(card_key: str):
        """服务访问页面"""
        index_file = os.path.join(STATIC_DIR, 'index.html')
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"error": "Access page not found"}
    
    # 处理其他静态文件
    @app.get("/{file_path:path}")
    async def serve_static(file_path: str):
        """服务其他静态文件"""
        # 如果是 API 路径，抛出 404 让 FastAPI 正确处理
        if file_path.startswith('api/') or file_path.startswith('docs') or file_path.startswith('openapi'):
            raise HTTPException(status_code=404, detail="Not found")
        
        full_path = os.path.join(STATIC_DIR, file_path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            return FileResponse(full_path)
        
        # 对于 SPA 路由，返回 index.html
        index_file = os.path.join(STATIC_DIR, 'index.html')
        if os.path.exists(index_file):
            return FileResponse(index_file)
        
        raise HTTPException(status_code=404, detail="File not found")
else:
    @app.get("/")
    async def root():
        """根路径"""
        return {
            "message": "AI 论文润色增强系统 API",
            "version": "1.0.0",
            "docs": "/docs",
            "note": "静态文件目录不存在，仅 API 可用"
        }


def open_browser(port: int):
    """延迟打开浏览器"""
    time.sleep(2)  # 等待服务器启动
    url = f"http://localhost:{port}"
    print(f"\n🌐 正在打开浏览器: {url}")
    webbrowser.open(url)


def create_sample_env():
    """创建示例 .env 文件（如果不存在）"""
    if not os.path.exists(ENV_FILE):
        sample_content = """# AI 学术写作助手配置文件
# 请根据实际情况修改以下配置

# 数据库配置 (SQLite 默认在 exe 同目录)
# DATABASE_URL=sqlite:///./ai_polish.db

# Redis 配置 (用于并发控制和队列)
REDIS_URL=redis://localhost:6379/0

# OpenAI API 配置
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# 第一阶段模型配置 (论文润色) - 推荐使用 gemini-2.5-pro
POLISH_MODEL=gemini-2.5-pro
POLISH_API_KEY=your-api-key-here
POLISH_BASE_URL=https://api.openai.com/v1

# 第二阶段模型配置 (原创性增强) - 推荐使用 gemini-2.5-pro
ENHANCE_MODEL=gemini-2.5-pro
ENHANCE_API_KEY=your-api-key-here
ENHANCE_BASE_URL=https://api.openai.com/v1

# 感情文章润色模型配置 - 推荐使用 gemini-2.5-pro
EMOTION_MODEL=gemini-2.5-pro
EMOTION_API_KEY=your-api-key-here
EMOTION_BASE_URL=https://api.openai.com/v1

# 并发配置
MAX_CONCURRENT_USERS=7

# 会话压缩配置
HISTORY_COMPRESSION_THRESHOLD=2000
COMPRESSION_MODEL=gemini-2.5-pro
COMPRESSION_API_KEY=your-api-key-here
COMPRESSION_BASE_URL=https://api.openai.com/v1

# JWT 密钥 (请修改为随机字符串)
SECRET_KEY=please-change-this-to-a-random-string-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# 管理员账户 (请修改默认密码)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=please-change-this-password
DEFAULT_USAGE_LIMIT=1
SEGMENT_SKIP_THRESHOLD=15
"""
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write(sample_content)
        print(f"✅ 已创建示例配置文件: {ENV_FILE}")
        print("   请编辑此文件，填入您的 API Key 和其他配置")


def main():
    """主入口函数"""
    port = 8000
    host = "127.0.0.1"
    
    print("\n" + "="*60)
    print("🚀 AI 学术写作助手 - 启动中...")
    print("="*60)
    
    # 创建示例配置文件
    create_sample_env()
    
    print(f"\n📍 服务地址: http://{host}:{port}")
    print(f"📍 管理后台: http://{host}:{port}/admin")
    print(f"📍 API 文档: http://{host}:{port}/docs")
    print("\n按 Ctrl+C 停止服务")
    print("="*60 + "\n")
    
    # 在后台线程中打开浏览器
    browser_thread = threading.Thread(target=open_browser, args=(port,))
    browser_thread.daemon = True
    browser_thread.start()
    
    # 启动 uvicorn 服务器
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
        sys.exit(0)


if __name__ == "__main__":
    main()
