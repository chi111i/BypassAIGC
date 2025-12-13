from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Tuple, Optional

# 先导入 config 以便加载环境变量
from app.config import settings
from app.database import init_db
from app.routes import admin, prompts, optimization
from app.models.models import CustomPrompt
from app.database import SessionLocal
from app.services.ai_service import get_default_polish_prompt, get_default_enhance_prompt

# 检查默认密钥 - 仅警告，不退出（允许开发环境使用）
if settings.SECRET_KEY == "your-secret-key-change-this-in-production":
    print("\n" + "="*60)
    print("⚠️  安全警告: 检测到默认 SECRET_KEY!")
    print("="*60)
    print("生产环境必须修改 SECRET_KEY,否则 JWT token 可被伪造!")
    print("请在 .env 文件中设置强密钥:")
    print("  python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    print("="*60 + "\n")
    # 仅警告,不强制退出 (开发环境可能需要)

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


async def _check_model_health(model_name: str, model: str, api_key: Optional[str], base_url: Optional[str]) -> dict:
    """检查单个模型的健康状态 - 只验证URL格式，不测试实际连接"""
    import re
    
    try:
        # 检查必需的配置项
        if not model or not model.strip():
            return {
                "status": "unavailable",
                "model": model,
                "base_url": base_url,
                "error": "模型名称未配置"
            }
        
        if not base_url or not base_url.strip():
            return {
                "status": "unavailable",
                "model": model,
                "base_url": base_url,
                "error": "Base URL 未配置"
            }
        
        # 验证 base_url 是否符合 OpenAI API 格式
        # 使用更严格的 URL 验证模式
        url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
        if not url_pattern.match(base_url):
            return {
                "status": "unavailable",
                "model": model,
                "base_url": base_url,
                "error": "Base URL 格式不正确，应为有效的 HTTP/HTTPS URL"
            }
        
        # URL 格式正确，认为配置有效
        return {
            "status": "available",
            "model": model,
            "base_url": base_url
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "model": model,
            "base_url": base_url,
            "error": str(e)
        }


@app.get("/api/health/models")
async def check_models_health():
    """检查 AI 模型可用性"""
    results = {
        "overall_status": "healthy",
        "models": {}
    }
    
    # 检查润色模型
    results["models"]["polish"] = await _check_model_health(
        "polish",
        settings.POLISH_MODEL,
        settings.POLISH_API_KEY,
        settings.POLISH_BASE_URL
    )
    if results["models"]["polish"]["status"] == "unavailable":
        results["overall_status"] = "degraded"
    
    # 检查增强模型
    results["models"]["enhance"] = await _check_model_health(
        "enhance",
        settings.ENHANCE_MODEL,
        settings.ENHANCE_API_KEY,
        settings.ENHANCE_BASE_URL
    )
    if results["models"]["enhance"]["status"] == "unavailable":
        results["overall_status"] = "degraded"
    
    # 检查感情润色模型（如果配置了）
    if settings.EMOTION_MODEL:
        results["models"]["emotion"] = await _check_model_health(
            "emotion",
            settings.EMOTION_MODEL,
            settings.EMOTION_API_KEY,
            settings.EMOTION_BASE_URL
        )
        if results["models"]["emotion"]["status"] == "unavailable":
            results["overall_status"] = "degraded"
    
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
