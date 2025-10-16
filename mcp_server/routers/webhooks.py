"""Webhook endpoints for OrderDesk integration."""

import hashlib
import hmac
import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from mcp_server.config import settings
from mcp_server.models.database import WebhookEvent, get_db
from mcp_server.utils.logging import logger

router = APIRouter()


@router.post("/webhooks/orderdesk")
async def receive_orderdesk_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive and process OrderDesk webhooks."""
    try:
        # Get request body
        body = await request.body()
        
        # Verify webhook signature if secret is configured
        if settings.webhook_secret:
            signature = request.headers.get("X-OrderDesk-Signature")
            if not signature:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing webhook signature",
                )
            
            # Verify HMAC signature
            expected_signature = hmac.new(
                settings.webhook_secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature",
                )
        
        # Parse webhook payload
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )
        
        # Extract event ID for deduplication
        event_id = payload.get("event_id") or payload.get("id")
        if not event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing event ID",
            )
        
        # Check for duplicate events
        existing_event = db.query(WebhookEvent).filter(
            WebhookEvent.event_id == event_id
        ).first()
        
        if existing_event:
            logger.info(
                "webhook_duplicate_ignored",
                event_id=event_id,
                message="Duplicate webhook event ignored",
            )
            return {"status": "duplicate", "message": "Event already processed"}
        
        # Store webhook event
        webhook_event = WebhookEvent(
            event_id=event_id,
            payload=json.dumps(payload),
            processed=False,
        )
        db.add(webhook_event)
        db.commit()
        
        # Log webhook receipt
        logger.info(
            "webhook_received",
            event_id=event_id,
            event_type=payload.get("event_type", "unknown"),
            store_id=payload.get("store_id"),
            message="Webhook event received and stored",
        )
        
        # TODO: Process webhook event (e.g., update cache, trigger external systems)
        # For now, just mark as processed
        webhook_event.processed = True
        db.commit()
        
        return {
            "status": "success",
            "message": "Webhook processed successfully",
            "event_id": event_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "webhook_processing_error",
            error=str(e),
            message="Failed to process webhook",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}",
        )
