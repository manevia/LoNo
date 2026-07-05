import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("lono_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/**
 * Resolve a media URL. If the URL is a relative /api/... path (e.g. proxied
 * object-storage file), prepend the backend origin; otherwise return as-is.
 */
export const resolveMedia = (url) => {
  if (!url) return url;
  if (url.startsWith("/api/")) return `${BACKEND_URL}${url}`;
  return url;
};
