"""
Word Formatter API Routes

Provides endpoints for document formatting with AI-assisted recognition.
Authentication uses card_key, usage counts shared with polishing service.
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.database import get_db
from app.models.models import User
from app.services.ai_service import AIService

from .services import (
    CompileOptions,
    CompilePhase,
    InputFormat,
    Job,
    JobStatus,
    ai_generate_spec,
    builtin_specs,
    compile_document,
    compile_document_with_ai,
    detect_input_format,
    export_spec_to_json,
    get_job_manager,
    get_spec_schema,
    validate_custom_spec,
)
from .utils.docx_text import extract_text_from_docx


router = APIRouter(prefix="/word-formatter", tags=["word-formatter"])


# Request/Response Models
class FormatRequest(BaseModel):
    """Request for document formatting."""
    text: Optional[str] = None
    input_format: str = "auto"
    spec_name: Optional[str] = None
    custom_spec_json: Optional[str] = None
    include_cover: bool = True
    include_toc: bool = True
    toc_title: str = "目 录"
    use_ai_recognition: bool = False


class FormatFileRequest(BaseModel):
    """Request for file upload formatting."""
    input_format: str = "auto"
    spec_name: Optional[str] = None
    custom_spec_json: Optional[str] = None
    include_cover: bool = True
    include_toc: bool = True
    toc_title: str = "目 录"
    use_ai_recognition: bool = False


class GenerateSpecRequest(BaseModel):
    """Request to generate spec from requirements."""
    requirements: str = Field(..., min_length=10, description="User's formatting requirements")


class JobResponse(BaseModel):
    """Response for job creation."""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status."""
    job_id: str
    status: str
    progress: Optional[float] = None
    phase: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    output_filename: Optional[str] = None


class SpecListResponse(BaseModel):
    """Response for listing specs."""
    specs: List[str]


class SpecSchemaResponse(BaseModel):
    """Response for spec schema."""
    schema: dict


class UsageInfoResponse(BaseModel):
    """Response for user usage info."""
    usage_count: int
    usage_limit: int
    remaining: int


def get_current_user(card_key: str, db: Session = Depends(get_db)) -> User:
    """Get current user by card_key."""
    user = db.query(User).filter(
        User.card_key == card_key,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="无效的卡密")

    user.last_used = datetime.utcnow()
    db.commit()

    return user


def check_usage_limit(user: User) -> None:
    """Check if user has remaining usage quota (shared with polishing)."""
    usage_limit = user.usage_limit if user.usage_limit is not None else settings.DEFAULT_USAGE_LIMIT
    usage_count = user.usage_count or 0

    # 0 means unlimited
    if usage_limit > 0 and usage_count >= usage_limit:
        raise HTTPException(status_code=403, detail="该卡密已达到使用次数限制")


def increment_usage(user: User, db: Session) -> None:
    """Increment user's usage count (shared with polishing)."""
    user.usage_count = (user.usage_count or 0) + 1
    db.commit()


def get_ai_service() -> AIService:
    """Get AI service instance for word formatting."""
    return AIService(
        model=settings.POLISH_MODEL,
        api_key=settings.POLISH_API_KEY,
        base_url=settings.POLISH_BASE_URL,
    )


@router.get("/usage", response_model=UsageInfoResponse)
async def get_usage_info(
    card_key: str,
    db: Session = Depends(get_db)
):
    """Get user's usage information (shared with polishing)."""
    user = get_current_user(card_key, db)

    usage_limit = user.usage_limit if user.usage_limit is not None else settings.DEFAULT_USAGE_LIMIT
    usage_count = user.usage_count or 0
    remaining = max(0, usage_limit - usage_count) if usage_limit > 0 else -1

    return UsageInfoResponse(
        usage_count=usage_count,
        usage_limit=usage_limit,
        remaining=remaining,
    )


@router.get("/specs", response_model=SpecListResponse)
async def list_specs():
    """List available built-in formatting specs."""
    return SpecListResponse(specs=list(builtin_specs().keys()))


@router.get("/specs/schema", response_model=SpecSchemaResponse)
async def get_schema():
    """Get JSON schema for custom spec validation."""
    return SpecSchemaResponse(schema=get_spec_schema())


@router.post("/specs/validate")
async def validate_spec(spec_json: str):
    """Validate a custom spec JSON."""
    try:
        spec = validate_custom_spec(spec_json)
        return {"valid": True, "spec_name": spec.meta.get("name", "Custom")}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/specs/generate")
async def generate_spec(
    card_key: str,
    request: GenerateSpecRequest,
    db: Session = Depends(get_db)
):
    """Generate a formatting spec from user requirements using AI."""
    user = get_current_user(card_key, db)
    check_usage_limit(user)

    try:
        ai_service = get_ai_service()
        spec = await ai_generate_spec(request.requirements, ai_service)

        increment_usage(user, db)

        return {
            "success": True,
            "spec_json": export_spec_to_json(spec),
            "spec_name": spec.meta.get("name", "AI_Generated"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成规范失败: {str(e)}")


@router.post("/format/text", response_model=JobResponse)
async def format_text(
    card_key: str,
    request: FormatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Format text document and return job ID."""
    user = get_current_user(card_key, db)
    check_usage_limit(user)

    if not request.text:
        raise HTTPException(status_code=400, detail="文本内容不能为空")

    # Parse input format
    try:
        input_format = InputFormat(request.input_format)
    except ValueError:
        input_format = InputFormat.AUTO

    # Parse custom spec if provided
    custom_spec = None
    if request.custom_spec_json:
        try:
            custom_spec = validate_custom_spec(request.custom_spec_json)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"自定义规范无效: {e}")

    # Create compile options
    options = CompileOptions(
        input_format=input_format,
        spec_name=request.spec_name,
        custom_spec=custom_spec,
        include_cover=request.include_cover,
        include_toc=request.include_toc,
        toc_title=request.toc_title,
    )

    # Create job
    job_manager = get_job_manager()
    job = job_manager.create_job(
        user_id=str(user.id),
        input_text=request.text,
        options=options,
    )

    # Run job in background
    async def run_job():
        ai_service = get_ai_service() if request.use_ai_recognition else None
        await job_manager.run_job(job.job_id, ai_service)
        increment_usage(user, db)

    background_tasks.add_task(run_job)

    return JobResponse(
        job_id=job.job_id,
        status=job.status.value,
        message="任务已创建，正在处理中",
    )


@router.post("/format/file", response_model=JobResponse)
async def format_file(
    card_key: str,
    file: UploadFile = File(...),
    input_format: str = Query("auto"),
    spec_name: Optional[str] = Query(None),
    include_cover: bool = Query(True),
    include_toc: bool = Query(True),
    toc_title: str = Query("目 录"),
    use_ai_recognition: bool = Query(False),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Upload and format a document file (docx, txt, md)."""
    user = get_current_user(card_key, db)
    check_usage_limit(user)

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # Check file extension
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in {"docx", "txt", "md", "markdown"}:
        raise HTTPException(status_code=400, detail="仅支持 .docx, .txt, .md 文件")

    # Read file content
    content = await file.read()

    # Check file size limit (0 means unlimited)
    max_size_mb = settings.MAX_UPLOAD_FILE_SIZE_MB
    if max_size_mb > 0:
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小 ({file_size_mb:.1f} MB) 超过限制 ({max_size_mb} MB)"
            )

    # Extract text based on file type
    if ext == "docx":
        try:
            text = extract_text_from_docx(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法解析 docx 文件: {e}")
        detected_format = InputFormat.PLAINTEXT
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("gbk")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="无法解析文件编码")

        if ext in {"md", "markdown"}:
            detected_format = InputFormat.MARKDOWN
        else:
            detected_format = InputFormat.AUTO

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    # Parse input format
    try:
        fmt = InputFormat(input_format)
    except ValueError:
        fmt = detected_format

    # Create compile options
    options = CompileOptions(
        input_format=fmt,
        spec_name=spec_name,
        include_cover=include_cover,
        include_toc=include_toc,
        toc_title=toc_title,
    )

    # Create job
    job_manager = get_job_manager()
    job = job_manager.create_job(
        user_id=str(user.id),
        input_text=text,
        input_file_name=file.filename,
        options=options,
    )

    # Run job in background
    async def run_job():
        ai_service = get_ai_service() if use_ai_recognition else None
        await job_manager.run_job(job.job_id, ai_service)
        increment_usage(user, db)

    background_tasks.add_task(run_job)

    return JobResponse(
        job_id=job.job_id,
        status=job.status.value,
        message="文件已上传，正在处理中",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """Get job status and progress."""
    user = get_current_user(card_key, db)

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问此任务")

    progress = job.current_progress
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=progress.progress if progress else None,
        phase=progress.phase if progress else None,
        message=progress.message if progress else None,
        error=job.error,
        output_filename=job.output_filename,
    )


@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(
    job_id: str,
    request: Request,
    card_key: str,
    db: Session = Depends(get_db)
):
    """Stream job progress via SSE."""
    user = get_current_user(card_key, db)

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问此任务")

    async def event_generator():
        async for event in job_manager.stream_progress(job_id):
            if await request.is_disconnected():
                break

            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}), ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return EventSourceResponse(event_generator())


@router.get("/jobs/{job_id}/download")
async def download_result(
    job_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """Download the formatted document."""
    user = get_current_user(card_key, db)

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问此任务")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if not job.output_bytes:
        raise HTTPException(status_code=500, detail="输出文件不存在")

    filename = job.output_filename or "formatted.docx"

    return StreamingResponse(
        io.BytesIO(job.output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/jobs/{job_id}/report")
async def get_validation_report(
    job_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """Get the validation report for a completed job."""
    user = get_current_user(card_key, db)

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问此任务")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if not job.result or not job.result.report:
        return {"report": None}

    report = job.result.report
    return {
        "report": {
            "summary": {
                "ok": report.summary.ok,
                "errors": report.summary.errors,
                "warnings": report.summary.warnings,
                "infos": report.summary.infos,
            },
            "violations": [
                {
                    "id": v.violation_id,
                    "severity": v.severity,
                    "message": v.message,
                    "location": v.location.model_dump() if v.location else None,
                }
                for v in report.violations[:50]
            ],
        },
    }


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    card_key: str,
    db: Session = Depends(get_db)
):
    """Delete a job and its data."""
    user = get_current_user(card_key, db)

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问此任务")

    job_manager.delete_job(job_id)

    return {"message": "任务已删除"}


@router.get("/jobs")
async def list_jobs(
    card_key: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List user's recent jobs."""
    user = get_current_user(card_key, db)

    job_manager = get_job_manager()
    jobs = job_manager.get_user_jobs(str(user.id), limit)

    return {
        "jobs": [
            {
                "job_id": j.job_id,
                "status": j.status.value,
                "input_file_name": j.input_file_name,
                "output_filename": j.output_filename,
                "created_at": j.created_at.isoformat(),
                "updated_at": j.updated_at.isoformat(),
            }
            for j in jobs
        ]
    }
