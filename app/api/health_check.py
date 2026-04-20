from fastapi import APIRouter, Response
from datetime import datetime


def get_router() -> APIRouter:

    router = APIRouter()

    @router.head("/health-check")
    @router.get("/health-check")
    async def health_check():
        """Simple health check endpoint for PWA online status detection."""
        return Response(headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Health-Check-Time": datetime.utcnow().isoformat()
        })

    return router

health_check_router = get_router()