from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./ai_polish.db"
    
    # Redis 配置
    REDIS_URL: str = "redis://IP:6379/0"
    
    # OpenAI API 配置
    OPENAI_API_KEY: str = "pwd"
    OPENAI_BASE_URL: str = "http://IP:PORT/v1"
    
    # 第一阶段模型配置 (论文润色)
    POLISH_MODEL: str = "gpt-5"
    POLISH_API_KEY: Optional[str] = None
    POLISH_BASE_URL: Optional[str] = None
    
    # 第二阶段模型配置 (原创性增强)
    ENHANCE_MODEL: str = "gpt-5"
    ENHANCE_API_KEY: Optional[str] = None
    ENHANCE_BASE_URL: Optional[str] = None
    
    # 并发配置
    MAX_CONCURRENT_USERS: int = 5
    DEFAULT_USAGE_LIMIT: int = 1
    SEGMENT_SKIP_THRESHOLD: int = 15
    
    # 会话压缩配置
    HISTORY_COMPRESSION_THRESHOLD: int = 5000  # 汉字数量阈值
    COMPRESSION_MODEL: str = "gpt-5"
    COMPRESSION_API_KEY: Optional[str] = None
    COMPRESSION_BASE_URL: Optional[str] = None
    
    # JWT 密钥
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 管理员账户
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


def reload_settings():
    """重新加载配置 - 直接更新现有 settings 对象的属性"""
    global settings
    
    # 重新读取 .env 文件到环境变量
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    os.environ[key] = value
                    
                    # 直接更新 settings 对象的属性
                    if hasattr(settings, key):
                        # 获取字段类型并转换
                        field_type = type(getattr(settings, key))
                        try:
                            if field_type == int:
                                setattr(settings, key, int(value))
                            elif field_type == bool:
                                setattr(settings, key, value.lower() in ('true', '1', 'yes'))
                            else:
                                setattr(settings, key, value)
                        except (ValueError, TypeError):
                            setattr(settings, key, value)
    
    return settings
