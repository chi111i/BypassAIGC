"""
Job Manager: Async job execution with SSE progress updates.

Features:
- Async job queue
- SSE (Server-Sent Events) progress streaming
- Job status tracking
- File cleanup
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
    compile_document_with_ai,
)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    user_id: Optional[str]
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    input_text: Optional[str] = None
    input_file_name: Optional[str] = None
    options: Optional[CompileOptions] = None
    result: Optional[CompileResult] = None
    progress_history: List[JobProgress] = field(default_factory=list)
    current_progress: Optional[JobProgress] = None
    error: Optional[str] = None
    output_bytes: Optional[bytes] = None
    output_filename: Optional[str] = None


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
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._job_retention = timedelta(hours=job_retention_hours)
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_job(
        self,
        user_id: Optional[str] = None,
        input_text: Optional[str] = None,
        input_file_name: Optional[str] = None,
        options: Optional[CompileOptions] = None,
    ) -> Job:
        """Create a new job and return it."""
        job_id = str(uuid.uuid4())
        now = datetime.now()

        job = Job(
            job_id=job_id,
            user_id=user_id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
            input_text=input_text,
            input_file_name=input_file_name,
            options=options,
        )

        self._jobs[job_id] = job
        self._job_locks[job_id] = asyncio.Lock()

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
            ai_service: Optional AI service for enhanced parsing

        Returns:
            Updated Job with results
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        async with self._semaphore:
            async with self._job_locks[job_id]:
                job.status = JobStatus.RUNNING
                job.updated_at = datetime.now()

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

                try:
                    options = job.options or CompileOptions()

                    if ai_service:
                        result = await compile_document_with_ai(
                            job.input_text or "",
                            ai_service,
                            options,
                            progress_callback,
                        )
                    else:
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
                    else:
                        job.status = JobStatus.FAILED
                        job.error = result.error

                except Exception as e:
                    job.status = JobStatus.FAILED
                    job.error = str(e)

                job.updated_at = datetime.now()
                return job

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
            job.status = JobStatus.CANCELLED
            job.updated_at = datetime.now()
            return True

        return False

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its data."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            if job_id in self._job_locks:
                del self._job_locks[job_id]
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

        # 取消所有运行中的任务
        for job_id, job in list(self._jobs.items()):
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.CANCELLED
                job.error = "服务关闭，任务被取消"

        # 清空任务字典
        self._jobs.clear()

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
