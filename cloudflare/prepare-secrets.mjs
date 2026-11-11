// Builds the secrets file for `wrangler deploy --secrets-file`.
// - Your secrets come from the environment (GitHub Actions secrets).
// - LoNo's internal secrets are generated ONCE: if Cloudflare already has them, they're
//   left out of the file and keep their values (secrets files apply additively).
// Nothing is printed except the names that were set.
import { execSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { writeFileSync } from "node:fs";

const out = {};
const fromEnv = { MONGO_URL: "MONGO_URL", AWS_ACCESS_KEY_ID: "R2_ACCESS_KEY_ID", AWS_SECRET_ACCESS_KEY: "R2_SECRET_ACCESS_KEY",
                  ADMIN_PASSWORD: "ADMIN_PASSWORD", ANTHROPIC_API_KEY: "ANTHROPIC_API_KEY", GOOGLE_CLIENT_ID: "GOOGLE_CLIENT_ID" };
for (const [name, envName] of Object.entries(fromEnv)) {
  if (process.env[envName]) out[name] = process.env[envName];
}

let existing = [];
try {
  existing = JSON.parse(execSync("npx wrangler secret list --format json", { stdio: ["ignore", "pipe", "ignore"] }).toString()).map((s) => s.name);
} catch {
  existing = [];   // first deployment: the Worker doesn't exist yet
}
for (const name of ["JWT_SECRET", "SECRET_ENC_KEY", "MEDIA_INTERNAL_SECRET"]) {
  if (!existing.includes(name)) out[name] = randomBytes(32).toString("hex");
}

const file = process.argv[2];
writeFileSync(file, JSON.stringify(out), { mode: 0o600 });
console.log("Secrets to set:", Object.keys(out).join(", ") || "(none; all already set)");
