# app/plugins/advanced_scheduler/celeryconfig.py
from app.core.config import settings

broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# If you use Celery beat, you can set beat_scheduler here or do it in your main Celery file
# e.g. beat_scheduler = "app.plugins.advanced_scheduler.myscheduler.DatabaseScheduler"
