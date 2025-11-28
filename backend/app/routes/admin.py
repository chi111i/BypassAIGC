import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type

from fastapi import APIRouter, Depends, Header, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy import inspect, func, case
from sqlalchemy.orm import Session, defer, joinedload

from app.config import reload_settings, settings
from app.database import get_db
from app.models.models import (
    ChangeLog,
    OptimizationSegment,
    OptimizationSession,
    SessionHistory,
    SystemSetting,
    User,
)
from app.schemas import (
    CardKeyGenerate,
    CardKeyResponse,
    DatabaseUpdateRequest,
    UserResponse,
    UserUsageUpdate,
)
from app.services.concurrency import concurrency_manager
from app.utils.auth import (
    create_access_token,
    generate_access_link,
    generate_card_key,
    verify_token,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminLogin(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class CardKeyCreate(BaseModel):
    card_key: Optional[str] = None
    usage_limit: Optional[int] = None


class CardKeyVerify(BaseModel):
    card_key: str


ALLOWED_TABLES: Dict[str, Type] = {
    "users": User,
    "optimization_sessions": OptimizationSession,
    "optimization_segments": OptimizationSegment,
    "session_history": SessionHistory,
    "change_logs": ChangeLog,
    "system_settings": SystemSetting,
}


def verify_admin_credentials(username: str, password: str) -> bool:
    return username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD


def verify_admin_token(token: str) -> bool:
    payload = verify_token(token)
    if not payload:
        return False
    return payload.get("sub") == settings.ADMIN_USERNAME and payload.get("role") == "admin"


def get_admin_from_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证令牌")

    token = authorization.split(" ")[1]
    if not verify_admin_token(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")
    return token


def _model_to_dict(record: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    mapper = inspect(record).mapper
    for column in mapper.columns:
        data[column.key] = getattr(record, column.key)
    return data


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(credentials: AdminLogin) -> AdminLoginResponse:
    # 速率限制: 每分钟最多5次登录尝试 (在 main.py 的 limiter 中配置)
    if not verify_admin_credentials(credentials.username, credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": credentials.username, "role": "admin"},
        expires_delta=access_token_expires,
    )
    return AdminLoginResponse(access_token=access_token, username=credentials.username)


@router.post("/verify-token")
async def verify_admin_token_endpoint(authorization: Optional[str] = Header(None)) -> Dict[str, bool]:
    get_admin_from_token(authorization)
    return {"valid": True}


@router.post("/verify-card-key")
async def verify_card_key(data: CardKeyVerify, db: Session = Depends(get_db)) -> Dict[str, Any]:
    # 速率限制: 每分钟最多10次卡密验证 (在 main.py 的 limiter 中配置)
    user = db.query(User).filter(User.card_key == data.card_key, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的卡密或卡密已被禁用")

    user.last_used = datetime.utcnow()
    db.commit()
    return {"valid": True, "user_id": user.id, "created_at": user.created_at}


@router.post("/card-keys")
async def create_card_key(
    data: CardKeyCreate,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    card_key = data.card_key or generate_card_key()
    existing_user = db.query(User).filter(User.card_key == card_key).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该卡密已存在")

    usage_limit = data.usage_limit or settings.DEFAULT_USAGE_LIMIT
    access_link = generate_access_link(card_key)
    user = User(
        card_key=card_key,
        access_link=access_link,
        is_active=True,
        usage_limit=usage_limit,
        usage_count=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "card_key": user.card_key,
        "access_link": user.access_link,
        "usage_limit": user.usage_limit,
        "created_at": user.created_at,
    }


@router.post("/batch-generate-keys")
async def batch_generate_keys(
    count: int,
    prefix: str = "",
    usage_limit: Optional[int] = None,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if count <= 0 or count > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="批量生成数量必须在 1-100 之间")

    limit = usage_limit or settings.DEFAULT_USAGE_LIMIT
    results: List[Dict[str, Any]] = []
    for _ in range(count):
        card_key = generate_card_key(prefix=prefix)
        access_link = generate_access_link(card_key)
        user = User(card_key=card_key, access_link=access_link, is_active=True, usage_limit=limit, usage_count=0)
        db.add(user)
        db.commit()
        db.refresh(user)
        results.append(
            {
                "card_key": card_key,
                "access_link": access_link,
                "usage_limit": user.usage_limit,
                "created_at": user.created_at,
            }
        )
    return {"count": len(results), "keys": results}


@router.get("/users", response_model=List[UserResponse])
async def get_all_users(_: str = Depends(get_admin_from_token), db: Session = Depends(get_db)) -> List[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}/toggle")
async def toggle_user_status(
    user_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "card_key": user.card_key,
        "is_active": user.is_active,
        "message": f"用户已{'启用' if user.is_active else '禁用'}",
    }


@router.patch("/users/{user_id}/usage")
async def update_user_usage(
    user_id: int,
    payload: UserUsageUpdate,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.usage_limit = payload.usage_limit
    if payload.reset_usage_count:
        user.usage_count = 0
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "usage_limit": user.usage_limit,
        "usage_count": user.usage_count,
        "message": "使用限制已更新",
    }


@router.post("/sessions/{session_id}/stop")
async def admin_stop_session(
    session_id: str,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """管理员停止会话"""
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
        
    if session.status not in ["queued", "processing"]:
        raise HTTPException(status_code=400, detail="只能停止排队中或处理中的会话")
        
    session.status = "stopped"
    session.error_message = "管理员手动停止"
    db.commit()
    
    return {"message": "会话已停止"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    return {"message": "用户已删除", "card_key": user.card_key}


@router.get("/statistics")
async def get_statistics(_: str = Depends(get_admin_from_token), db: Session = Depends(get_db)) -> Dict[str, Any]:
    total_users = db.query(User).count() or 0
    active_users = db.query(User).filter(User.is_active.is_(True)).count() or 0
    inactive_users = total_users - active_users
    used_users = db.query(User).filter(User.last_used.isnot(None)).count() or 0

    total_sessions = db.query(OptimizationSession).count() or 0
    completed_sessions = db.query(OptimizationSession).filter(OptimizationSession.status == "completed").count() or 0
    processing_sessions = db.query(OptimizationSession).filter(OptimizationSession.status == "processing").count() or 0
    queued_sessions = db.query(OptimizationSession).filter(OptimizationSession.status == "queued").count() or 0
    failed_sessions = db.query(OptimizationSession).filter(OptimizationSession.status == "failed").count() or 0

    total_segments = db.query(OptimizationSegment).count() or 0
    completed_segments = db.query(OptimizationSegment).filter(OptimizationSegment.status == "completed").count() or 0

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_active_users = db.query(User).filter(User.last_used >= seven_days_ago).count() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new_users = db.query(User).filter(User.created_at >= today_start).count() or 0
    today_active_users = db.query(User).filter(User.last_used >= today_start).count() or 0
    today_sessions = db.query(OptimizationSession).filter(OptimizationSession.created_at >= today_start).count() or 0
    
    # 统计文本处理字数
    all_sessions = db.query(OptimizationSession).filter(
        OptimizationSession.status == "completed"
    ).all()
    
    total_original_chars = sum(len(s.original_text) for s in all_sessions if s.original_text)
    
    # 统计各处理模式的使用量
    paper_polish_count = db.query(OptimizationSession).filter(
        OptimizationSession.processing_mode == "paper_polish"
    ).count() or 0
    
    paper_polish_enhance_count = db.query(OptimizationSession).filter(
        OptimizationSession.processing_mode == "paper_polish_enhance"
    ).count() or 0
    
    emotion_polish_count = db.query(OptimizationSession).filter(
        OptimizationSession.processing_mode == "emotion_polish"
    ).count() or 0
    
    # 统计平均处理时间
    completed_with_time = db.query(OptimizationSession).filter(
        OptimizationSession.status == "completed",
        OptimizationSession.completed_at.isnot(None),
        OptimizationSession.created_at.isnot(None)
    ).all()
    
    avg_processing_time = 0
    if completed_with_time:
        total_time = sum(
            (s.completed_at - s.created_at).total_seconds() 
            for s in completed_with_time
        )
        avg_processing_time = total_time / len(completed_with_time)

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": inactive_users,
            "used": used_users,
            "unused": total_users - used_users,
            "today_new": today_new_users,
            "today_active": today_active_users,
            "recent_active_7days": recent_active_users,
        },
        "sessions": {
            "total": total_sessions,
            "completed": completed_sessions,
            "processing": processing_sessions,
            "queued": queued_sessions,
            "failed": failed_sessions,
            "today": today_sessions,
        },
        "segments": {
            "total": total_segments,
            "completed": completed_segments,
            "pending": total_segments - completed_segments,
        },
        "processing": {
            "total_chars_processed": total_original_chars,
            "avg_processing_time": round(avg_processing_time, 2),
            "paper_polish_count": paper_polish_count,
            "paper_polish_enhance_count": paper_polish_enhance_count,
            "emotion_polish_count": emotion_polish_count,
        },
    }


@router.get("/users/{user_id}/details")
async def get_user_details(
    user_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user_sessions = db.query(OptimizationSession).filter(OptimizationSession.user_id == user_id).all()
    total_sessions = len(user_sessions)
    completed_sessions = sum(1 for session in user_sessions if session.status == "completed")

    session_ids = [session.id for session in user_sessions]
    total_segments = 0
    completed_segments = 0
    if session_ids:
        total_segments = db.query(OptimizationSegment).filter(OptimizationSegment.session_id.in_(session_ids)).count()
        completed_segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id.in_(session_ids), OptimizationSegment.status == "completed")
            .count()
        )

    recent_sessions = (
        db.query(OptimizationSession)
        .filter(OptimizationSession.user_id == user_id)
        .order_by(OptimizationSession.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "user": {
            "id": user.id,
            "card_key": user.card_key,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "last_used": user.last_used,
            "usage_limit": user.usage_limit,
            "usage_count": user.usage_count,
        },
        "statistics": {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "processing_sessions": total_sessions - completed_sessions,
            "total_segments": total_segments,
            "completed_segments": completed_segments,
        },
        "recent_sessions": [
            {
                "id": session.id,
                "status": session.status,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            }
            for session in recent_sessions
        ],
    }


@router.post("/generate-keys", response_model=List[CardKeyResponse])
async def generate_keys(
    data: CardKeyGenerate,
    admin_password: str,
    db: Session = Depends(get_db),
) -> List[CardKeyResponse]:
    if not verify_admin_credentials(settings.ADMIN_USERNAME, admin_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员密码错误")

    results: List[CardKeyResponse] = []
    for _ in range(data.count):
        card_key = generate_card_key(prefix=data.prefix or "")
        access_link = generate_access_link(card_key)
        user = User(
            card_key=card_key,
            access_link=access_link,
            is_active=True,
            usage_limit=settings.DEFAULT_USAGE_LIMIT,
            usage_count=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        results.append(
            CardKeyResponse(
                card_key=card_key,
                access_link=access_link,
                created_at=user.created_at,
            )
        )

    return results


@router.get("/sessions")
async def get_all_sessions(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
    limit: int = 100,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """获取所有会话历史"""
    query = db.query(OptimizationSession).options(
        joinedload(OptimizationSession.user),
        defer(OptimizationSession.original_text),
        defer(OptimizationSession.error_message)
    ).order_by(OptimizationSession.created_at.desc())
    
    if status:
        query = query.filter(OptimizationSession.status == status)
    
    sessions = query.limit(limit).all()
    
    if not sessions:
        return []

    # 批量获取段落统计信息
    session_ids = [s.id for s in sessions]
    # 批量获取会话的原始文本长度
    original_lengths = db.query(
        OptimizationSession.id,
        func.length(OptimizationSession.original_text).label('length')
    ).filter(
        OptimizationSession.id.in_(session_ids)
    ).all()
    
    original_length_map = {item.id: (item.length or 0) for item in original_lengths}

    stats_query = db.query(
        OptimizationSegment.session_id,
        func.count(OptimizationSegment.id).label('total'),
        func.sum(case((OptimizationSegment.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(func.length(func.coalesce(OptimizationSegment.polished_text, ''))).label('polished_chars'),
        func.sum(func.length(func.coalesce(OptimizationSegment.enhanced_text, ''))).label('enhanced_chars')
    ).filter(
        OptimizationSegment.session_id.in_(session_ids)
    ).group_by(OptimizationSegment.session_id).all()
    
    stats_map = {
        stat.session_id: {
            'total': stat.total,
            'completed': stat.completed,
            'polished_chars': stat.polished_chars or 0,
            'enhanced_chars': stat.enhanced_chars or 0
        }
        for stat in stats_query
    }
    
    result = []
    for session in sessions:
        # 计算处理时间
        processing_time = None
        if session.completed_at and session.created_at:
            processing_time = (session.completed_at - session.created_at).total_seconds()
        elif session.status == 'processing' and session.created_at:
            processing_time = (datetime.utcnow() - session.created_at).total_seconds()
        
        # 获取统计信息
        stats = stats_map.get(session.id, {
            'total': 0, 'completed': 0, 'polished_chars': 0, 'enhanced_chars': 0
        })
        
        result.append({
            "session_id": session.id,
            "user_id": session.user_id,
            "card_key": session.user.card_key if session.user else None,
            "status": session.status,
            "processing_mode": session.processing_mode,
            "original_char_count": original_length_map.get(session.id, 0),
            "polished_char_count": int(stats['polished_chars']),
            "enhanced_char_count": int(stats['enhanced_chars']),
            "total_segments": stats['total'],
            "completed_segments": stats['completed'],
            "progress": round((stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0, 1),
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "processing_time": processing_time,
            "error_message": None, # 列表页不返回详细错误信息
        })
    
    return result


@router.get("/sessions/active")
async def get_active_sessions(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """获取所有活跃会话（处理中和排队中）"""
    active_sessions = db.query(OptimizationSession).filter(
        OptimizationSession.status.in_(["processing", "queued"])
    ).order_by(OptimizationSession.created_at.desc()).all()
    
    result = []
    for session in active_sessions:
        # 获取用户信息
        user = db.query(User).filter(User.id == session.user_id).first()
        
        # 计算已处理段落数
        completed_segments = db.query(OptimizationSegment).filter(
            OptimizationSegment.session_id == session.id,
            OptimizationSegment.status == "completed"
        ).count()
        
        # 计算处理时间
        processing_time = None
        if session.status == "processing" and session.created_at:
            processing_time = (datetime.utcnow() - session.created_at).total_seconds()
        
        # 统计文本字数
        original_char_count = len(session.original_text) if session.original_text else 0
        
        result.append({
            "id": session.id,
            "session_id": session.session_id,
            "user_id": session.user_id,
            "card_key": user.card_key if user else "未知",
            "status": session.status,
            "progress": session.progress,
            "current_stage": session.current_stage,
            "current_position": session.current_position,
            "total_segments": session.total_segments,
            "processed_segments": completed_segments,
            "original_text": session.original_text[:200] if session.original_text else "",
            "original_char_count": original_char_count,
            "processing_mode": session.processing_mode,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "processing_time": processing_time,
            "error_message": session.error_message
        })
    
    return result


@router.get("/users/{user_id}/sessions")
async def get_user_sessions(
    user_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """获取指定用户的所有会话历史"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    sessions = db.query(OptimizationSession).options(
        defer(OptimizationSession.original_text),
        defer(OptimizationSession.error_message)
    ).filter(
        OptimizationSession.user_id == user_id
    ).order_by(OptimizationSession.created_at.desc()).limit(50).all()
    
    if not sessions:
        return []

    session_ids = [s.id for s in sessions]
    
    # 批量获取会话的原始文本长度和预览
    original_info = db.query(
        OptimizationSession.id,
        func.length(OptimizationSession.original_text).label('length'),
        func.substring(OptimizationSession.original_text, 1, 100).label('preview')
    ).filter(
        OptimizationSession.id.in_(session_ids)
    ).all()
    
    original_info_map = {
        item.id: {'length': item.length or 0, 'preview': item.preview or ""}
        for item in original_info
    }

    stats_query = db.query(
        OptimizationSegment.session_id,
        func.count(OptimizationSegment.id).label('total'),
        func.sum(case((OptimizationSegment.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(func.length(func.coalesce(OptimizationSegment.polished_text, ''))).label('polished_chars'),
        func.sum(func.length(func.coalesce(OptimizationSegment.enhanced_text, ''))).label('enhanced_chars')
    ).filter(
        OptimizationSegment.session_id.in_(session_ids)
    ).group_by(OptimizationSegment.session_id).all()
    
    stats_map = {
        stat.session_id: {
            'total': stat.total,
            'completed': stat.completed,
            'polished_chars': stat.polished_chars or 0,
            'enhanced_chars': stat.enhanced_chars or 0
        }
        for stat in stats_query
    }
    
    result = []
    for session in sessions:
        # 计算处理时间
        processing_time = None
        if session.completed_at and session.created_at:
            processing_time = (session.completed_at - session.created_at).total_seconds()
        elif session.status == "processing" and session.created_at:
            processing_time = (datetime.utcnow() - session.created_at).total_seconds()
        
        stats = stats_map.get(session.id, {
            'total': 0, 'completed': 0, 'polished_chars': 0, 'enhanced_chars': 0
        })
        
        orig_info = original_info_map.get(session.id, {'length': 0, 'preview': ""})

        result.append({
            "id": session.id,
            "session_id": session.session_id,
            "status": session.status,
            "processing_mode": session.processing_mode,
            "original_text": orig_info['preview'],
            "original_char_count": orig_info['length'],
            "polished_char_count": int(stats['polished_chars']),
            "enhanced_char_count": int(stats['enhanced_chars']),
            "total_segments": stats['total'],
            "completed_segments": stats['completed'],
            "progress": session.progress,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "processing_time": processing_time,
            "error_message": None # 列表页不返回详细错误信息
        })
    
    return result


@router.get("/config")
async def get_config(_: str = Depends(get_admin_from_token)) -> Dict[str, Any]:
    return {
        "polish": {
            "model": settings.POLISH_MODEL,
            "api_key": settings.POLISH_API_KEY or "",
            "base_url": settings.POLISH_BASE_URL or "",
        },
        "enhance": {
            "model": settings.ENHANCE_MODEL,
            "api_key": settings.ENHANCE_API_KEY or "",
            "base_url": settings.ENHANCE_BASE_URL or "",
        },
        "emotion": {
            "model": getattr(settings, 'EMOTION_MODEL', settings.POLISH_MODEL),
            "api_key": getattr(settings, 'EMOTION_API_KEY', settings.POLISH_API_KEY) or "",
            "base_url": getattr(settings, 'EMOTION_BASE_URL', settings.POLISH_BASE_URL) or "",
        },
        "compression": {
            "model": settings.COMPRESSION_MODEL,
            "api_key": settings.COMPRESSION_API_KEY or "",
            "base_url": settings.COMPRESSION_BASE_URL or "",
        },
        "system": {
            "max_concurrent_users": settings.MAX_CONCURRENT_USERS,
            "history_compression_threshold": settings.HISTORY_COMPRESSION_THRESHOLD,
            "default_usage_limit": settings.DEFAULT_USAGE_LIMIT,
            "segment_skip_threshold": settings.SEGMENT_SKIP_THRESHOLD,
        },
    }


@router.post("/config")
async def update_config(
    updates: Dict[str, str],
    _: str = Depends(get_admin_from_token),
) -> Dict[str, Any]:
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少更新内容")

    current_file = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
    env_path = os.path.join(backend_dir, ".env")

    if not os.path.exists(env_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f".env 文件不存在: {env_path}")

    with open(env_path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    updated_keys = set()
    new_lines: List[str] = []
    for line in lines:
        stripped = line.rstrip("\n")
        if "=" in stripped and not stripped.strip().startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as handle:
        handle.writelines(new_lines)

    reload_settings()

    if "MAX_CONCURRENT_USERS" in updates:
        try:
            await concurrency_manager.update_limit(int(updates["MAX_CONCURRENT_USERS"]))
        except ValueError:
            pass

    return {"message": "配置已更新并保存", "updated_keys": list(updates.keys())}


@router.get("/database/tables")
async def list_tables(_: str = Depends(get_admin_from_token)) -> Dict[str, List[str]]:
    return {"tables": list(ALLOWED_TABLES.keys())}


@router.get("/database/{table_name}")
async def fetch_table_records(
    table_name: str,
    skip: int = 0,
    limit: int = 50,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="表不存在或不允许访问")

    model = ALLOWED_TABLES[table_name]
    page_size = max(min(limit, 200), 1)
    query = db.query(model).offset(max(skip, 0)).limit(page_size)
    records = [_model_to_dict(row) for row in query.all()]
    total = db.query(model).count()
    return {"total": total, "items": records}


@router.put("/database/{table_name}/{record_id}")
async def update_table_record(
    table_name: str,
    record_id: int,
    payload: DatabaseUpdateRequest,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="表不存在或不允许访问")

    model = ALLOWED_TABLES[table_name]
    record = db.query(model).filter(getattr(model, "id") == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    mapper = inspect(model)
    allowed_columns = {column.key for column in mapper.columns if not column.primary_key}

    for key, value in payload.data.items():
        if key in allowed_columns:
            setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return {"message": "记录已更新", "record": _model_to_dict(record)}


@router.delete("/database/{table_name}/{record_id}")
async def delete_table_record(
    table_name: str,
    record_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="表不存在或不允许访问")

    model = ALLOWED_TABLES[table_name]
    record = db.query(model).filter(getattr(model, "id") == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    db.delete(record)
    db.commit()
    return {"message": "记录已删除"}
