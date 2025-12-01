from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Tuple

# 先导入 config 以便加载环境变量
from app.config import settings
from app.database import init_db
from app.routes import admin, prompts, optimization
from app.models.models import CustomPrompt
from app.database import SessionLocal
from app.services.ai_service import get_default_polish_prompt, get_default_enhance_prompt

# 检查默认密钥
if settings.SECRET_KEY == "your-secret-key-change-this-in-production":
    print("\n" + "="*60)
    print("⚠️  安全警告: 检测到默认 SECRET_KEY!")
    print("="*60)
    print("生产环境必须修改 SECRET_KEY,否则 JWT token 可被伪造!")
    print("请在 .env 文件中设置强密钥:")
    print("  python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    print("="*60 + "\n")
    sys.exit(1)

if settings.ADMIN_PASSWORD == "admin123":
    print("\n" + "="*60)
    print("⚠️  安全警告: 检测到默认管理员密码!")
    print("="*60)
    print("生产环境必须修改 ADMIN_PASSWORD!")
    print("请在 .env 文件中设置强密码 (建议12位以上)")
    print("="*60 + "\n")
    # 仅警告,不强制退出 (开发环境可能需要)

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
    allow_origins=["*"],  # 生产环境应设置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（添加 /api 前缀，与 backend/app/main.py 保持一致）
app.include_router(admin.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(optimization.router, prefix="/api")

# 速率限制中间件已移除


@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
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


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "AI 论文润色增强系统 API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
