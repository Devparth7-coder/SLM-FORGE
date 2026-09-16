"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ShieldAlert } from "lucide-react";

export default function RobustnessPage() {
  const [runs, setRuns] = useState<any[]>([]);
  useEffect(() => { api.listRobustness().then(setRuns).catch(() => {}); }, []);
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold">Robustness</h1>
      <p className="text-sm text-fg-muted">
        Perturbation testing: formatting, variable renaming, truncation, adversarial examples.
        <br />
        <span className="text-accent-info text-xs">
          RobustnessScore(p) = Macro-F1(p) / Macro-F1(baseline). Degradation = Baseline − Perturbed.
        </span>
      </p>
      {runs.length === 0 ? (
        <div className="card py-16 text-center">
          <ShieldAlert className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No robustness tests run yet.</p>
          <p className="text-xs text-fg-subtle mt-1">Run robustness from an experiment detail page.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-base">
            <thead><tr><th>Perturbation</th><th>Model</th><th>Macro F1</th><th>Score</th><th>Degradation</th><th>Status</th></tr></thead>
            <tbody>
              {runs.map((r: any) => (
                <tr key={r.id}>
                  <td className="font-mono text-xs">{r.perturbation_type}</td>
                  <td className="text-xs">{r.is_baseline ? "Base" : "Fine-tuned"}</td>
                  <td className="font-mono">{r.metrics_json?.macro_f1?.toFixed(3) ?? "—"}</td>
                  <td className="font-mono">{r.robustness_score != null ? r.robustness_score.toFixed(3) : "—"}</td>
                  <td className={`font-mono ${r.performance_degradation > 0 ? "text-accent-danger" : "text-accent-success"}`}>
                    {r.performance_degradation != null ? r.performance_degradation.toFixed(4) : "—"}
                  </td>
                  <td><span className={`badge ${r.status === "COMPLETED" ? "badge-green" : r.status === "FAILED" ? "badge-red" : "badge-gray"}`}>{r.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
