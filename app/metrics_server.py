#!/usr/bin/env python3
# metrics_server.py - Metrics server for Prometheus
from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
from prometheus_client import Counter, Summary, Gauge, Histogram
import uvicorn
import psutil
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("metrics-server")

app = FastAPI(title="Kaapi Metrics", docs_url=None, redoc_url=None)
REGISTRY = CollectorRegistry()

# --- FIX : NOMS UNIQUES POUR ÉVITER LE DUPLICATED TIMESERIES ---
# Base metrics (avec labels)
HTTP_REQUESTS_LABELED = Counter('http_requests_labeled_total', 'Total HTTP requests with labels', ['method', 'endpoint', 'status'], registry=REGISTRY)
REQUEST_LATENCY_SUMMARY = Summary('http_request_latency_seconds', 'HTTP request latency summary', registry=REGISTRY)

# Server metrics (globaux)
REQUEST_COUNT_GLOBAL = Counter('http_requests_global_total', 'Total global HTTP requests', registry=REGISTRY)
REQUEST_DURATION_HIST = Histogram('http_request_duration_hist_seconds', 'HTTP request duration histogram', registry=REGISTRY)

# System metrics
DISK_FREE = Gauge('system_disk_free_bytes', 'Free disk space in bytes', registry=REGISTRY)

@app.get("/metrics")
async def metrics():
    try:
        update_system_metrics()
        return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error generating metrics: {str(e)}")
        return Response(content=f"# Error: {str(e)}", status_code=500)

def update_system_metrics():
    try:
        disk = psutil.disk_usage('/')
        DISK_FREE.set(disk.free)
    except Exception as e:
        logger.error(f"Error updating system metrics: {str(e)}")

async def periodic_metrics_update():
    while True:
        update_system_metrics()
        await asyncio.sleep(15)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_metrics_update())
    logger.info("Metrics server started")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)