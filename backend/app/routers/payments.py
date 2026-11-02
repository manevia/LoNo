from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import config
from ..db import db
from ..ledger import credit
from ..security import get_user
from ..util import now_iso

router = APIRouter(prefix="/payments", tags=["payments"])
PRICES = {"premium": 999, "creator": 2499}  # USD cents / month


class CheckoutIn(BaseModel):
    plan: Literal["free", "premium", "creator"]


class TokenBuyIn(BaseModel):
    amount_usd: float = Field(gt=0, le=500)


def _stripe():
    if not config.STRIPE_API_KEY:
        raise HTTPException(503, "Payments are off. Set STRIPE_API_KEY on the server to take payments.")
    import stripe
    stripe.api_key = config.STRIPE_API_KEY
    return stripe


@router.post("/checkout")
async def checkout(body: CheckoutIn, user=Depends(get_user)):
    if body.plan == "free":
        await db.users.update_one({"id": user["id"]}, {"$set": {"plan": "free"}})
        return {"url": None, "message": "You're on the Free plan"}
    stripe = _stripe()
    try:
        s = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=user["email"],
            client_reference_id=user["id"],
            line_items=[{"quantity": 1, "price_data": {
                "currency": "usd", "unit_amount": PRICES[body.plan], "recurring": {"interval": "month"},
                "product_data": {"name": f"LoNo {body.plan.title()}"}}}],
            success_url=f"{config.PUBLIC_ORIGIN}/wallet?checkout=success",
            cancel_url=f"{config.PUBLIC_ORIGIN}/wallet?checkout=cancelled",
            metadata={"user_id": user["id"], "plan": body.plan},
            subscription_data={"metadata": {"user_id": user["id"], "plan": body.plan}},
        )
    except Exception as e:
        raise HTTPException(502, f"Stripe couldn't start checkout: {e}")
    return {"url": s.url, "session_id": s.id}


@router.post("/webhook")
async def webhook(request: Request):
    """Stripe → LoNo. Point a Stripe webhook at /api/payments/webhook with events
    checkout.session.completed and customer.subscription.deleted."""
    stripe = _stripe()
    if not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Set STRIPE_WEBHOOK_SECRET to accept Stripe webhooks")
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""),
                                               config.STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid Stripe signature")
    if await db.stripe_events.find_one({"id": event["id"]}):
        return {"ok": True, "duplicate": True}
    await db.stripe_events.insert_one({"id": event["id"], "type": event["type"], "at": now_iso()})

    obj = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        md = obj.get("metadata") or {}
        if md.get("user_id") and md.get("plan") in PRICES:
            await db.users.update_one({"id": md["user_id"]}, {"$set": {
                "plan": md["plan"], "stripe_customer_id": obj.get("customer"),
                "stripe_subscription_id": obj.get("subscription")}})
    elif event["type"] == "customer.subscription.deleted":
        await db.users.update_one({"stripe_subscription_id": obj.get("id")}, {"$set": {"plan": "free"}})
    return {"ok": True}


@router.post("/token-buy")
async def token_buy(body: TokenBuyIn, user=Depends(get_user)):
    """Demo-only: credits $LONO without taking payment. Disable with SIMULATED_TOKEN_PURCHASE=false."""
    if not config.SIMULATED_TOKEN_PURCHASE:
        raise HTTPException(403, "Token purchases are not available")
    tokens = round(body.amount_usd / config.LONO_PRICE_USD, 4)
    await credit(user["id"], tokens, "token_purchase", f"Demo purchase: {tokens} LONO for ${body.amount_usd:.2f}",
                 earned=False)
    return {"tokens": tokens, "message": f"Added {tokens:,.2f} $LONO (demo purchase)"}
