"use client";
import { useEffect, useState, useSearchParams } from "react";
import { api } from "@/lib/api";
import { Bug } from "lucide-react";

export default function FailuresPage() {
  const params = useSearchParams();
  const expId = params.get("experiment");
  const [failures, setFailures] = useState<any[]>([]);

  useEffect(() => {
    api.listFailures(expId || undefined).then(setFailures).catch(() => {});
  }, [expId]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold">Failure Explorer</h1>
      <p className="text-sm text-fg-muted">
        False positives, false negatives, malformed JSON, wrong categories, robustness failures.
      </p>
      {failures.length === 0 ? (
        <div className="card py-16 text-center">
          <Bug className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No failures recorded yet.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-base">
            <thead>
              <tr>
                <th>Sample</th><th>Ground Truth</th><th>Category</th><th>Severity</th>
                <th>Failure Type</th><th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {failures.map((f: any) => (
                <tr key={f.id}>
                  <td className="max-w-xs truncate font-mono text-xs" title={f.input_preview}>
                    {f.input_preview?.slice(0, 100)}…
                  </td>
                  <td className="text-xs">
                    {f.ground_truth?.label || "—"}
                  </td>
                  <td className="font-mono text-xs">{f.category || "—"}</td>
                  <td className="font-mono text-xs">{f.severity || "—"}</td>
                  <td><span className="badge badge-red">{f.failure_type}</span></td>
                  <td className="font-mono text-xs">{f.latency_ms.toFixed(1)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
