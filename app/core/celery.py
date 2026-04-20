# backend/app/core/celery.py
from celery import Celery
from .config import settings
import os

# Create Celery instance
celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # Tell Celery where to find tasks
    include=["app.tasks.veille_tasks"]
)

# Set LangSmith environment variables if configured
from pydantic import SecretStr

if settings.LANGSMITH_TRACING_V2:
    os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGSMITH_TRACING_V2
if settings.LANGSMITH_ENDPOINT:
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
if settings.LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
if settings.LANGSMITH_PROJECT:
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT

celery_app.conf.update(
    task_track_started=True,
)

if __name__ == "__main__":
    celery_app.start()