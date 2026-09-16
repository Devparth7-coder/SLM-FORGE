"use client";

import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";

export function TopBar() {
  const [health, setHealth] = useState<any>(null);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    fetch("/api/v1/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "error" }));
  }, []);

  return (
    <header className="h-12 shrink-0 border-b border-border bg-bg-elevated flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        <div className="text-xs text-fg-muted font-mono">
          {time.toLocaleTimeString()}
        </div>
      </div>
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${health?.status === "ok" ? "bg-accent-success" : "bg-accent-danger"}`}
          />
          <span className="text-fg-muted">
            API {health?.status === "ok" ? "connected" : "disconnected"}
          </span>
        </div>
        {health?.database && (
          <span className="text-fg-subtle">DB: {health.database}</span>
        )}
        {health?.gpu_available && (
          <span className="badge badge-green">GPU</span>
        )}
        {!health?.gpu_available && health && (
          <span className="badge badge-yellow">CPU</span>
        )}
        <span className="text-fg-subtle font-mono">
          v{health?.app_version || "0.1.0"}
        </span>
      </div>
    </header>
  );
}
