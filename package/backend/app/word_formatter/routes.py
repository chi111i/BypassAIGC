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
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.database import get_db
from app.models.models import User, SavedSpec
from app.services.ai_service import AIService
from app.utils.auth import get_user_from_token

from .services import (
    CompileOptions,
    CompilePhase,
    InputFormat,
    Job,
    JobType,
    JobStatus,
    ai_generate_spec,
    builtin_specs,
    compile_document,
    detect_input_format,
    export_spec_to_json,
    get_job_manager,
    get_spec_schema,
    validate_custom_spec,
    PreprocessConfig,
    PreprocessResult,
    # Format Checker
    FormatChecker,
    FormatCheckResult,
    FormatIssue,
    CheckMode,
    IssueSeverity,
    IssueType,
    check_format,
    PARAGRAPH_TYPES,
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


class FormatFileRequest(BaseModel):
    """Request for file upload formatting."""
    input_format: str = "auto"
    spec_name: Optional[str] = None
    custom_spec_json: Optional[str] = None
    include_cover: bool = True
    include_toc: bool = True
    toc_title: str = "目 录"


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


# Preprocess Request/Response Models
class PreprocessRequest(BaseModel):
    """Request for text preprocessing."""
    text: str = Field(..., min_length=10, description="原始文章文本")
    chunk_paragraphs: int = Field(40, ge=10, le=100, description="每块最大段落数")
    chunk_chars: int = Field(8000, ge=2000, le=15000, description="每块最大字符数")


class PreprocessJobResponse(BaseModel):
    """Response for preprocess job creation."""
    job_id: str
    status: str
    message: str


class PreprocessProgressEvent(BaseModel):
    """SSE progress event for preprocessing."""
    phase: str
    total_paragraphs: int
    processed_paragraphs: int
    current_chunk: int
    total_chunks: int
    message: str
    error: Optional[str] = None
    is_recoverable: bool = True


class ParagraphInfoResponse(BaseModel):
    """Paragraph info in preprocess result."""
    index: int
    text: str
    paragraph_type: Optional[str] = None
    confidence: float = 0.0
    is_rule_identified: bool = False


class PreprocessResultResponse(BaseModel):
    """Response for preprocess result."""
    success: bool
    marked_text: str = ""
    paragraphs: List[ParagraphInfoResponse] = []
    type_statistics: dict = {}
    integrity_check_passed: bool = False
    warnings: List[str] = []
    error: Optional[str] = None


# Format Check Request/Response Models
class FormatCheckRequest(BaseModel):
    """Request for format checking."""
    text: str = Field(..., min_length=10, description="原始文章文本")
    mode: str = Field("loose", description="检测模式: loose(宽松) 或 strict(严格)")


class FormatIssueResponse(BaseModel):
    """Format issue in check result."""
    line: int
    paragraph_index: int
    issue_type: str
    severity: str
    message: str
    suggestion: str
    content_preview: str = ""


class FormatParagraphResponse(BaseModel):
    """Paragraph info in format check result."""
    index: int
    text: str
    line_start: int
    line_end: int
    paragraph_type: str = "body"
    confidence: float = 1.0
    is_auto_detected: bool = True


class FormatCheckResponse(BaseModel):
    """Response for format check."""
    success: bool
    is_valid: bool = False
    mode: str = "loose"
    issues: List[FormatIssueResponse] = []
    paragraphs: List[FormatParagraphResponse] = []
    marked_text: str = ""
    type_statistics: dict = {}
    original_hash: str = ""
    error: Optional[str] = None


class ParagraphTypesResponse(BaseModel):
    """Response for paragraph types."""
    types: dict


# Saved Spec Request/Response Models
class SaveSpecRequest(BaseModel):
    """Request to save a spec."""
    name: str = Field(..., min_length=1, max_length=100, description="规范名称")
    spec_json: str = Field(..., min_length=10, description="规范 JSON 内容")
    description: Optional[str] = Field(None, max_length=500, description="规范描述")


class SavedSpecResponse(BaseModel):
    """Response for a saved spec."""
    id: int
    name: str
    description: Optional[str] = None
    spec_json: str
    created_at: str
    updated_at: str


class SavedSpecListResponse(BaseModel):
    """Response for saved spec list."""
    specs: List[SavedSpecResponse]


def get_current_user(
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> User:
    """Get current user by JWT token or card_key (backward compat)."""
    if authorization and authorization.startswith("Bearer "):
        jwt_token = authorization.split(" ")[1]
        user_id = get_user_from_token(jwt_token)
        if user_id is not None:
            user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
            if user:
                user.last_used = datetime.utcnow()
                db.commit()
                return user

    if token:
        user_id = get_user_from_token(token)
        if user_id is not None:
            user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
            if user:
                user.last_used = datetime.utcnow()
                db.commit()
                return user

    if card_key:
        user = db.query(User).filter(
            User.card_key == card_key,
            User.is_active.is_(True),
        ).first()
        if user:
            user.last_used = datetime.utcnow()
            db.commit()
            return user

    raise HTTPException(status_code=401, detail="未提供有效认证")


def check_usage_limit(user: User) -> None:
    """Check if user has remaining usage quota (shared with polishing)."""
    usage_limit = user.usage_limit or 0
    usage_count = user.usage_count or 0

    if usage_limit > 0 and usage_count >= usage_limit:
        raise HTTPException(status_code=403, detail="该账户已达到使用次数限制")


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
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Get user's usage information (shared with polishing)."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

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
    request: GenerateSpecRequest,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Generate a formatting spec from user requirements using AI."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)
    check_usage_limit(user)

    print(f"\n[WORD-FORMATTER] ========== AI 规范生成请求 ==========", flush=True)
    print(f"[WORD-FORMATTER] 用户ID: {user.id}", flush=True)
    print(f"[WORD-FORMATTER] 需求长度: {len(request.requirements)} 字符", flush=True)

    try:
        ai_service = get_ai_service()
        spec = await ai_generate_spec(request.requirements, ai_service)

        increment_usage(user, db)

        print(f"[WORD-FORMATTER] ✅ 规范生成成功: {spec.meta.get('name', 'AI_Generated')}", flush=True)
        print(f"[WORD-FORMATTER] ===========================================\n", flush=True)

        return {
            "success": True,
            "spec_json": export_spec_to_json(spec),
            "spec_name": spec.meta.get("name", "AI_Generated"),
        }
    except Exception as e:
        print(f"[WORD-FORMATTER] ❌ 规范生成失败: {e}", flush=True)
        print(f"[WORD-FORMATTER] ===========================================\n", flush=True)
        raise HTTPException(status_code=500, detail=f"生成规范失败: {str(e)}")


@router.post("/format/text", response_model=JobResponse)
async def format_text(
    request: FormatRequest,
    background_tasks: BackgroundTasks,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Format text document and return job ID."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)
    check_usage_limit(user)

    if not request.text:
        raise HTTPException(status_code=400, detail="文本内容不能为空")

    print(f"\n[WORD-FORMATTER] ========== 文本格式化请求 ==========", flush=True)
    print(f"[WORD-FORMATTER] 用户ID: {user.id}", flush=True)
    print(f"[WORD-FORMATTER] 文本长度: {len(request.text)} 字符", flush=True)
    print(f"[WORD-FORMATTER] 规范: {request.spec_name or 'Default'}", flush=True)
    print(f"[WORD-FORMATTER] 封面: {'是' if request.include_cover else '否'}, 目录: {'是' if request.include_toc else '否'}", flush=True)

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
        job_type=JobType.FORMAT,
        user_id=str(user.id),
        input_text=request.text,
        options=options,
    )

    # Run job in background
    async def run_job():
        await job_manager.run_job(job.job_id)
        increment_usage(user, db)

    background_tasks.add_task(run_job)

    return JobResponse(
        job_id=job.job_id,
        status=job.status.value,
        message="任务已创建，正在处理中",
    )


@router.post("/format/file", response_model=JobResponse)
async def format_file(
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    file: UploadFile = File(...),
    input_format: str = Query("auto"),
    spec_name: Optional[str] = Query(None),
    include_cover: bool = Query(True),
    include_toc: bool = Query(True),
    toc_title: str = Query("目 录"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Upload and format a document file (docx, txt, md)."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)
    check_usage_limit(user)

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    print(f"\n[WORD-FORMATTER] ========== 文件格式化请求 ==========", flush=True)
    print(f"[WORD-FORMATTER] 用户ID: {user.id}", flush=True)
    print(f"[WORD-FORMATTER] 文件名: {file.filename}", flush=True)
    print(f"[WORD-FORMATTER] 规范: {spec_name or 'Default'}", flush=True)

    # Check file extension
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in {"docx", "txt", "md", "markdown"}:
        raise HTTPException(status_code=400, detail="仅支持 .docx, .txt, .md 文件")

    # Read file content
    content = await file.read()

    print(f"[WORD-FORMATTER] 文件大小: {len(content)} 字节", flush=True)
    print(f"[WORD-FORMATTER] 文件类型: {ext}", flush=True)

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
        job_type=JobType.FORMAT,
        user_id=str(user.id),
        input_text=text,
        input_file_name=file.filename,
        options=options,
    )

    # Run job in background
    async def run_job():
        await job_manager.run_job(job.job_id)
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
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Get job status and progress."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

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
    card_key: str = Query(None),
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Stream job progress via SSE."""
    user = get_current_user(authorization=authorization, card_key=card_key, db=db)

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
    card_key: str = Query(None),
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Download the formatted document."""
    user = get_current_user(authorization=authorization, card_key=card_key, db=db)

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

    # RFC 5987: URL encode filename for Content-Disposition header
    # to support non-ASCII characters (e.g., Chinese filenames)
    encoded_filename = quote(filename, safe='')

    # Provide ASCII-safe fallback for legacy clients
    try:
        filename.encode('ascii')
        ascii_fallback = filename
    except UnicodeEncodeError:
        # For non-ASCII filenames, provide a generic fallback
        ascii_fallback = "download.docx"

    return StreamingResponse(
        io.BytesIO(job.output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.get("/jobs/{job_id}/report")
async def get_validation_report(
    job_id: str,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Get the validation report for a completed job."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

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
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Delete a job and its data."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

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
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List user's recent jobs."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    job_manager = get_job_manager()
    jobs = job_manager.get_user_jobs(str(user.id), limit)

    return {
        "jobs": [
            {
                "job_id": j.job_id,
                "job_type": j.job_type.value,
                "status": j.status.value,
                "input_file_name": j.input_file_name,
                "output_filename": j.output_filename,
                "created_at": j.created_at.isoformat(),
                "updated_at": j.updated_at.isoformat(),
            }
            for j in jobs
        ]
    }


# ============ Preprocess API Endpoints ============

@router.post("/preprocess/text", response_model=PreprocessJobResponse)
async def preprocess_text(
    request: PreprocessRequest,
    background_tasks: BackgroundTasks,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Start text preprocessing job."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)
    check_usage_limit(user)

    print(f"\n[WORD-FORMATTER] ========== 文本预处理请求 ==========", flush=True)
    print(f"[WORD-FORMATTER] 用户ID: {user.id}", flush=True)
    print(f"[WORD-FORMATTER] 文本长度: {len(request.text)} 字符", flush=True)
    print(f"[WORD-FORMATTER] 分块配置: {request.chunk_paragraphs} 段/{request.chunk_chars} 字符", flush=True)

    preprocess_config = PreprocessConfig(
        chunk_paragraphs=request.chunk_paragraphs,
        chunk_chars=request.chunk_chars,
    )

    job_manager = get_job_manager()
    job = job_manager.create_job(
        job_type=JobType.PREPROCESS,
        user_id=str(user.id),
        input_text=request.text,
        preprocess_config=preprocess_config,
    )

    ai_service = get_ai_service()

    async def run_job():
        await job_manager.run_job(job.job_id, ai_service)
        increment_usage(user, db)

    background_tasks.add_task(run_job)

    return PreprocessJobResponse(
        job_id=job.job_id,
        status=job.status.value,
        message="预处理任务已创建，正在处理中",
    )


@router.post("/preprocess/file", response_model=PreprocessJobResponse)
async def preprocess_file(
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    file: UploadFile = File(...),
    chunk_paragraphs: int = Query(40, ge=10, le=100),
    chunk_chars: int = Query(8000, ge=2000, le=15000),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Upload and preprocess a document file."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)
    check_usage_limit(user)

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    print(f"\n[WORD-FORMATTER] ========== 文件预处理请求 ==========", flush=True)
    print(f"[WORD-FORMATTER] 用户ID: {user.id}", flush=True)
    print(f"[WORD-FORMATTER] 文件名: {file.filename}", flush=True)

    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in {"docx", "txt", "md", "markdown"}:
        raise HTTPException(status_code=400, detail="仅支持 .docx, .txt, .md 文件")

    content = await file.read()

    print(f"[WORD-FORMATTER] 文件大小: {len(content)} 字节", flush=True)

    max_size_mb = settings.MAX_UPLOAD_FILE_SIZE_MB
    if max_size_mb > 0:
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小 ({file_size_mb:.1f} MB) 超过限制 ({max_size_mb} MB)"
            )

    if ext == "docx":
        try:
            text = extract_text_from_docx(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法解析 docx 文件: {e}")
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("gbk")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="无法解析文件编码")

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    preprocess_config = PreprocessConfig(
        chunk_paragraphs=chunk_paragraphs,
        chunk_chars=chunk_chars,
    )

    job_manager = get_job_manager()
    job = job_manager.create_job(
        job_type=JobType.PREPROCESS,
        user_id=str(user.id),
        input_text=text,
        input_file_name=file.filename,
        preprocess_config=preprocess_config,
    )

    ai_service = get_ai_service()

    async def run_job():
        await job_manager.run_job(job.job_id, ai_service)
        increment_usage(user, db)

    background_tasks.add_task(run_job)

    return PreprocessJobResponse(
        job_id=job.job_id,
        status=job.status.value,
        message="文件已上传，预处理任务正在处理中",
    )


@router.get("/preprocess/{job_id}/stream")
async def stream_preprocess_progress(
    job_id: str,
    request: Request,
    card_key: str = Query(None),
    token: str = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Stream preprocessing progress via SSE."""
    user = get_current_user(authorization=authorization, card_key=card_key, db=db)

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问此任务")

    if job.job_type != JobType.PREPROCESS:
        raise HTTPException(status_code=400, detail="该任务不是预处理任务")

    async def event_generator():
        async for event in job_manager.stream_progress(job_id):
            if await request.is_disconnected():
                break

            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}), ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return EventSourceResponse(event_generator())


@router.get("/preprocess/{job_id}/result", response_model=PreprocessResultResponse)
async def get_preprocess_result(
    job_id: str,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Get preprocessing result."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问此任务")

    if job.job_type != JobType.PREPROCESS:
        raise HTTPException(status_code=400, detail="该任务不是预处理任务")

    if job.status == JobStatus.PENDING or job.status == JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if job.status == JobStatus.FAILED:
        return PreprocessResultResponse(
            success=False,
            error=job.error,
        )

    result = job.preprocess_result
    if not result:
        raise HTTPException(status_code=500, detail="预处理结果不存在")

    return PreprocessResultResponse(
        success=result.success,
        marked_text=result.marked_text,
        paragraphs=[
            ParagraphInfoResponse(
                index=p.index,
                text=p.text,
                paragraph_type=p.paragraph_type,
                confidence=p.confidence,
                is_rule_identified=p.is_rule_identified,
            )
            for p in result.paragraphs
        ],
        type_statistics=result.type_statistics,
        integrity_check_passed=result.integrity_check_passed,
        warnings=result.warnings,
        error=result.error,
    )


@router.delete("/preprocess/{job_id}")
async def delete_preprocess_job(
    job_id: str,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Delete a preprocess job."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job.user_id != str(user.id):
        raise HTTPException(status_code=403, detail="无权访问此任务")

    if job.job_type != JobType.PREPROCESS:
        raise HTTPException(status_code=400, detail="该任务不是预处理任务")

    job_manager.delete_job(job_id)

    return {"message": "预处理任务已删除"}


# ============ Saved Spec API Endpoints ============

@router.post("/specs/save", response_model=SavedSpecResponse)
async def save_spec(
    request: SaveSpecRequest,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Save a user's custom spec."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    # Validate spec JSON
    try:
        validate_custom_spec(request.spec_json)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"规范 JSON 无效: {e}")

    # Check if name already exists for this user
    existing = db.query(SavedSpec).filter(
        SavedSpec.user_id == user.id,
        SavedSpec.name == request.name
    ).first()

    if existing:
        # Update existing spec
        existing.spec_json = request.spec_json
        existing.description = request.description
        db.commit()
        db.refresh(existing)

        print(f"[WORD-FORMATTER] 更新规范 user_id={user.id} name={request.name}", flush=True)

        return SavedSpecResponse(
            id=existing.id,
            name=existing.name,
            description=existing.description,
            spec_json=existing.spec_json,
            created_at=existing.created_at.isoformat(),
            updated_at=existing.updated_at.isoformat(),
        )

    # Create new spec
    new_spec = SavedSpec(
        user_id=user.id,
        name=request.name,
        description=request.description,
        spec_json=request.spec_json,
    )
    db.add(new_spec)
    db.commit()
    db.refresh(new_spec)

    print(f"[WORD-FORMATTER] 保存规范 user_id={user.id} name={request.name} id={new_spec.id}", flush=True)

    return SavedSpecResponse(
        id=new_spec.id,
        name=new_spec.name,
        description=new_spec.description,
        spec_json=new_spec.spec_json,
        created_at=new_spec.created_at.isoformat(),
        updated_at=new_spec.updated_at.isoformat(),
    )


@router.get("/specs/saved", response_model=SavedSpecListResponse)
async def list_saved_specs(
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """List user's saved specs."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    specs = db.query(SavedSpec).filter(
        SavedSpec.user_id == user.id
    ).order_by(SavedSpec.updated_at.desc()).all()

    return SavedSpecListResponse(
        specs=[
            SavedSpecResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                spec_json=s.spec_json,
                created_at=s.created_at.isoformat(),
                updated_at=s.updated_at.isoformat(),
            )
            for s in specs
        ]
    )


@router.get("/specs/saved/{spec_id}", response_model=SavedSpecResponse)
async def get_saved_spec(
    spec_id: int,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Get a specific saved spec."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    spec = db.query(SavedSpec).filter(
        SavedSpec.id == spec_id,
        SavedSpec.user_id == user.id
    ).first()

    if not spec:
        raise HTTPException(status_code=404, detail="规范不存在")

    return SavedSpecResponse(
        id=spec.id,
        name=spec.name,
        description=spec.description,
        spec_json=spec.spec_json,
        created_at=spec.created_at.isoformat(),
        updated_at=spec.updated_at.isoformat(),
    )


@router.delete("/specs/saved/{spec_id}")
async def delete_saved_spec(
    spec_id: int,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Delete a saved spec."""
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    spec = db.query(SavedSpec).filter(
        SavedSpec.id == spec_id,
        SavedSpec.user_id == user.id
    ).first()

    if not spec:
        raise HTTPException(status_code=404, detail="规范不存在")

    db.delete(spec)
    db.commit()

    print(f"[WORD-FORMATTER] 删除规范 user_id={user.id} spec_id={spec_id}", flush=True)

    return {"message": "规范已删除"}


# ============ Format Check API Endpoints ============

@router.get("/format-check/types", response_model=ParagraphTypesResponse)
async def get_paragraph_types():
    """Get available paragraph types and their descriptions."""
    return ParagraphTypesResponse(types=PARAGRAPH_TYPES)


@router.post("/format-check/text", response_model=FormatCheckResponse)
async def format_check_text(
    request: FormatCheckRequest,
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Check text format (synchronous, no AI required).

    This endpoint detects Markdown format issues and auto-identifies paragraph types
    based on rules. Users can choose between 'loose' and 'strict' check modes.
    """
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    print(f"\n[WORD-FORMATTER] ========== 文章格式检测请求 ==========", flush=True)
    print(f"[WORD-FORMATTER] 用户ID: {user.id}", flush=True)
    print(f"[WORD-FORMATTER] 文本长度: {len(request.text)} 字符", flush=True)
    print(f"[WORD-FORMATTER] 检测模式: {request.mode}", flush=True)

    try:
        # Perform format check
        result = check_format(request.text, mode=request.mode)

        print(f"[WORD-FORMATTER] ✅ 格式检测完成", flush=True)
        print(f"[WORD-FORMATTER] 是否通过: {result.is_valid}", flush=True)
        print(f"[WORD-FORMATTER] 问题数量: {len(result.issues)}", flush=True)
        print(f"[WORD-FORMATTER] 段落数量: {len(result.paragraphs)}", flush=True)
        print(f"[WORD-FORMATTER] ===========================================\n", flush=True)

        return FormatCheckResponse(
            success=result.success,
            is_valid=result.is_valid,
            mode=result.mode.value,
            issues=[
                FormatIssueResponse(
                    line=issue.line,
                    paragraph_index=issue.paragraph_index,
                    issue_type=issue.issue_type.value,
                    severity=issue.severity.value,
                    message=issue.message,
                    suggestion=issue.suggestion,
                    content_preview=issue.content_preview
                )
                for issue in result.issues
            ],
            paragraphs=[
                FormatParagraphResponse(
                    index=p.index,
                    text=p.text,
                    line_start=p.line_start,
                    line_end=p.line_end,
                    paragraph_type=p.paragraph_type,
                    confidence=p.confidence,
                    is_auto_detected=p.is_auto_detected
                )
                for p in result.paragraphs
            ],
            marked_text=result.marked_text,
            type_statistics=result.type_statistics,
            original_hash=result.original_hash,
            error=result.error
        )

    except Exception as e:
        print(f"[WORD-FORMATTER] ❌ 格式检测失败: {e}", flush=True)
        print(f"[WORD-FORMATTER] ===========================================\n", flush=True)
        raise HTTPException(status_code=500, detail=f"格式检测失败: {str(e)}")


@router.post("/format-check/file", response_model=FormatCheckResponse)
async def format_check_file(
    card_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    file: UploadFile = File(...),
    mode: str = Query("loose", description="检测模式: loose(宽松) 或 strict(严格)"),
    db: Session = Depends(get_db)
):
    """
    Check file format (synchronous, no AI required).

    Supports .docx, .txt, .md files.
    """
    user = get_current_user(card_key=card_key, authorization=authorization, db=db)

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    print(f"\n[WORD-FORMATTER] ========== 文件格式检测请求 ==========", flush=True)
    print(f"[WORD-FORMATTER] 用户ID: {user.id}", flush=True)
    print(f"[WORD-FORMATTER] 文件名: {file.filename}", flush=True)
    print(f"[WORD-FORMATTER] 检测模式: {mode}", flush=True)

    # Check file extension
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in {"docx", "txt", "md", "markdown"}:
        raise HTTPException(status_code=400, detail="仅支持 .docx, .txt, .md 文件")

    # Read file content
    content = await file.read()

    print(f"[WORD-FORMATTER] 文件大小: {len(content)} 字节", flush=True)

    # Check file size limit
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
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("gbk")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="无法解析文件编码")

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        # Perform format check
        result = check_format(text, mode=mode)

        print(f"[WORD-FORMATTER] ✅ 文件格式检测完成", flush=True)
        print(f"[WORD-FORMATTER] 是否通过: {result.is_valid}", flush=True)
        print(f"[WORD-FORMATTER] 问题数量: {len(result.issues)}", flush=True)
        print(f"[WORD-FORMATTER] ===========================================\n", flush=True)

        return FormatCheckResponse(
            success=result.success,
            is_valid=result.is_valid,
            mode=result.mode.value,
            issues=[
                FormatIssueResponse(
                    line=issue.line,
                    paragraph_index=issue.paragraph_index,
                    issue_type=issue.issue_type.value,
                    severity=issue.severity.value,
                    message=issue.message,
                    suggestion=issue.suggestion,
                    content_preview=issue.content_preview
                )
                for issue in result.issues
            ],
            paragraphs=[
                FormatParagraphResponse(
                    index=p.index,
                    text=p.text,
                    line_start=p.line_start,
                    line_end=p.line_end,
                    paragraph_type=p.paragraph_type,
                    confidence=p.confidence,
                    is_auto_detected=p.is_auto_detected
                )
                for p in result.paragraphs
            ],
            marked_text=result.marked_text,
            type_statistics=result.type_statistics,
            original_hash=result.original_hash,
            error=result.error
        )

    except Exception as e:
        print(f"[WORD-FORMATTER] ❌ 文件格式检测失败: {e}", flush=True)
        print(f"[WORD-FORMATTER] ===========================================\n", flush=True)
        raise HTTPException(status_code=500, detail=f"格式检测失败: {str(e)}")
