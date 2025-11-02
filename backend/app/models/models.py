from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.config import settings


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    card_key = Column(String(255), unique=True, index=True, nullable=False)
    access_link = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    usage_limit = Column(Integer, default=settings.DEFAULT_USAGE_LIMIT)
    usage_count = Column(Integer, default=0)
    
    # 关系
    sessions = relationship("OptimizationSession", back_populates="user")
    prompts = relationship("CustomPrompt", back_populates="user")


class CustomPrompt(Base):
    """自定义提示词表"""
    __tablename__ = "custom_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    stage = Column(String(50), nullable=False)  # 'polish' 或 'enhance'
    content = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)  # 系统预设提示词
    is_active = Column(Boolean, default=True)  # 是否启用
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="prompts")


class OptimizationSession(Base):
    """优化会话表"""
    __tablename__ = "optimization_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(255), unique=True, index=True)
    original_text = Column(Text)
    current_stage = Column(String(50))  # 'polish' 或 'enhance'
    status = Column(String(50))  # 'queued', 'processing', 'completed', 'failed'
    progress = Column(Float, default=0.0)
    current_position = Column(Integer, default=0)  # 当前处理的段落位置
    total_segments = Column(Integer, default=0)  # 总段落数
    error_message = Column(Text, nullable=True)
    failed_segment_index = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # 模型配置
    polish_model = Column(String(100), nullable=True)
    polish_api_key = Column(String(255), nullable=True)
    polish_base_url = Column(String(255), nullable=True)
    enhance_model = Column(String(100), nullable=True)
    enhance_api_key = Column(String(255), nullable=True)
    enhance_base_url = Column(String(255), nullable=True)
    
    # 关系
    user = relationship("User", back_populates="sessions")
    segments = relationship("OptimizationSegment", back_populates="session", cascade="all, delete-orphan")
    history = relationship("SessionHistory", back_populates="session", cascade="all, delete-orphan")

    @property
    def completed_segments(self) -> int:
        """Return how many segments finished successfully."""
        return sum(1 for segment in self.segments if segment.status == "completed")


class OptimizationSegment(Base):
    """优化段落表"""
    __tablename__ = "optimization_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id"))
    segment_index = Column(Integer)  # 段落序号
    stage = Column(String(50))  # 'polish' 或 'enhance'
    original_text = Column(Text)
    polished_text = Column(Text, nullable=True)
    enhanced_text = Column(Text, nullable=True)
    status = Column(String(50))  # 'pending', 'processing', 'completed', 'failed'
    is_title = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    session = relationship("OptimizationSession", back_populates="segments")


class SessionHistory(Base):
    """会话历史表 (用于AI上下文)"""
    __tablename__ = "session_history"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id"))
    stage = Column(String(50))  # 'polish' 或 'enhance'
    history_data = Column(Text)  # JSON格式的历史会话
    is_compressed = Column(Boolean, default=False)
    character_count = Column(Integer, default=0)  # 汉字数量
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    session = relationship("OptimizationSession", back_populates="history")


class ChangeLog(Base):
    """变更对照记录表 (用于学术审计)"""
    __tablename__ = "change_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("optimization_sessions.id"))
    segment_index = Column(Integer)
    stage = Column(String(50))  # 'polish' 或 'enhance'
    before_text = Column(Text)
    after_text = Column(Text)
    changes_detail = Column(Text)  # JSON格式的详细变更
    created_at = Column(DateTime, default=datetime.utcnow)


class QueueStatus(Base):
    """队列状态表"""
    __tablename__ = "queue_status"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    position = Column(Integer)  # 队列位置
    status = Column(String(50))  # 'queued' 或 'processing'
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)


class SystemSetting(Base):
    """系统设置表"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
