"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/ui/MetricCard";
import { Loader2, Play, XCircle, FileText, ShieldAlert, RefreshCw } from "lucide-react";

export default function ExperimentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [exp, setExp] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    const [e, c] = await Promise.all([
      api.getExperiment(id),
      api.getComparison(id).catch(() => null),
    ]);
    setExp(e);
    setComparison(c);
    setLoading(false);
    setRefreshing(false);
  }

  useEffect(() => {
    load();
    const interval = setInterval(() => {
      if (exp?.status === "RUNNING" || exp?.status === "QUEUED") {
        setRefreshing(true);
        load();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [id]);

  async function start() {
    await api.startExperiment(id);
    load();
  }
  async function cancel() {
    await api.cancelExperiment(id);
    load();
  }
  async function genReport() {
    await api.generateReports({ experiment_id: id, formats: ["json", "markdown", "html"] });
    alert("Reports generated");
  }
  async function runRobust() {
    await api.runRobustness(id, true);
    load();
  }

  if (loading)
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-accent" />
      </div>
    );

  const baselineEval = exp.evaluation_runs?.find((e: any) => e.is_baseline);
  const finetunedEval = exp.evaluation_runs?.find((e: any) => !e.is_baseline);
  const bm = baselineEval?.metrics_json || {};
  const fm = finetunedEval?.metrics_json || {};

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-fg-subtle uppercase tracking-wider font-mono">
            Experiment
          </div>
          <h1 className="text-xl font-semibold mt-1">{exp.name}</h1>
          <div className="flex gap-3 mt-2 text-xs font-mono text-fg-muted">
            <span>ID: {exp.id}</span>
            <span>Seed: {exp.seed}</span>
            <span>Git: {(exp.git_commit || "N/A").slice(0, 8)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {exp.status === "QUEUED" && (
            <button onClick={start} className="btn btn-primary">
              <Play className="w-4 h-4" /> Start
            </button>
          )}
          {exp.status === "RUNNING" && (
            <button onClick={cancel} className="btn btn-danger">
              <XCircle className="w-4 h-4" /> Cancel
            </button>
          )}
          {exp.status === "COMPLETED" && (
            <>
              <button onClick={runRobust} className="btn">
                <ShieldAlert className="w-4 h-4" /> Run Robustness
              </button>
              <button onClick={genReport} className="btn btn-primary">
                <FileText className="w-4 h-4" /> Generate Report
              </button>
            </>
          )}
          <button onClick={load} className="btn" disabled={refreshing}>
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Status card */}
      <div className="card p-4 flex items-center gap-6">
        <div>
          <div className="metric-label">Status</div>
          <div
            className={`text-lg font-semibold ${
              exp.status === "COMPLETED"
                ? "text-accent-success"
                : exp.status === "FAILED"
                  ? "text-accent-danger"
                  : exp.status === "RUNNING"
                    ? "text-accent"
                    : "text-fg-muted"
            }`}
          >
            {exp.status}
            {refreshing && <Loader2 className="w-4 h-4 inline ml-2 animate-spin" />}
          </div>
        </div>
        {exp.error_message && (
          <div className="text-accent-danger text-sm font-mono bg-accent-danger/10 border border-accent-danger/30 rounded p-2 flex-1">
            {exp.error_message}
          </div>
        )}
      </div>

      {/* Key metrics */}
      {(baselineEval || finetunedEval) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Base Accuracy"
            value={bm.accuracy != null ? bm.accuracy.toFixed(3) : "—"}
          />
          <MetricCard
            label="FT Accuracy"
            value={fm.accuracy != null ? fm.accuracy.toFixed(3) : "—"}
            accent={fm.accuracy > bm.accuracy ? "success" : fm.accuracy < bm.accuracy ? "danger" : "default"}
          />
          <MetricCard
            label="Base Macro F1"
            value={bm.macro_f1 != null ? bm.macro_f1.toFixed(3) : "—"}
          />
          <MetricCard
            label="FT Macro F1"
            value={fm.macro_f1 != null ? fm.macro_f1.toFixed(3) : "—"}
            accent={fm.macro_f1 > bm.macro_f1 ? "success" : fm.macro_f1 < bm.macro_f1 ? "danger" : "default"}
          />
        </div>
      )}

      {/* Comparison table */}
      {comparison?.metrics?.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="font-medium">Base vs Fine-Tuned Comparison</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th className="text-right">Base</th>
                  <th className="text-right">Fine-Tuned</th>
                  <th className="text-right">Δ</th>
                </tr>
              </thead>
              <tbody>
                {comparison.metrics.map((m: any) => (
                  <tr key={m.name}>
                    <td className="font-mono text-xs">
                      {m.name}
                      {m.note && (
                        <div className="text-[10px] text-fg-subtle">{m.note}</div>
                      )}
                    </td>
                    <td className="text-right font-mono">
                      {m.base_value != null ? m.base_value.toFixed(4) : "—"}
                    </td>
                    <td className="text-right font-mono">
                      {m.finetuned_value != null ? m.finetuned_value.toFixed(4) : "—"}
                    </td>
                    <td
                      className={`text-right font-mono ${
                        m.delta == null
                          ? "text-fg-subtle"
                          : m.delta > 0
                            ? "text-accent-success"
                            : m.delta < 0
                              ? "text-accent-danger"
                              : "text-fg"
                      }`}
                    >
                      {m.delta != null ? (m.delta > 0 ? "+" : "") + m.delta.toFixed(4) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Training config */}
      <div className="card">
        <div className="card-header">
          <h3 className="font-medium">Training Configuration</h3>
        </div>
        <div className="card-body">
          <pre className="text-xs font-mono bg-bg-muted p-3 rounded overflow-auto">
            {JSON.stringify(exp.training_config || {}, null, 2)}
          </pre>
        </div>
      </div>

      <div className="text-xs text-fg-subtle">
        See <Link href={`/failures?experiment=${id}`} className="text-accent underline">Failures</Link>
        {" · "}
        <Link href={`/reports?experiment=${id}`} className="text-accent underline">Reports</Link>
      </div>
    </div>
  );
}
