from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session, defer
from sqlalchemy import func, and_, case
from typing import List
import json
from app.database import get_db
from app.models.models import User, OptimizationSession, OptimizationSegment, ChangeLog
from app.schemas import (
    OptimizationCreate, SessionResponse, SessionDetailResponse,
    QueueStatusResponse, ProgressUpdate, ChangeLogResponse, ExportConfirmation
)
from app.services.optimization_service import OptimizationService
from app.services.concurrency import concurrency_manager
from app.services.stream_manager import stream_manager
from app.utils.auth import generate_session_id
from datetime import datetime
import asyncio
from app.config import settings
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/optimization", tags=["optimization"])


def get_current_user(card_key: str, db: Session = Depends(get_db)) -> User:
    """获取当前用户"""
    user = db.query(User).filter(
        User.card_key == card_key,
        User.is_active == True
    ).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="无效的卡密")
    
    user.last_used = datetime.utcnow()
    db.commit()
    
    return user


async def run_optimization(session_id: int, db: Session):
    """后台运行优化任务"""
    session_obj = db.query(OptimizationSession).filter(
        OptimizationSession.id == session_id
    ).first()
    
    if not session_obj:
        return
    
    service = OptimizationService(db, session_obj)
    await service.start_optimization()


@router.post("/start", response_model=SessionResponse)
async def start_optimization(
    card_key: str,
    data: OptimizationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """开始优化任务"""
    user = get_current_user(card_key, db)

    usage_limit = user.usage_limit if user.usage_limit is not None else settings.DEFAULT_USAGE_LIMIT
    usage_count = user.usage_count or 0
    # 0 表示无限制
    if usage_limit > 0 and usage_count >= usage_limit:
        raise HTTPException(status_code=403, detail="该卡密已达到使用次数限制")
    
    # 验证处理模式
    valid_modes = ['paper_polish', 'paper_polish_enhance', 'emotion_polish']
    if data.processing_mode not in valid_modes:
        raise HTTPException(
            status_code=400, 
            detail=f"无效的处理模式。支持的模式: {', '.join(valid_modes)}"
        )
    
    # 根据处理模式设置初始阶段
    if data.processing_mode == 'emotion_polish':
        initial_stage = 'emotion_polish'
    else:
        initial_stage = 'polish'
    
    # 创建会话
    session_id = generate_session_id()
    session = OptimizationSession(
        user_id=user.id,
        session_id=session_id,
        original_text=data.original_text,
        processing_mode=data.processing_mode,
        current_stage=initial_stage,
        status="queued",
        progress=0.0,
        polish_model=data.polish_config.model if data.polish_config else None,
        polish_api_key=data.polish_config.api_key if data.polish_config else None,
        polish_base_url=data.polish_config.base_url if data.polish_config else None,
        enhance_model=data.enhance_config.model if data.enhance_config else None,
        enhance_api_key=data.enhance_config.api_key if data.enhance_config else None,
        enhance_base_url=data.enhance_config.base_url if data.enhance_config else None,
        emotion_model=data.emotion_config.model if data.emotion_config else None,
        emotion_api_key=data.emotion_config.api_key if data.emotion_config else None,
        emotion_base_url=data.emotion_config.base_url if data.emotion_config else None
    )
    
    db.add(session)
    user.usage_count = usage_count + 1
    db.commit()
    db.refresh(session)
    
    # 添加后台任务
    background_tasks.add_task(run_optimization, session.id, db)
    
    return session


@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status(
    card_key: str,
    session_id: str = None,
    db: Session = Depends(get_db)
):
    """获取队列状态"""
    user = get_current_user(card_key, db)
    
    status = await concurrency_manager.get_status(session_id)
    return QueueStatusResponse(**status)


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    card_key: str,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """列出用户的所有会话（支持分页）"""
    user = get_current_user(card_key, db)
    
    # 限制最大返回数量为100，避免一次性加载过多数据
    limit = min(limit, 100)
    
    # 查询会话及其原始文本长度
    results = db.query(
        OptimizationSession,
        func.length(OptimizationSession.original_text).label('original_char_count')
    ).options(
        defer(OptimizationSession.original_text),
        defer(OptimizationSession.error_message)
    ).filter(
        OptimizationSession.user_id == user.id
    ).order_by(OptimizationSession.created_at.desc()).limit(limit).offset(offset).all()
    
    # 构造响应，手动注入 original_char_count
    sessions = []
    for session, char_count in results:
        session.original_char_count = char_count or 0
        sessions.append(session)
        
    return sessions


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """获取会话详情"""
    user = get_current_user(card_key, db)
    
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 获取段落
    segments = db.query(OptimizationSegment).filter(
        OptimizationSegment.session_id == session.id
    ).order_by(OptimizationSegment.segment_index).all()
    
    return SessionDetailResponse(
        **session.__dict__,
        segments=[seg.__dict__ for seg in segments]
    )


@router.get("/sessions/{session_id}/progress", response_model=ProgressUpdate)
async def get_session_progress(
    session_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """获取会话进度"""
    user = get_current_user(card_key, db)
    
    # 查询完整会话对象，但避免急切加载关联对象
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return ProgressUpdate(
        session_id=session.session_id,
        status=session.status,
        progress=session.progress,
        current_position=session.current_position,
        total_segments=session.total_segments,
        current_stage=session.current_stage,
        error_message=session.error_message
    )


@router.get("/sessions/{session_id}/stream")
async def stream_session_progress(
    session_id: str,
    request: Request,
    card_key: str,  # 简单的鉴权，实际可能需要更严格的检查
    db: Session = Depends(get_db)
):
    """流式获取会话进度和内容"""
    # 验证用户权限
    user = get_current_user(card_key, db)
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    async def event_generator():
        queue = await stream_manager.connect(session_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                # 从队列获取消息，设置超时以便检查连接状态
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    # 发送心跳注释以保持连接活跃
                    yield ": keep-alive\n\n"
                    
        finally:
            await stream_manager.disconnect(session_id, queue)

    return EventSourceResponse(event_generator())


@router.get("/sessions/{session_id}/changes", response_model=List[ChangeLogResponse])
async def get_session_changes(
    session_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """获取会话的变更对照"""
    user = get_current_user(card_key, db)
    
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    latest_log_subquery = db.query(
        ChangeLog.segment_index,
        ChangeLog.stage,
        func.max(ChangeLog.id).label("latest_id")
    ).filter(
        ChangeLog.session_id == session.id
    ).group_by(
        ChangeLog.segment_index,
        ChangeLog.stage
    ).subquery()

    change_logs = db.query(ChangeLog).join(
        latest_log_subquery,
        and_(
            ChangeLog.segment_index == latest_log_subquery.c.segment_index,
            ChangeLog.stage == latest_log_subquery.c.stage,
            ChangeLog.id == latest_log_subquery.c.latest_id
        )
    ).filter(
        ChangeLog.session_id == session.id
    ).order_by(
        ChangeLog.segment_index,
        case((ChangeLog.stage == "polish", 0), else_=1)
    ).all()

    parsed_changes = []
    for change in change_logs:
        detail = None
        if change.changes_detail:
            try:
                detail = json.loads(change.changes_detail)
            except json.JSONDecodeError:
                detail = {"raw": change.changes_detail}

        parsed_changes.append(
            ChangeLogResponse(
                id=change.id,
                segment_index=change.segment_index,
                stage=change.stage,
                before_text=change.before_text,
                after_text=change.after_text,
                changes_detail=detail,
                created_at=change.created_at
            )
        )

    return parsed_changes


@router.post("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    card_key: str,
    confirmation: ExportConfirmation,
    db: Session = Depends(get_db)
):
    """导出优化结果"""
    if not confirmation.acknowledge_academic_integrity:
        raise HTTPException(
            status_code=400,
            detail="必须确认学术诚信承诺"
        )
    
    user = get_current_user(card_key, db)
    
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="会话未完成")
    
    # 获取所有段落
    segments = db.query(OptimizationSegment).filter(
        OptimizationSegment.session_id == session.id
    ).order_by(OptimizationSegment.segment_index).all()
    
    # 组合最终文本
    final_text = "\n\n".join([
        seg.enhanced_text or seg.polished_text or seg.original_text
        for seg in segments
    ])
    
    # 根据格式返回
    if confirmation.export_format == "txt":
        return {
            "format": "txt",
            "content": final_text,
            "filename": f"optimized_{session_id}.txt"
        }
    else:
        # TODO: 实现 docx 和 pdf 导出
        raise HTTPException(status_code=501, detail="暂不支持此格式")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """删除会话"""
    user = get_current_user(card_key, db)
    
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    db.delete(session)
    db.commit()
    
    return {"message": "会话已删除"}


@router.post("/sessions/{session_id}/retry")
async def retry_session(
    session_id: str,
    card_key: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """重新尝试处理失败的会话，继续未完成的段落"""
    user = get_current_user(card_key, db)

    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status not in ["failed", "stopped"]:
        raise HTTPException(status_code=400, detail="仅可对失败或已停止的会话执行重试")

    session.status = "queued"
    session.error_message = None
    db.commit()

    background_tasks.add_task(run_optimization, session.id, db)

    return {"message": "已重新排队处理未完成段落"}


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """停止正在进行中的会话"""
    user = get_current_user(card_key, db)

    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id,
        OptimizationSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.status not in ["queued", "processing"]:
        raise HTTPException(status_code=400, detail="只能停止排队中或处理中的会话")

    # 更新状态为 stopped
    session.status = "stopped"
    session.error_message = "用户手动停止"
    db.commit()

    return {"message": "会话已停止"}
