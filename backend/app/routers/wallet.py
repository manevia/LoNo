import random
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config
from ..db import db
from ..ledger import credit, debit, log_tx
from ..security import get_user
from ..util import now, now_iso, uid

router = APIRouter(tags=["wallet"])
APY = {30: 8, 90: 14, 180: 22, 365: 35}


class StakeIn(BaseModel):
    amount: float = Field(gt=0)
    lock_days: Literal[30, 90, 180, 365] = 30


@router.get("/wallet")
async def wallet(user=Depends(get_user)):
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "wallet": 1})
    stakes = await db.stakes.find({"user_id": user["id"], "active": True}, {"_id": 0}).to_list(100)
    for s in stakes:
        s["unlocked"] = datetime.fromisoformat(s["unlock_at"]) <= now()
        s["accrued"] = _accrued(s)
    return {"wallet": u["wallet"], "stakes": stakes, "address": f"lono1{user['id'].replace('-', '')[:38]}",
            "price_usd": config.LONO_PRICE_USD}


@router.get("/wallet/transactions")
async def transactions(user=Depends(get_user)):
    return await db.transactions.find({"user_id": user["id"]}, {"_id": 0}).sort("at", -1).limit(200).to_list(200)


def _accrued(s) -> float:
    days = max(0.0, (now() - datetime.fromisoformat(s["started_at"])).total_seconds() / 86400)
    days = min(days, s["lock_days"])
    return round(s["amount"] * (s["apy"] / 100) * (days / 365), 4)


SOURCES = {"watch_to_earn": "watching", "learn_to_earn": "courses", "staking_reward": "staking",
           "creator_payout": "creator", "signup_bonus": "bonus"}


@router.get("/wallet/insights")
async def insights(days: int = 30, user=Depends(get_user)):
    """Daily earnings by source, watch time and viewing streak for the wallet chart."""
    if days not in (7, 30, 90):
        raise HTTPException(422, "days must be 7, 30 or 90")
    today_dt = now()
    dates = [(today_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    start = dates[0]
    series = {d: {"date": d, **{k: 0.0 for k in SOURCES.values()}, "watch_minutes": 0} for d in dates}
    totals = {k: 0.0 for k in SOURCES.values()}
    async for t in db.transactions.find({"user_id": user["id"], "kind": {"$in": list(SOURCES)},
                                         "at": {"$gte": start}}, {"kind": 1, "amount": 1, "at": 1}):
        d, src = t["at"][:10], SOURCES[t["kind"]]
        if d in series:
            series[d][src] = round(series[d][src] + t["amount"], 4)
            totals[src] = round(totals[src] + t["amount"], 4)

    watched = {}
    async for w in db.watch_sessions.find({"user_id": user["id"]}, {"day": 1, "verified_sec": 1}):
        watched[w["day"]] = watched.get(w["day"], 0) + w.get("verified_sec", 0)
    for d in dates:
        series[d]["watch_minutes"] = int(watched.get(d, 0) // 60)

    # Streak: consecutive days, ending today (or yesterday if nothing yet today), with 1+ verified minute.
    streak, cursor = 0, today_dt
    if watched.get(cursor.strftime("%Y-%m-%d"), 0) < 60:
        cursor -= timedelta(days=1)
    while watched.get(cursor.strftime("%Y-%m-%d"), 0) >= 60:
        streak += 1
        cursor -= timedelta(days=1)

    return {"days": days, "series": list(series.values()), "totals": totals,
            "total_earned": round(sum(totals.values()), 4),
            "watch_minutes": sum(v["watch_minutes"] for v in series.values()),
            "streak_days": streak}


@router.post("/wallet/stake")
async def stake(body: StakeIn, user=Depends(get_user)):
    apy = APY[body.lock_days]
    await debit(user["id"], body.amount, "stake", f"Staked for {body.lock_days} days at {apy}% APY",
                extra_inc={"wallet.staked": body.amount})
    s = {"id": uid(), "user_id": user["id"], "amount": body.amount, "lock_days": body.lock_days,
         "apy": apy, "active": True, "started_at": now_iso(),
         "unlock_at": (now() + timedelta(days=body.lock_days)).isoformat()}
    await db.stakes.insert_one(s)
    s.pop("_id", None)
    return s


@router.post("/wallet/unstake/{stake_id}")
async def unstake(stake_id: str, user=Depends(get_user)):
    s = await db.stakes.find_one({"id": stake_id, "user_id": user["id"], "active": True})
    if not s:
        raise HTTPException(404, "Stake not found")
    early = datetime.fromisoformat(s["unlock_at"]) > now()
    # Early exit forfeits rewards; principal is always returned.
    reward = 0.0 if early else _accrued(s)
    res = await db.stakes.update_one({"id": stake_id, "active": True},
                                     {"$set": {"active": False, "ended_at": now_iso(), "reward": reward, "early": early}})
    if not res.modified_count:
        raise HTTPException(409, "Stake already closed")
    await db.users.update_one({"id": user["id"]},
                              {"$inc": {"wallet.lono_balance": s["amount"], "wallet.staked": -s["amount"]}})
    await log_tx(user["id"], "unstake", s["amount"],
                 "Unstaked early, rewards forfeited" if early else "Unstaked principal")
    if reward > 0:
        await credit(user["id"], reward, "staking_reward", f"{s['apy']}% APY over {s['lock_days']} days")
    return {"returned": round(s["amount"] + reward, 4), "reward": reward, "early": early}


@router.get("/tokenomics")
async def tokenomics():
    staked, wallets = 0.0, 0
    async for u in db.users.find({}, {"wallet.staked": 1}):
        wallets += 1
        staked += u.get("wallet", {}).get("staked", 0.0)
    rewards = 0.0
    async for t in db.transactions.find({"amount": {"$gt": 0}, "kind": {"$in": [
            "watch_to_earn", "learn_to_earn", "staking_reward", "signup_bonus"]}}, {"amount": 1}):
        rewards += t["amount"]
    circulating, price = 250_000_000, config.LONO_PRICE_USD
    rng = random.Random(now().strftime("%Y-%m-%d"))  # same chart all day
    chart = [{"day": (now() - timedelta(days=i)).strftime("%a"), "price": round(price * (0.85 + rng.random() * 0.25), 4)}
             for i in range(6, 0, -1)] + [{"day": now().strftime("%a"), "price": price}]
    return {
        "symbol": "LONO", "name": "LoNo Utility Token", "simulated": True,
        "circulating_supply": circulating, "max_supply": 1_000_000_000, "burned": 12_500_000,
        "treasury": 350_000_000, "creator_fund": 120_000_000, "education_fund": 80_000_000,
        "community_fund": 60_000_000, "rewards_distributed": round(rewards, 2),
        "total_wallets": wallets, "total_staked": round(staked, 2), "price_usd": price,
        "market_cap": circulating * price,
        "change_24h": round((chart[-1]["price"] / chart[-2]["price"] - 1) * 100, 2),
        "network_health": 98.6, "chart_7d": chart,
        "allocation": [
            {"name": "Community & Rewards", "value": 35}, {"name": "Treasury", "value": 20},
            {"name": "Creator Fund", "value": 15}, {"name": "Education Fund", "value": 10},
            {"name": "Team & Advisors", "value": 12}, {"name": "Public Sale", "value": 8},
        ],
    }
