import axios from "axios";

// Empty = same origin (nginx in Docker, or CRA's dev proxy to :8001).
const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("lono_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Pull the server's human-readable message out of an axios error. */
export const errorText = (e, fallback = "Something went wrong. Try again.") => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg.replace(/^Value error, /, "");
  return fallback;
};

/** Relative /api/... media paths (uploaded files) need the backend origin prefixed. */
export const resolveMedia = (url) => {
  if (!url) return url;
  if (url.startsWith("/api/")) return `${BACKEND_URL}${url}`;
  return url;
};
