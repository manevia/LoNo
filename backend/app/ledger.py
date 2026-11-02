"""Simulated $LONO ledger. Every balance change goes through credit()/debit()
so the transactions table always reconciles with wallet balances."""
from fastapi import HTTPException

from .db import db
from .util import uid, now_iso


async def log_tx(user_id: str, kind: str, amount: float, memo: str, ref: str | None = None):
    tx = {"id": uid(), "user_id": user_id, "kind": kind, "amount": round(amount, 4),
          "memo": memo, "ref": ref, "at": now_iso()}
    await db.transactions.insert_one(tx)
    tx.pop("_id", None)
    return tx


async def credit(user_id: str, amount: float, kind: str, memo: str, ref: str | None = None, earned: bool = True):
    inc = {"wallet.lono_balance": amount}
    if earned:
        inc["wallet.total_earned"] = amount
    await db.users.update_one({"id": user_id}, {"$inc": inc})
    return await log_tx(user_id, kind, amount, memo, ref)


async def debit(user_id: str, amount: float, kind: str, memo: str, extra_inc: dict | None = None):
    """Atomic: only succeeds if the balance covers the amount."""
    inc = {"wallet.lono_balance": -amount, **(extra_inc or {})}
    res = await db.users.update_one(
        {"id": user_id, "wallet.lono_balance": {"$gte": amount}}, {"$inc": inc})
    if res.modified_count == 0:
        raise HTTPException(400, "Insufficient $LONO balance")
    return await log_tx(user_id, kind, -amount, memo)


def new_wallet() -> dict:
    return {"lono_balance": 0.0, "staked": 0.0, "total_earned": 0.0}
