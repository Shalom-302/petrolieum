# app/plugins/advanced_scheduler/main.py
import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict
from sqlalchemy.orm import Session
from app.core.db import get_db
from .models import ScheduledJob
from .tasks import celery_app, sample_task, long_running_task
from .schemas import JobCreateSchema

PLUGIN_ENABLED = True  # Could load from DB or environment

def validate_cron(cron_expr: str):
    # Minimal check, or parse w/ "croniter" library to be robust
    pattern = r"^(\S+\s+){4,5}\S+$"
    if not re.match(pattern, cron_expr):
        raise ValueError("Invalid cron expression")

def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/status")
    def get_scheduler_status():
        """
        Return whether advanced_scheduler plugin is enabled.
        """
        return {"name": "Advanced Scheduler", "enabled": PLUGIN_ENABLED}

    class PluginEnableModel(BaseModel):
        enabled: bool

    @router.post("/status")
    def toggle_scheduler_state(data: PluginEnableModel):
        """
        Enable or disable advanced_scheduler plugin.
        """
        global PLUGIN_ENABLED
        PLUGIN_ENABLED = data.enabled
        return {"detail": f"Plugin Advanced Scheduler is now {'enabled' if PLUGIN_ENABLED else 'disabled'}"}

    # ----- SCHEDULED JOBS CRUD -----
    @router.post("/jobs")
    def create_job(payload: JobCreateSchema, db: Session = Depends(get_db)):
        if not PLUGIN_ENABLED:
            raise HTTPException(403, "Scheduler plugin is disabled.")

        try:
            validate_cron(payload.cron_expr)
        except ValueError as e:
            raise HTTPException(400, str(e))

        job = ScheduledJob(
            name=payload.name,
            cron_expr=payload.cron_expr,
            task_name=payload.task_name,
            args=payload.args,
            enabled=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return {"detail": "Created", "job_id": job.id}

    @router.get("/jobs")
    def list_jobs(db: Session = Depends(get_db)):
        if not PLUGIN_ENABLED:
            raise HTTPException(403, "Scheduler plugin is disabled.")

        jobs = db.query(ScheduledJob).all()
        return [
            {
                "id": j.id,
                "name": j.name,
                "cron_expr": j.cron_expr,
                "task_name": j.task_name,
                "args": j.args,
                "enabled": j.enabled
            }
            for j in jobs
        ]

    @router.put("/jobs/{job_id}")
    def update_job(job_id: int, payload: JobCreateSchema, db: Session = Depends(get_db)):
        if not PLUGIN_ENABLED:
            raise HTTPException(403, "Scheduler plugin is disabled.")

        job = db.query(ScheduledJob).filter_by(id=job_id).first()
        if not job:
            raise HTTPException(404, "Job not found")

        try:
            validate_cron(payload.cron_expr)
        except ValueError as e:
            raise HTTPException(400, str(e))

        job.name = payload.name
        job.cron_expr = payload.cron_expr
        job.task_name = payload.task_name
        job.args = payload.args
        db.commit()
        db.refresh(job)
        return {"detail": "Updated"}

    @router.delete("/jobs/{job_id}")
    def delete_job(job_id: int, db: Session = Depends(get_db)):
        if not PLUGIN_ENABLED:
            raise HTTPException(403, "Scheduler plugin is disabled.")

        job = db.query(ScheduledJob).filter_by(id=job_id).first()
        if not job:
            raise HTTPException(404, "Job not found")

        db.delete(job)
        db.commit()
        return {"detail": "Deleted"}

    # ----- Example Celery tasks endpoints -----
    @router.post("/enqueue-add")
    def enqueue_add(x: int, y: int):
        if not PLUGIN_ENABLED:
            raise HTTPException(403, "Scheduler plugin is disabled.")
        result = sample_task.delay(x, y)
        return {"task_id": result.id, "status": "queued"}

    @router.post("/enqueue-long-running")
    def enqueue_long_running(seconds: int = 10):
        if not PLUGIN_ENABLED:
            raise HTTPException(403, "Scheduler plugin is disabled.")
        result = long_running_task.delay(seconds)
        return {"task_id": result.id, "status": "queued"}

    @router.get("/task-status/{task_id}")
    def task_status(task_id: str):
        async_result = celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "state": async_result.state,
            "result": async_result.result if async_result.ready() else None
        }

    return router

advanced_scheduler_router = get_router()
