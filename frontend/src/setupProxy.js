// Dev only: forward /api to the FastAPI server so the app can use relative URLs.
const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use("/media", createProxyMiddleware({
    target: process.env.API_PROXY_TARGET || "http://localhost:8001",
    changeOrigin: true,
    pathRewrite: (path) => (path.startsWith("/media") ? path : `/media${path}`),
  }));
  app.use("/api", createProxyMiddleware({
    target: process.env.API_PROXY_TARGET || "http://localhost:8001",
    changeOrigin: true,
    pathRewrite: (path) => (path.startsWith("/api") ? path : `/api${path}`),
  }));
};
