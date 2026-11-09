import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";
import { applyDeviceClasses, getPrefs, setPref } from "@/lib/device";
import { installSpatialNav } from "@/lib/spatialNav";
import "@/lib/install"; // start listening for the install prompt early

// ?tv=1 / ?tv=0 (used by the TV app packages) switches TV mode on or off and remembers it.
const tvParam = new URLSearchParams(window.location.search).get("tv");
if (tvParam === "1" || tvParam === "0") setPref("tv", tvParam === "1");
applyDeviceClasses();
installSpatialNav(() => getPrefs().tv);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);

// Installable app + offline screen. Only in production builds, and only on
// HTTPS or localhost (browsers refuse service workers elsewhere).
if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => { /* app still works without it */ });
  });
}
