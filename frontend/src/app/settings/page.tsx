"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Settings as SettingsIcon } from "lucide-react";

export default function SettingsPage() {
  const [hw, setHw] = useState<any>(null);
  useEffect(() => {
    api.hardware().then(setHw).catch(() => {});
  }, []);
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold">Settings</h1>
      <p className="text-sm text-fg-muted">System configuration and hardware detection.</p>
      <div className="card p-4 space-y-3">
        <h3 className="font-medium flex items-center gap-2"><SettingsIcon className="w-4 h-4" />Hardware</h3>
        {hw && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm font-mono">
            <div><div className="text-fg-subtle text-xs">CPU cores</div><div>{hw.cpu_count_logical}</div></div>
            <div><div className="text-fg-subtle text-xs">RAM</div><div>{hw.total_ram_gb} GB</div></div>
            <div><div className="text-fg-subtle text-xs">GPU</div><div>{hw.gpu_name || "None"}</div></div>
            <div><div className="text-fg-subtle text-xs">VRAM</div><div>{hw.vram_total_mb ? `${hw.vram_total_mb.toFixed(0)} MB` : "—"}</div></div>
          </div>
        )}
        {hw?.warnings?.length > 0 && (
          <div className="bg-accent-warning/10 border border-accent-warning/30 rounded p-2 text-xs">
            {hw.warnings.map((w: string, i: number) => <div key={i}>⚠ {w}</div>)}
          </div>
        )}
      </div>
      <div className="card p-4 text-sm text-fg-muted">
        <h3 className="font-medium text-fg mb-2">Configuration</h3>
        <p>Configuration is loaded from <code className="font-mono text-accent">.env</code> and YAML files in <code className="font-mono text-accent">configs/</code>.</p>
      </div>
    </div>
  );
}
