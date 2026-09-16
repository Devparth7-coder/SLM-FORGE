"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BarChart3 } from "lucide-react";
import { MetricCard } from "@/components/ui/MetricCard";

export default function EvaluationPage() {
  const [evals, setEvals] = useState<any[]>([]);
  useEffect(() => { api.listEvaluations().then(setEvals).catch(() => {}); }, []);
  const completed = evals.filter((e) => e.status === "COMPLETED");
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold">Evaluation</h1>
      <p className="text-sm text-fg-muted">Standardised evaluation results across models.</p>
      {completed.length === 0 ? (
        <div className="card py-16 text-center">
          <BarChart3 className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No completed evaluations yet.</p>
        </div>
      ) : (
        completed.map((e: any) => (
          <div key={e.id} className="card">
            <div className="card-header">
              <div className="font-medium">{e.is_baseline ? "BASELINE" : "FINE-TUNED"} · {e.id.slice(0, 8)}</div>
              <span className="badge badge-green">{e.sample_count} samples</span>
            </div>
            <div className="card-body grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="Accuracy" value={e.metrics_json.accuracy?.toFixed(3) ?? "—"} />
              <MetricCard label="F1" value={e.metrics_json.f1?.toFixed(3) ?? "—"} />
              <MetricCard label="Macro F1" value={e.metrics_json.macro_f1?.toFixed(3) ?? "—"} />
              <MetricCard label="JSON Validity" value={(e.metrics_json.json_validity_rate != null ? (e.metrics_json.json_validity_rate * 100).toFixed(1) + "%" : "—")} />
            </div>
          </div>
        ))
      )}
    </div>
  );
}
