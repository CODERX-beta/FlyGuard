import threading
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


class BackgroundJobManager:
    """
    Observable background job manager for long-running data generation and ML training operations.
    Ensures API endpoints remain responsive while reporting genuine progress and errors.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def create_job(self, job_type: str, description: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "job_type": job_type,
                "description": description,
                "status": "queued",
                "progress_pct": 0.0,
                "stage": "Initialized",
                "metadata": metadata or {},
                "result": None,
                "error": None,
                "started_at": now,
                "updated_at": now,
                "completed_at": None,
            }
        return job_id

    def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        progress_pct: Optional[float] = None,
        stage: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            if status is not None:
                job["status"] = status
                if status in ("completed", "failed"):
                    job["completed_at"] = now
            if progress_pct is not None:
                job["progress_pct"] = round(float(progress_pct), 1)
            if stage is not None:
                job["stage"] = stage
            if result is not None:
                job["result"] = result
            if error is not None:
                job["error"] = error
            job["updated_at"] = now

    def run_in_background(
        self,
        job_type: str,
        description: str,
        fn: Callable[..., Dict[str, Any]],
        *args: Any,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        job_id = self.create_job(job_type, description, metadata)

        def progress_callback(pct: float, stage_msg: str) -> None:
            self.update_job(job_id, status="running", progress_pct=pct, stage=stage_msg)

        def runner() -> None:
            self.update_job(job_id, status="running", progress_pct=2.0, stage="Starting background worker")
            try:
                res = fn(*args, progress_callback=progress_callback, **kwargs)
                self.update_job(
                    job_id,
                    status="completed",
                    progress_pct=100.0,
                    stage="Completed successfully",
                    result=res,
                )
            except Exception as exc:
                err_str = f"{type(exc).__name__}: {str(exc)}"
                tb = traceback.format_exc()
                self.update_job(
                    job_id,
                    status="failed",
                    stage=f"Failed: {err_str}",
                    error=f"{err_str}\n{tb}",
                )

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return self.get_job(job_id)  # type: ignore

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._jobs.values())
        items.sort(key=lambda x: x["started_at"], reverse=True)
        return items[:limit]


job_manager = BackgroundJobManager()

