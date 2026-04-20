# app/plugins/advanced_scheduler/tasks.py
from celery import Celery
from . import celeryconfig

# Create the Celery app instance for this plugin
celery_app = Celery("kaapi_scheduler")
celery_app.config_from_object(celeryconfig)

# Example tasks in this plugin
@celery_app.task
def sample_task(x, y):
    """A simple add task."""
    return x + y

@celery_app.task
def long_running_task(duration=10):
    """Simulate a long-running process."""
    import time
    time.sleep(duration)
    return f"Finished long-running task in {duration} seconds."
