import asyncio, uuid, httpx
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8001"
async def main():
    c = httpx.Client(timeout=20)
    tok = c.post(f"{B}/api/auth/register", json={"email": f"dv{uuid.uuid4().hex[:6]}@example.com", "password": "Passw0rd!", "name": "Dev", "accept_terms": True}).json()["token"]
    async with async_playwright() as p:
        br = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"); pg = await br.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.goto(B + "/"); await pg.evaluate(f"localStorage.setItem('lono_token','{tok}')")
        await pg.goto(B + "/studio"); await pg.click('[data-testid=open-developer-access]'); await pg.wait_for_selector('[data-testid=developer-access]')
        await pg.click('[data-testid=new-integration]'); await pg.fill('[data-testid=integration-name]', 'Scheduler')
        await pg.check('[data-testid=scope-broadcast\\:control]'); await pg.click('[data-testid=integration-create]')
        await pg.wait_for_selector('[data-testid=integration-token]')
        token = await pg.inner_text('[data-testid=integration-token]')
        me = c.get(f"{B}/api/v1/me", headers={"Authorization": f"Bearer {token}"}).json()
        print("token works:", me["integration"]["scopes"], me["integration"]["environment"])
        await pg.click('text=I\'ve saved them'); await pg.reload(); await pg.wait_for_selector('[data-testid^=integration-ig]')
        print("token hidden after reload:", await pg.locator('[data-testid=integration-token]').count() == 0)
        await pg.click('text=Revoke'); await pg.wait_for_timeout(800)
        print("revoked token rejected:", c.get(f"{B}/api/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401)
        print("API reference:", (await (await pg.request.get(B + "/api/docs")).text()).count("swagger") > 0)
        print("JS ERRORS:", errs)
        await br.close()
asyncio.run(main())
