"""
Job Manager: Async job execution with SSE progress updates.

Features:
- Async job queue
- SSE (Server-Sent Events) progress streaming
- Job status tracking
- File cleanup
- Support for both format and preprocess jobs
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from ..models.stylespec import StyleSpec
from ..models.validation import ValidationReport
from .compiler import (
    CompileOptions,
    CompilePhase,
    CompileProgress,
    CompileResult,
    compile_document,
)
from .preprocessor import (
    ArticlePreprocessor,
    PreprocessConfig,
    PreprocessProgress,
    PreprocessResult,
)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Job type enumeration."""
    FORMAT = "format"
    PREPROCESS = "preprocess"


@dataclass
class JobProgress:
    phase: str
    progress: float
    message: str
    detail: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Job:
    job_id: str
    job_type: JobType
    user_id: Optional[str]
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    input_text: Optional[str] = None
    input_file_name: Optional[str] = None
    # Format job fields
    options: Optional[CompileOptions] = None
    result: Optional[CompileResult] = None
    output_bytes: Optional[bytes] = None
    output_filename: Optional[str] = None
    # Preprocess job fields
    preprocess_config: Optional[PreprocessConfig] = None
    preprocess_result: Optional[PreprocessResult] = None
    # Common fields
    progress_history: List[JobProgress] = field(default_factory=list)
    current_progress: Optional[JobProgress] = None
    error: Optional[str] = None


class JobManager:
    """
    Manages async document formatting jobs.
    """

    def __init__(
        self,
        max_concurrent_jobs: int = 5,
        job_retention_hours: int = 24,
    ):
        self._jobs: Dict[str, Job] = {}
        self._job_locks: Dict[str, asyncio.Lock] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}  # 跟踪运行中的任务，用于取消
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._job_retention = timedelta(hours=job_retention_hours)
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_job(
        self,
        job_type: JobType = JobType.FORMAT,
        user_id: Optional[str] = None,
        input_text: Optional[str] = None,
        input_file_name: Optional[str] = None,
        options: Optional[CompileOptions] = None,
        preprocess_config: Optional[PreprocessConfig] = None,
    ) -> Job:
        """Create a new job and return it."""
        job_id = str(uuid.uuid4())
        now = datetime.now()

        job = Job(
            job_id=job_id,
            job_type=job_type,
            user_id=user_id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
            input_text=input_text,
            input_file_name=input_file_name,
            options=options,
            preprocess_config=preprocess_config,
        )

        self._jobs[job_id] = job
        self._job_locks[job_id] = asyncio.Lock()

        print(f"[WORD-FORMATTER] 创建任务 job_id={job_id[:8]}... 类型={job_type.value}", flush=True)
        print(f"[WORD-FORMATTER] 用户ID: {user_id}", flush=True)
        print(f"[WORD-FORMATTER] 输入文件: {input_file_name or '文本输入'}", flush=True)
        print(f"[WORD-FORMATTER] 文本长度: {len(input_text or '')} 字符", flush=True)

        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def get_user_jobs(self, user_id: str, limit: int = 10) -> List[Job]:
        """Get recent jobs for a user."""
        user_jobs = [
            j for j in self._jobs.values()
            if j.user_id == user_id
        ]
        user_jobs.sort(key=lambda x: x.created_at, reverse=True)
        return user_jobs[:limit]

    async def run_job(
        self,
        job_id: str,
        ai_service: Any = None,
    ) -> Job:
        """
        Execute a job asynchronously.

        Args:
            job_id: Job ID to execute
            ai_service: AI service instance (required for preprocess jobs)

        Returns:
            Updated Job with results
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        print(f"\n[WORD-FORMATTER] ========== 开始执行任务 ==========", flush=True)
        print(f"[WORD-FORMATTER] Job ID: {job_id[:8]}... 类型: {job.job_type.value}", flush=True)

        async with self._semaphore:
            # 注册当前 task，用于 delete_job 时取消
            current_task = asyncio.current_task()
            self._running_tasks[job_id] = current_task

            async with self._job_locks[job_id]:
                job.status = JobStatus.RUNNING
                job.updated_at = datetime.now()

                try:
                    if job.job_type == JobType.FORMAT:
                        await self._run_format_job(job)
                    elif job.job_type == JobType.PREPROCESS:
                        await self._run_preprocess_job(job, ai_service)
                    else:
                        raise ValueError(f"Unknown job type: {job.job_type}")

                except asyncio.CancelledError:
                    # 任务被取消，释放 semaphore 槽位
                    job.status = JobStatus.CANCELLED
                    job.updated_at = datetime.now()
                    job.error = "任务被用户取消"
                    print(f"[WORD-FORMATTER] ⚠️ 任务被取消 job_id={job_id[:8]}...", flush=True)
                    # 重新抛出 CancelledError，让 asyncio 处理
                    raise

                except Exception as e:
                    import traceback
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    print(f"[WORD-FORMATTER] ❌ 任务异常 job_id={job_id[:8]}...", flush=True)
                    print(f"[WORD-FORMATTER] 异常类型: {type(e).__name__}", flush=True)
                    print(f"[WORD-FORMATTER] 异常信息: {e}", flush=True)
                    print(f"[WORD-FORMATTER] 堆栈跟踪:\n{traceback.format_exc()}", flush=True)

                finally:
                    # 确保清理运行任务记录
                    self._running_tasks.pop(job_id, None)

                job.updated_at = datetime.now()
                print(f"[WORD-FORMATTER] ========== 任务执行结束 ==========\n", flush=True)
                return job

    async def _run_format_job(self, job: Job) -> None:
        """Execute a format job."""
        def progress_callback(p: CompileProgress):
            progress = JobProgress(
                phase=p.phase.value,
                progress=p.progress,
                message=p.message,
                detail=p.detail,
            )
            job.current_progress = progress
            job.progress_history.append(progress)
            job.updated_at = datetime.now()

        options = job.options or CompileOptions()

        result = compile_document(
            job.input_text or "",
            options,
            progress_callback,
        )

        job.result = result

        if result.success:
            job.status = JobStatus.COMPLETED
            job.output_bytes = result.docx_bytes
            job.output_filename = self._generate_output_filename(job)
            print(f"[WORD-FORMATTER] ✅ 格式化任务完成 job_id={job.job_id[:8]}...", flush=True)
            print(f"[WORD-FORMATTER] 输出文件: {job.output_filename}", flush=True)
            print(f"[WORD-FORMATTER] 文件大小: {len(result.docx_bytes or b'')} 字节", flush=True)
        else:
            job.status = JobStatus.FAILED
            job.error = result.error
            print(f"[WORD-FORMATTER] ❌ 格式化任务失败 job_id={job.job_id[:8]}...", flush=True)
            print(f"[WORD-FORMATTER] 错误: {result.error}", flush=True)

    async def _run_preprocess_job(self, job: Job, ai_service: Any) -> None:
        """Execute a preprocess job."""
        if not ai_service:
            raise ValueError("AI service is required for preprocess jobs")

        def progress_callback(p: PreprocessProgress):
            progress = JobProgress(
                phase=p.phase.value,
                progress=p.processed_paragraphs / max(p.total_paragraphs, 1),
                message=p.message,
                detail=f"分块 {p.current_chunk}/{p.total_chunks}" if p.total_chunks > 0 else None,
            )
            job.current_progress = progress
            job.progress_history.append(progress)
            job.updated_at = datetime.now()

        config = job.preprocess_config or PreprocessConfig()
        preprocessor = ArticlePreprocessor(ai_service, config)

        result = await preprocessor.preprocess(
            job.input_text or "",
            progress_callback,
        )

        job.preprocess_result = result

        if result.success:
            job.status = JobStatus.COMPLETED
            print(f"[WORD-FORMATTER] ✅ 预处理任务完成 job_id={job.job_id[:8]}...", flush=True)
            print(f"[WORD-FORMATTER] 段落数: {len(result.paragraphs)}", flush=True)
            print(f"[WORD-FORMATTER] 一致性校验: {'通过' if result.integrity_check_passed else '失败'}", flush=True)
        else:
            job.status = JobStatus.FAILED
            job.error = result.error
            print(f"[WORD-FORMATTER] ❌ 预处理任务失败 job_id={job.job_id[:8]}...", flush=True)
            print(f"[WORD-FORMATTER] 错误: {result.error}", flush=True)

    def _generate_output_filename(self, job: Job) -> str:
        """Generate output filename based on input."""
        if job.input_file_name:
            base = job.input_file_name.rsplit(".", 1)[0]
            return f"{base}_formatted.docx"
        return f"formatted_{job.job_id[:8]}.docx"

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
            # 取消正在运行的任务，释放 semaphore 槽位
            task = self._running_tasks.get(job_id)
            if task and not task.done():
                task.cancel()
            job.status = JobStatus.CANCELLED
            job.updated_at = datetime.now()
            return True

        return False

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its data. For RUNNING jobs, also cancels the asyncio task to release semaphore."""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            if job.status in {JobStatus.RUNNING, JobStatus.CANCELLED}:
                # 取消正在运行的任务，释放 semaphore 槽位
                task = self._running_tasks.get(job_id)
                if task and not task.done():
                    task.cancel()
                    print(f"[WORD-FORMATTER] 🛑 取消运行中的任务 job_id={job_id[:8]}...", flush=True)
            del self._jobs[job_id]
            if job_id in self._job_locks:
                del self._job_locks[job_id]
            self._running_tasks.pop(job_id, None)
            return True
        return False

    async def stream_progress(
        self,
        job_id: str,
        poll_interval: float = 0.5,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream job progress as SSE-compatible events.

        Yields dicts suitable for SSE formatting.
        """
        job = self._jobs.get(job_id)
        if not job:
            yield {"event": "error", "data": {"message": "Job not found"}}
            return

        last_progress_count = 0

        while True:
            job = self._jobs.get(job_id)
            if not job:
                yield {"event": "error", "data": {"message": "Job disappeared"}}
                return

            new_progress = job.progress_history[last_progress_count:]
            for p in new_progress:
                yield {
                    "event": "progress",
                    "data": {
                        "phase": p.phase,
                        "progress": p.progress,
                        "message": p.message,
                        "detail": p.detail,
                    },
                }
            last_progress_count = len(job.progress_history)

            if job.status == JobStatus.COMPLETED:
                # 区分不同类型的任务返回不同的完成数据
                if job.job_type == JobType.FORMAT:
                    yield {
                        "event": "completed",
                        "data": {
                            "job_id": job.job_id,
                            "filename": job.output_filename,
                            "warnings": job.result.warnings if job.result else [],
                            "report": {
                                "ok": job.result.report.summary.ok,
                                "errors": job.result.report.summary.errors,
                                "warnings": job.result.report.summary.warnings,
                            } if job.result and job.result.report else None,
                        },
                    }
                else:
                    # PREPROCESS 任务
                    yield {
                        "event": "completed",
                        "data": {
                            "job_id": job.job_id,
                            "success": job.preprocess_result is not None,
                        },
                    }
                return

            if job.status == JobStatus.FAILED:
                yield {
                    "event": "error",
                    "data": {"message": job.error or "Unknown error"},
                }
                return

            if job.status == JobStatus.CANCELLED:
                yield {
                    "event": "cancelled",
                    "data": {"message": "Job was cancelled"},
                }
                return

            await asyncio.sleep(poll_interval)

    async def cleanup_old_jobs(self) -> int:
        """Remove jobs older than retention period. Returns count removed."""
        now = datetime.now()
        cutoff = now - self._job_retention
        to_remove = [
            jid for jid, job in self._jobs.items()
            if job.updated_at < cutoff
        ]
        for jid in to_remove:
            self.delete_job(jid)
        return len(to_remove)

    async def start_cleanup_loop(self, interval_hours: int = 1):
        """Start periodic cleanup task."""
        async def _loop():
            while True:
                await asyncio.sleep(interval_hours * 3600)
                await self.cleanup_old_jobs()

        self._cleanup_task = asyncio.create_task(_loop())

    def stop_cleanup_loop(self):
        """Stop the cleanup loop."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def shutdown(self):
        """
        优雅关闭 Job Manager，清理所有资源。

        应在 FastAPI shutdown 事件中调用。
        """
        # 停止清理循环
        self.stop_cleanup_loop()

        # 取消所有运行中的任务，释放 semaphore 槽位
        for job_id, task in list(self._running_tasks.items()):
            if not task.done():
                task.cancel()
                print(f"[WORD-FORMATTER] 🛑 关闭时取消任务 job_id={job_id[:8]}...", flush=True)

        # 等待任务取消完成（可选，防止立即清理）
        if self._running_tasks:
            await asyncio.sleep(0.1)  # 给取消的任务一点时间处理 CancelledError

        # 清空任务字典
        self._jobs.clear()
        self._running_tasks.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get job statistics."""
        stats = {
            "total": len(self._jobs),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        for job in self._jobs.values():
            stats[job.status.value] = stats.get(job.status.value, 0) + 1
        return stats


# Global job manager instance
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get or create the global job manager."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager


def init_job_manager(
    max_concurrent_jobs: int = 5,
    job_retention_hours: int = 24,
) -> JobManager:
    """Initialize the global job manager with custom settings."""
    global _job_manager
    _job_manager = JobManager(
        max_concurrent_jobs=max_concurrent_jobs,
        job_retention_hours=job_retention_hours,
    )
    return _job_manager
