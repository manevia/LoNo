"""Create admin accounts at startup, and manage admins from the command line.

    python -m app.admin_setup make-admin  someone@example.org
    python -m app.admin_setup remove-admin someone@example.org
    python -m app.admin_setup reset-password someone@example.org

The command line works with a real MongoDB (MONGO_URL=mongodb://...). With the
in-memory database each run is separate, so use ADMIN_EMAILS instead."""
import asyncio
import logging
import secrets
import sys

from . import config
from .audit import audit
from .db import db
from .security import hash_password

log = logging.getLogger("lono")


def _new_password() -> str:
    return secrets.token_urlsafe(12)


def _banner(lines: list[str]):
    width = max(len(x) for x in lines) + 4
    out = ["", "=" * width] + [f"  {x}" for x in lines] + ["=" * width, ""]
    print("\n".join(out), flush=True)


async def bootstrap_admins():
    """For each ADMIN_EMAILS address: create the account if it doesn't exist (so nobody
    else can register it), or leave an existing account alone unless it's already admin."""
    from .routers.auth import create_user  # avoid import cycle at module load
    for email in sorted(config.ADMIN_EMAILS):
        u = await db.users.find_one({"email": email})
        if u is None:
            password = config.ADMIN_PASSWORD or _new_password()
            created = await create_user(email, "LoNo Admin", "admin_setup", password=password, record_consent=False)
            await db.users.update_one({"id": created["id"]}, {"$set": {"role": "admin"}})
            await audit("admin_created", None, target=created["id"], details={"via": "ADMIN_EMAILS"})
            if config.ADMIN_PASSWORD:
                _banner([f"LoNo admin account ready: {email}", "Password: the ADMIN_PASSWORD you set."])
            else:
                _banner([f"LoNo admin account created: {email}",
                         f"Temporary password: {password}",
                         "Sign in, then change it under Profile > Settings.",
                         "This password is shown only once."])
        elif u.get("role") != "admin":
            log.warning("%s is in ADMIN_EMAILS but already belongs to an ordinary account, so it was NOT "
                        "made admin (someone else may have registered it). If you're sure it's yours, run: "
                        "python -m app.admin_setup make-admin %s", email, email)


async def _cli(cmd: str, email: str):
    email = email.strip().lower()
    u = await db.users.find_one({"email": email})
    if not u:
        print(f"No account with the email {email}. Sign up first, then run this again.")
        return 1
    if cmd == "make-admin":
        await db.users.update_one({"id": u["id"]}, {"$set": {"role": "admin"}})
        await audit("admin_granted", None, target=u["id"], details={"via": "command line"})
        print(f"{email} is now an admin.")
    elif cmd == "remove-admin":
        await db.users.update_one({"id": u["id"]}, {"$set": {"role": "viewer"}})
        await audit("admin_removed", None, target=u["id"], details={"via": "command line"})
        print(f"{email} is no longer an admin.")
    elif cmd == "reset-password":
        pw = _new_password()
        await db.users.update_one({"id": u["id"]}, {"$set": {"password_hash": hash_password(pw)}})
        await audit("password_reset", None, target=u["id"], details={"via": "command line"})
        print(f"New temporary password for {email}: {pw}\nSign in and change it under Profile > Settings.")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    if config.MONGO_URL.startswith("mongomock://"):
        print("The in-memory database can't be changed from the command line (it lives inside the running "
              "server). Put the email in ADMIN_EMAILS in backend/.env and restart instead.")
        sys.exit(1)
    sys.exit(asyncio.run(_cli(sys.argv[1], sys.argv[2])))
