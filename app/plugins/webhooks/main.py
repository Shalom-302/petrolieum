# app/plugins/webhooks/main.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from .schemas import WebhookCreate, WebhookUpdate
from .models import WebhookSubscription
from app.core.db import get_db
from app.core.security import get_current_user  # or your own auth
from app.casbin_setup import get_casbin_enforcer  # optional, if you do RBAC checks

def get_router() -> APIRouter:

    router = APIRouter()

    @router.get("/", name="list_webhooks")
    def list_webhooks(
        db: Session = Depends(get_db),
        # optional: current_user = Depends(get_current_user),
        # optional: enforcer = Depends(get_casbin_enforcer)
    ) -> List[dict]:
        subs = db.query(WebhookSubscription).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "event": s.event,
                "url": s.url,
                "secret": s.secret,
                "is_enabled": s.is_enabled,
                "config": s.config
            }
            for s in subs
        ]

    @router.post("/", name="create_webhook", status_code=status.HTTP_201_CREATED)
    def create_webhook(
        data: WebhookCreate,
        db: Session = Depends(get_db),
        # optional: current_user = Depends(get_current_user),
    ):
        sub = WebhookSubscription(
            name=data.name,
            event=data.event,
            url=data.url,
            secret=data.secret,
            is_enabled=data.is_enabled,
            config=data.config
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return {"detail": "Webhook created", "id": sub.id}

    @router.get("/{webhook_id}", name="get_webhook")
    def get_webhook(
        webhook_id: int,
        db: Session = Depends(get_db),
    ):
        sub = db.query(WebhookSubscription).filter_by(id=webhook_id).first()
        if not sub:
            raise HTTPException(404, "Webhook not found")
        return {
            "id": sub.id,
            "name": sub.name,
            "event": sub.event,
            "url": sub.url,
            "secret": sub.secret,
            "is_enabled": sub.is_enabled,
            "config": sub.config
        }

    @router.put("/{webhook_id}", name="update_webhook")
    def update_webhook(
        webhook_id: int,
        data: WebhookUpdate,
        db: Session = Depends(get_db),
    ):
        sub = db.query(WebhookSubscription).filter_by(id=webhook_id).first()
        if not sub:
            raise HTTPException(404, "Webhook not found")

        if data.name is not None:
            sub.name = data.name
        if data.event is not None:
            sub.event = data.event
        if data.url is not None:
            sub.url = data.url
        if data.secret is not None:
            sub.secret = data.secret
        if data.is_enabled is not None:
            sub.is_enabled = data.is_enabled
        if data.config is not None:
            sub.config = data.config

        db.commit()
        db.refresh(sub)
        return {"detail": "Webhook updated"}

    @router.delete("/{webhook_id}", name="delete_webhook")
    def delete_webhook(
        webhook_id: int,
        db: Session = Depends(get_db),
    ):
        sub = db.query(WebhookSubscription).filter_by(id=webhook_id).first()
        if not sub:
            raise HTTPException(404, "Webhook not found")
        db.delete(sub)
        db.commit()
        return {"detail": "Webhook deleted"}

    return router


webhooks_router = get_router()