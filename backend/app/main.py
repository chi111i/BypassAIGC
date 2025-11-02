from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# 简单的内存速率限制器
class SimpleRateLimiter:
    def __init__(self):
        self.requests: Dict[Tuple[str, str], list] = defaultdict(list)
    
    def check_limit(self, key: str, limit: int, window: int = 60):
        """检查速率限制
        Args:
            key: 客户端标识(IP地址)
            limit: 时间窗口内的最大请求数
            window: 时间窗口(秒)
        """
        now = datetime.now()
        # 清理过期记录
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if now - req_time < timedelta(seconds=window)
        ]
        
        # 检查是否超过限制
        if len(self.requests[key]) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁,请在 {window} 秒后重试"
            )
        
        # 记录本次请求
        self.requests[key].append(now)

rate_limiter = SimpleRateLimiter()

app = FastAPI(
    title="AI 论文润色增强系统",
    description="高质量论文润色与原创性学术表达增强",
    version="1.0.0"
)

# 绑定速率限制器到应用
app.state.rate_limiter = rate_limiter

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应设置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(admin.router)
app.include_router(prompts.router)
app.include_router(optimization.router)

# 速率限制中间件
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """对敏感端点应用速率限制"""
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # 登录接口: 每分钟最多5次
        if request.url.path == "/api/admin/login" and request.method == "POST":
            rate_limiter.check_limit(f"login:{client_ip}", limit=5, window=60)
        
        # 卡密验证接口: 每分钟最多10次
        elif request.url.path == "/api/admin/verify-card-key" and request.method == "POST":
            rate_limiter.check_limit(f"verify:{client_ip}", limit=10, window=60)
    
    except HTTPException as e:
        # 速率限制异常,直接返回
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail}
        )
    
    response = await call_next(request)
    return response


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
