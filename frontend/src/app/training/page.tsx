"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Activity } from "lucide-react";

export default function TrainingPage() {
  const [exps, setExps] = useState<any[]>([]);
  useEffect(() => {
    api.listExperiments("RUNNING").then(setExps).catch(() => {});
  }, []);
  const running = exps.filter((e) => e.training_run?.status === "RUNNING");
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold">Training</h1>
      <p className="text-sm text-fg-muted">Live training metrics for active runs.</p>
      {running.length === 0 ? (
        <div className="card py-16 text-center">
          <Activity className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No active training runs.</p>
        </div>
      ) : (
        running.map((e: any) => {
          const tr = e.training_run;
          const progress = tr.total_steps ? (tr.current_step / tr.total_steps) * 100 : 0;
          return (
            <div key={e.id} className="card p-4 space-y-3">
              <div className="flex justify-between">
                <div className="font-medium">{e.name}</div>
                <div className="text-xs font-mono text-fg-muted">Step {tr.current_step}/{tr.total_steps || "?"}</div>
              </div>
              <div className="w-full h-2 bg-bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
              </div>
              <div className="grid grid-cols-4 gap-3 text-center text-sm">
                <div><div className="text-fg-subtle text-xs">Loss</div><div className="font-mono">{tr.train_loss?.toFixed(4) ?? "—"}</div></div>
                <div><div className="text-fg-subtle text-xs">Val Loss</div><div className="font-mono">{tr.val_loss?.toFixed(4) ?? "—"}</div></div>
                <div><div className="text-fg-subtle text-xs">LR</div><div className="font-mono">{tr.learning_rate?.toExponential(2) ?? "—"}</div></div>
                <div><div className="text-fg-subtle text-xs">tok/s</div><div className="font-mono">{tr.tokens_per_sec?.toFixed(1) ?? "—"}</div></div>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
