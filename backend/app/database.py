from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """数据库会话依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库"""
    # 导入所有模型以确保它们被注册到 Base.metadata
    from app.models import models  # noqa: F401
    
    Base.metadata.create_all(bind=engine)
    # 确保新增列在旧数据表中可用
    with engine.connect() as conn:
        inspector = inspect(conn)
        columns = {column["name"] for column in inspector.get_columns("optimization_sessions")}
        if "failed_segment_index" not in columns:
            conn.execute(text("ALTER TABLE optimization_sessions ADD COLUMN failed_segment_index INTEGER"))
            conn.commit()

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "usage_limit" not in user_columns:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN usage_limit INTEGER DEFAULT {settings.DEFAULT_USAGE_LIMIT}"))
        if "usage_count" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN usage_count INTEGER DEFAULT 0"))
        conn.execute(text(f"UPDATE users SET usage_limit = {settings.DEFAULT_USAGE_LIMIT} WHERE usage_limit IS NULL"))
        conn.execute(text("UPDATE users SET usage_count = 0 WHERE usage_count IS NULL"))

        segment_columns = {column["name"] for column in inspector.get_columns("optimization_segments")}
        if "is_title" not in segment_columns:
            conn.execute(text("ALTER TABLE optimization_segments ADD COLUMN is_title BOOLEAN DEFAULT 0"))
        conn.commit()
