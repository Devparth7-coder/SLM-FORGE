"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { GitCompare } from "lucide-react";

export default function ComparisonPage() {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [comparison, setComparison] = useState<any>(null);

  useEffect(() => {
    api.listExperiments().then((e) => {
      setExperiments(e);
      if (e.length) setSelected(e[0].id);
    });
  }, []);
  useEffect(() => {
    if (selected) api.getComparison(selected).then(setComparison).catch(() => setComparison(null));
  }, [selected]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold">Base vs Fine-Tuned Comparison</h1>
      <p className="text-sm text-fg-muted">
        Same test set, same evaluation harness. Δ = Fine-tuned − Base.
      </p>
      <div>
        <label className="label">Experiment</label>
        <select className="select max-w-md" value={selected} onChange={(e) => setSelected(e.target.value)}>
          {experiments.map((e: any) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </div>
      {!comparison?.metrics?.length ? (
        <div className="card py-16 text-center">
          <GitCompare className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">Run both baseline and fine-tuned evaluation to compare.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-base">
            <thead><tr><th>Metric</th><th className="text-right">Base</th><th className="text-right">Fine-tuned</th><th className="text-right">Δ</th></tr></thead>
            <tbody>
              {comparison.metrics.map((m: any) => (
                <tr key={m.name}>
                  <td className="font-mono text-xs">{m.name}</td>
                  <td className="text-right font-mono">{m.base_value != null ? m.base_value.toFixed(4) : "—"}</td>
                  <td className="text-right font-mono">{m.finetuned_value != null ? m.finetuned_value.toFixed(4) : "—"}</td>
                  <td className={`text-right font-mono ${m.delta == null ? "text-fg-subtle" : m.delta > 0 ? "text-accent-success" : m.delta < 0 ? "text-accent-danger" : ""}`}>
                    {m.delta != null ? (m.delta > 0 ? "+" : "") + m.delta.toFixed(4) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
