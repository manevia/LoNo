// LoNo on Cloudflare: one Worker serves the website (static assets) and forwards the
// API to a single always-on Container running LoNo's Python API (backend/Dockerfile).
import { Container, getContainer } from "@cloudflare/containers";

// `Env` (bindings and plain vars) is generated from wrangler.jsonc by `wrangler types`.
// Settings and secrets passed into the API container (plain vars from wrangler.jsonc,
// secrets set with `wrangler secret put` or by the GitHub deploy workflow).
const PASS_THROUGH = [
  "MONGO_URL", "DB_NAME", "JWT_SECRET", "SECRET_ENC_KEY", "MEDIA_INTERNAL_SECRET",
  "STORAGE_BACKEND", "S3_BUCKET", "S3_REGION", "S3_ENDPOINT_URL", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
  "ADMIN_EMAILS", "ADMIN_PASSWORD", "SUPPORT_EMAIL", "PUBLIC_ORIGIN", "CORS_ORIGINS",
  "PILOT_MODE", "PILOT_STARTED_AT", "SEED_DEMO_DATA", "MAX_UPLOAD_MB", "MEDIA_ENABLED", "TERMS_VERSION",
  "ANTHROPIC_API_KEY", "TRANSCRIBE_API_KEY", "GOOGLE_CLIENT_ID", "STRIPE_API_KEY",
  "ANDROID_APP_PACKAGE", "ANDROID_CERT_SHA256",
];

export class LonoApi extends Container<Env> {
  defaultPort = 8001;            // uvicorn in backend/Dockerfile
  sleepAfter = "2h";             // kept awake by the cron below; wakes on the next request if it ever sleeps
  enableInternet = true;         // MongoDB Atlas, Cloudflare R2, optional AI/payment APIs

  constructor(ctx: DurableObjectState<{}>, env: Env) {
    super(ctx, env);
    const vars: Record<string, string> = {};
    const all = env as unknown as Record<string, unknown>;     // includes secrets, which aren't in the generated type
    for (const k of PASS_THROUGH) {
      const v = all[k];
      if (typeof v === "string" && v !== "") vars[k] = v;
    }
    this.envVars = vars;
  }
}

const api = (env: Env) => getContainer(env.LONO_API, "api");   // one named instance: consistent state

function toApi(request: Request): Request {
  // The visitor's address comes from Cloudflare; anything the client sent is dropped.
  const headers = new Headers(request.headers);
  headers.delete("x-forwarded-for");
  headers.delete("x-real-ip");
  const ip = request.headers.get("cf-connecting-ip");
  if (ip) headers.set("x-forwarded-for", ip);
  headers.set("x-forwarded-proto", "https");
  headers.set("x-forwarded-host", new URL(request.url).host);
  return new Request(request, { headers });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url);
    if (pathname.startsWith("/api/") || pathname.startsWith("/.well-known/")) {
      try {
        return await api(env).fetch(toApi(request));
      } catch (err) {
        console.error("API unavailable", err);
        return Response.json({ detail: "LoNo is starting up or briefly unavailable. Try again in a moment." }, { status: 503 });
      }
    }
    return env.ASSETS.fetch(request);       // website; app routes fall back to index.html
  },

  // Keep the API awake so background jobs (claim repair, scheduled publishing) keep running.
  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(api(env).fetch(new Request("http://lono/api/health")).then((r) => r.text()).catch(() => undefined));
  },
};
