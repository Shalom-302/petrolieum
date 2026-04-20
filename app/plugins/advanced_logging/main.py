from fastapi import APIRouter, HTTPException, FastAPI, Response
from typing import Dict
import uuid
import os
import logging
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST, Gauge
from .schemas import LogEntryCreate
from .loki_client import LokiClient
from app.core.db import SessionLocal, get_db
from app.core.config import settings
import time

# We define a global plugin "enabled" flag, read from ENV or DB
ADV_LOGGING_ENABLED = True

# Example of a minimal in-memory store (or DB usage)
# LOG_STORE could be replaced by direct push to Loki
LOG_STORE: Dict[str, Dict] = {}

# Prometheus counter for log events
LOG_EVENTS_COUNTER = Counter(
    "kaapi_advanced_logging_events_total",
    "Count of log events created via advanced_logging plugin"
)

# Prometheus gauge for log events by level
LOG_EVENTS_BY_LEVEL = Gauge(
    "kaapi_advanced_logging_events_by_level",
    "Count of log events by level",
    ["level"]
)

# Prometheus gauge for timestamp of the last log event
LAST_LOG_EVENT_TIMESTAMP = Gauge(
    "kaapi_advanced_logging_last_event_timestamp",
    "Timestamp of the last log event"
)

# Initialize a Loki client with the environment variable from settings
LOKI_URL = os.environ.get("LOKI_URL", settings.LOKI_URL)
logging.info(f"Initializing Loki client with URL: {LOKI_URL}")
loki_client = LokiClient(LOKI_URL)

# Function to initialize metrics from existing logs
def initialize_log_metrics():
    try:
        # Query Loki for existing logs
        # This is a simplified version - in a real implementation, 
        # you would need to use the Loki API to query logs
        logs = loki_client.query_logs({"plugin": "advanced_logging"})
        
        # If we can't get logs from Loki, try to use the in-memory store
        if not logs and LOG_STORE:
            logs = LOG_STORE.values()
        
        # Count logs by level
        level_counts = {}
        for log in logs:
            level = log.get("level", "INFO")
            level_counts[level] = level_counts.get(level, 0) + 1
        
        # Update the Prometheus gauges
        for level, count in level_counts.items():
            LOG_EVENTS_BY_LEVEL.labels(level=level).set(count)
            LOG_EVENTS_COUNTER.inc(count)
        
        # Set the last log event timestamp if there are logs
        if logs:
            LAST_LOG_EVENT_TIMESTAMP.set(time.time())
        
        logging.info(f"Initialized log metrics with {sum(level_counts.values())} logs")
        logging.info(f"Logs by level: {level_counts}")
    except Exception as e:
        logging.error(f"Error initializing log metrics: {e}")

# Initialize metrics when the module is loaded
initialize_log_metrics()

def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/metrics")
    def metrics():
      return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


    @router.get("/status")
    def plugin_status():
        return {"name": "advanced_logging", "enabled": ADV_LOGGING_ENABLED}

    @router.post("/status")
    def toggle_plugin_state(enable: bool):
        global ADV_LOGGING_ENABLED
        ADV_LOGGING_ENABLED = enable
        return {"detail": f"advanced_logging plugin is now {'enabled' if enable else 'disabled'}"}

    @router.post("/logs")
    def create_log(entry: LogEntryCreate):
        """
        Create a new log entry. We'll:
          1) increment a Prometheus counter
          2) store in memory
          3) push to Loki
        """
        if not ADV_LOGGING_ENABLED:
            raise HTTPException(403, "advanced_logging plugin is disabled")

        # 1) increment prometheus counter
        LOG_EVENTS_COUNTER.inc()
        LOG_EVENTS_BY_LEVEL.labels(level=entry.level).inc()
        LAST_LOG_EVENT_TIMESTAMP.set(time.time())

        # 2) store in memory (optional)
        log_id = str(uuid.uuid4())
        LOG_STORE[log_id] = {
            "level": entry.level,
            "message": entry.message,
            "labels": entry.labels or {}
        }

        # 3) push to Loki
        combined_labels = {"plugin": "advanced_logging"}
        if entry.labels:
            combined_labels.update(entry.labels)
        loki_client.push_log(entry.level, entry.message, combined_labels)

        return {
            "id": log_id,
            "level": entry.level,
            "message": entry.message,
            "labels": entry.labels or {}
        }

    @router.get("/logs")
    def list_logs():
        """
        Return logs from in-memory store or a subset.
        In production, you'd query from DB or from Loki directly.
        """
        if not ADV_LOGGING_ENABLED:
            raise HTTPException(403, "advanced_logging plugin is disabled")

        result = []
        for log_id, data in LOG_STORE.items():
            result.append({
                "id": log_id,
                "level": data["level"],
                "message": data["message"],
                "labels": data["labels"]
            })
        return result

    @router.delete("/logs/{log_id}")
    def delete_log(log_id: str):
        """
        Remove a log entry from the in-memory store.
        (This won't remove it from Loki.)
        """
        if not ADV_LOGGING_ENABLED:
            raise HTTPException(403, "advanced_logging plugin is disabled")
        if log_id not in LOG_STORE:
            raise HTTPException(404, "Log not found")
        del LOG_STORE[log_id]
        return {"detail": f"Log {log_id} deleted from memory"}

    return router

advanced_logging_router = get_router()
