"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Database, Loader2 } from "lucide-react";

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [ds, setDs] = useState<any>(null);
  const [quality, setQuality] = useState<any[]>([]);
  const [samples, setSamples] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getDataset(id),
      api.getDatasetQuality(id),
      api.listSamples(id, undefined, undefined),
    ]).then(([d, q, s]) => {
      setDs(d); setQuality(q); setSamples(s); setLoading(false);
    });
  }, [id]);

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin text-accent" /></div>;
  const latest = ds.versions?.[0];
  const qr = quality[0];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <div className="text-xs text-fg-subtle uppercase tracking-wider">Dataset</div>
        <h1 className="text-xl font-semibold mt-1">{ds.name}</h1>
        {ds.is_demo && <span className="badge badge-yellow mt-2">DEMO DATASET</span>}
      </div>
      <p className="text-sm text-fg-muted">{ds.description}</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4"><div className="metric-label">Samples</div><div className="metric-value">{latest?.sample_count || "—"}</div></div>
        <div className="card p-4"><div className="metric-label">Version</div><div className="metric-value text-base">{latest?.version || "—"}</div></div>
        <div className="card p-4"><div className="metric-label">Hash</div><div className="metric-value text-xs font-mono">{latest?.content_hash?.slice(0, 16)}…</div></div>
        <div className="card p-4"><div className="metric-label">Domain</div><div className="metric-value text-base">{ds.domain}</div></div>
      </div>
      {qr && (
        <div className="card">
          <div className="card-header"><h3 className="font-medium">Quality Report</h3></div>
          <div className="card-body grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <QMetric label="Duplicate rate" value={`${(qr.duplicate_rate * 100).toFixed(1)}%`} />
            <QMetric label="Near-duplicates" value={qr.near_duplicate_count} />
            <QMetric label="Short samples" value={qr.short_samples_count} />
            <QMetric label="Leakage" value={qr.train_test_overlap} danger={qr.train_test_overlap > 0} />
          </div>
          {qr.issues?.length > 0 && (
            <div className="px-4 pb-4 space-y-1">
              {qr.issues.map((i: any, idx: number) => (
                <div key={idx} className={`text-xs p-2 rounded border ${
                  i.severity === "error" ? "border-accent-danger/30 bg-accent-danger/10 text-accent-danger" :
                  i.severity === "warning" ? "border-accent-warning/30 bg-accent-warning/10 text-accent-warning" :
                  "border-border bg-bg-muted text-fg-muted"
                }`}>
                  <span className="font-mono">{i.code}</span>: {i.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="card">
        <div className="card-header"><h3 className="font-medium">Samples ({samples.length})</h3></div>
        <div className="max-h-96 overflow-auto">
          <table className="table-base">
            <thead><tr><th>ID</th><th>Split</th><th>Label</th><th>Category</th><th>Preview</th></tr></thead>
            <tbody>
              {samples.slice(0, 50).map((s: any) => (
                <tr key={s.id}>
                  <td className="font-mono text-xs">{s.sample_id}</td>
                  <td className="text-xs">{s.split}</td>
                  <td><span className={`badge ${s.label === "vulnerable" ? "badge-red" : "badge-green"}`}>{s.label}</span></td>
                  <td className="font-mono text-xs">{s.category}</td>
                  <td className="max-w-md truncate text-xs font-mono text-fg-muted">{s.input_text?.slice(0, 80)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function QMetric({ label, value, danger }: { label: string; value: any; danger?: boolean }) {
  return (
    <div>
      <div className="metric-label">{label}</div>
      <div className={`metric-value text-base ${danger ? "text-accent-danger" : ""}`}>{value}</div>
    </div>
  );
}
