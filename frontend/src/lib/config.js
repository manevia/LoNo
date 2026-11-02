import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// Feature flags from GET /api/config, fetched once and shared.
const DEFAULTS = { ai: false, transcription: false, payments: false, google_client_id: null,
  simulated_token_purchase: true, heartbeat_sec: 30, lono_price_usd: 0.184 };
let cache = null;
let pending = null;

export function loadConfig() {
  if (cache) return Promise.resolve(cache);
  if (!pending) {
    pending = api.get("/config")
      .then(({ data }) => (cache = { ...DEFAULTS, ...data }))
      .catch(() => (cache = DEFAULTS));
  }
  return pending;
}

export function useConfig() {
  const [cfg, setCfg] = useState(cache || DEFAULTS);
  useEffect(() => { loadConfig().then(setCfg); }, []);
  return cfg;
}
