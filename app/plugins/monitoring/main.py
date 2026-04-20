    # main.py
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import Counter, Histogram, Gauge
from fastapi import APIRouter, Response, Request, Depends
import time
import os
import psutil

# Définition des métriques
REQUEST_COUNT = Counter(
    'http_requests_total', 
    'Total number of HTTP requests', 
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds', 
    'HTTP request latency in seconds', 
    ['method', 'endpoint']
)

# Remove duplicate system metrics
# CPU_USAGE and MEMORY_USAGE are removed since they are already defined in main.py

def get_router():
    router = APIRouter()
    
    @router.get("/metrics")
    async def metrics_endpoint():
        """
        Endpoint to expose Prometheus metrics.
        Used by Prometheus to scrape monitoring data.
        """
        try:
            # Generate metrics in Prometheus format
            prometheus_metrics = generate_latest()
            return Response(
                content=prometheus_metrics, 
                media_type=CONTENT_TYPE_LATEST
            )
        except Exception as e:
            # In case of error, return a response with an error message
            return Response(
                content=f"Error generating metrics: {str(e)}",
                status_code=500
            )
    
    # Add endpoints for testing and manually generating metrics
    @router.get("/record-request")
    async def record_request(request: Request, path: str, status_code: int = 200, latency: float = 0.1):
        """
        Endpoint to manually record a request in metrics.
        """
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=path,
            status=status_code
        ).inc()
        
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=path
        ).observe(latency)
        
        return {"message": "Request recorded in metrics"}
    
    @router.get("/info")
    async def get_system_info():
        """
        Retrieves current system information.
        Used to display general system information.
        """
        try:
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "disk_usage_percent": disk.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_used_gb": round(disk.used / (1024**3), 2)
            }
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error retrieving system information: {str(e)}")
            return {"error": str(e)}
    
    return router

monitoring_router = get_router()