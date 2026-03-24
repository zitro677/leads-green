import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.webhook import Webhook, WebhookDelivery
from app.schemas.webhook import WebhookCreate, WebhookUpdate, WebhookResponse, DeliveryResponse
from app.api.v1.dependencies import get_current_user

router = APIRouter()


@router.post("/", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wh = Webhook(
        user_id=current_user.id,
        name=body.name,
        url=str(body.url),
        secret=body.secret,
        events=body.events,
    )
    db.add(wh)
    await db.flush()
    return WebhookResponse.model_validate(wh)


@router.get("/", response_model=list[WebhookResponse])
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hooks = (await db.scalars(select(Webhook).where(Webhook.user_id == current_user.id))).all()
    return [WebhookResponse.model_validate(h) for h in hooks]


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wh = await db.scalar(select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == current_user.id))
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse.model_validate(wh)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: uuid.UUID,
    body: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wh = await db.scalar(select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == current_user.id))
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "url":
            value = str(value)
        setattr(wh, field, value)
    return WebhookResponse.model_validate(wh)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wh = await db.scalar(select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == current_user.id))
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(wh)


@router.get("/{webhook_id}/deliveries", response_model=list[DeliveryResponse])
async def list_deliveries(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wh = await db.scalar(select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == current_user.id))
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    deliveries = (await db.scalars(
        select(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id).order_by(WebhookDelivery.created_at.desc()).limit(50)
    )).all()
    return [DeliveryResponse.model_validate(d) for d in deliveries]
