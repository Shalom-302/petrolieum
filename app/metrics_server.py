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

# Create a FastAPI application dedicated to metrics
app = FastAPI(title="Kaapi Metrics", docs_url=None, redoc_url=None)

# Create a custom registry for metrics
REGISTRY = CollectorRegistry()

# Base metrics
HTTP_REQUESTS = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'], registry=REGISTRY)
REQUEST_LATENCY = Summary('http_request_duration_seconds', 'HTTP request latency', registry=REGISTRY)

# Server metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', registry=REGISTRY)
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration in seconds', registry=REGISTRY)

# System metrics
DISK_FREE = Gauge('system_disk_free_bytes', 'Free disk space in bytes', registry=REGISTRY)

@app.get("/metrics")
async def metrics():
    """Endpoint to expose Prometheus metrics."""
    try:
        # Update system metrics
        update_system_metrics()
        
        # Generate Prometheus metrics
        return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error generating metrics: {str(e)}")
        return Response(content=f"# Error: {str(e)}", status_code=500)

def update_system_metrics():
    """Update system metrics."""
    try:
        # We no longer update system metrics here
        # since they are managed in main.py
        
        # Only the DISK_FREE metric is preserved since it is not duplicated
        disk = psutil.disk_usage('/')
        DISK_FREE.set(disk.free)
    except Exception as e:
        logger.error(f"Error updating system metrics: {str(e)}")

async def periodic_metrics_update():
    """Update system metrics periodically."""
    while True:
        update_system_metrics()
        await asyncio.sleep(15)  # Update every 15 seconds

@app.on_event("startup")
async def startup_event():
    """Startup event to initialize background tasks."""
    asyncio.create_task(periodic_metrics_update())
    logger.info("Metrics server started")

if __name__ == "__main__":
    # Start the server on port 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)
