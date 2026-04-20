    
# main.py
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter,  Response

def get_router():
    router = APIRouter(tags=["Messaging"])
    
    @router.get("/messaging")
    async def init_messaging():
        print("ok")
    return router