"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MetricCard } from "@/components/ui/MetricCard";
import { api } from "@/lib/api";
import {
  Play,
  Database,
  Cpu,
  FlaskConical,
  Plus,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertCircle,
} from "lucide-react";

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { cls: string; icon: any; label: string }> = {
    QUEUED: { cls: "badge-gray", icon: Clock, label: "Queued" },
    RUNNING: { cls: "badge-blue", icon: Loader2, label: "Running" },
    COMPLETED: { cls: "badge-green", icon: CheckCircle2, label: "Completed" },
    FAILED: { cls: "badge-red", icon: XCircle, label: "Failed" },
    CANCELLED: { cls: "badge-yellow", icon: AlertCircle, label: "Cancelled" },
    PENDING: { cls: "badge-gray", icon: Clock, label: "Pending" },
  };
  const c = cfg[status] || cfg.QUEUED;
  const Icon = c.icon;
  return (
    <span className={`badge ${c.cls}`}>
      <Icon className="w-3 h-3" />
      {c.label}
    </span>
  );
}

export default function OverviewPage() {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [datasets, setDatasets] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.listExperiments(),
      api.listDatasets(),
      api.listModels(),
      api.health(),
    ])
      .then(([exps, ds, ms, h]) => {
        setExperiments(exps);
        setDatasets(ds);
        setModels(ms);
        setHealth(h);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-accent" />
      </div>
    );
  }

  const latestExp = experiments[0];
  const latestDs = datasets[0];
  const latestModel = models[0];
  const running = experiments.filter((e) => e.status === "RUNNING").length;
  const completed = experiments.filter((e) => e.status === "COMPLETED").length;
  const baselineEval = latestExp?.evaluation_runs?.find(
    (e: any) => e.is_baseline,
  );
  const finetunedEval = latestExp?.evaluation_runs?.find(
    (e: any) => !e.is_baseline,
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">Overview</h1>
          <p className="text-sm text-fg-muted mt-1">
            Small Language Model Fine-Tuning & Evaluation Laboratory
          </p>
        </div>
        {latestExp && (
          <Link href={`/experiments/${latestExp.id}`} className="btn btn-primary">
            <FlaskConical className="w-4 h-4" />
            Open Current Experiment
          </Link>
        )}
      </div>

      {experiments.length === 0 ? (
        <div className="card">
          <div className="card-body py-16 text-center">
            <div className="text-3xl font-bold tracking-widest text-fg-subtle mb-4">
              NO EXPERIMENTS YET
            </div>
            <p className="text-sm text-fg-muted max-w-md mx-auto mb-8">
              Begin by ingesting a dataset, registering a base model, and
              running a baseline evaluation. Fine-tuning follows.
            </p>
            <div className="flex items-center justify-center gap-3 flex-wrap">
              <Link href="/datasets" className="btn btn-primary">
                <Database className="w-4 h-4" />
                Create Dataset
              </Link>
              <Link href="/models" className="btn">
                <Cpu className="w-4 h-4" />
                Register Model
              </Link>
              <Link href="/experiments" className="btn">
                <Play className="w-4 h-4" />
                Run Baseline
              </Link>
              <Link href="/experiments" className="btn">
                <Plus className="w-4 h-4" />
                Start Experiment
              </Link>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Status cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="Experiments"
              value={experiments.length}
              sublabel={`${completed} completed, ${running} running`}
            />
            <MetricCard label="Datasets" value={datasets.length} />
            <MetricCard label="Models" value={models.length} />
            <MetricCard
              label="Hardware"
              value={health?.gpu_available ? "GPU" : "CPU"}
              accent={health?.gpu_available ? "success" : "warning"}
              sublabel={health?.gpu_info?.name || "CPU-only"}
            />
          </div>

          {/* Current experiment */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card">
              <div className="card-header">
                <h2 className="section-title">Current Experiment</h2>
                <StatusBadge status={latestExp?.status} />
              </div>
              <div className="card-body space-y-3 text-sm">
                <div>
                  <div className="text-fg-subtle text-xs uppercase">Name</div>
                  <div className="font-medium">{latestExp?.name}</div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-fg-subtle text-xs uppercase">Seed</div>
                    <div className="font-mono">{latestExp?.seed}</div>
                  </div>
                  <div>
                    <div className="text-fg-subtle text-xs uppercase">Git</div>
                    <div className="font-mono text-xs">
                      {(latestExp?.git_commit || "N/A").slice(0, 8)}
                    </div>
                  </div>
                </div>
                <div>
                  <div className="text-fg-subtle text-xs uppercase mb-2">
                    Training Status
                  </div>
                  {latestExp?.training_run ? (
                    <div className="flex items-center justify-between text-xs">
                      <span>
                        Step {latestExp.training_run.current_step}/
                        {latestExp.training_run.total_steps || "?"}
                      </span>
                      <StatusBadge status={latestExp.training_run.status} />
                    </div>
                  ) : (
                    <div className="text-fg-subtle text-xs">
                      No training run (baseline-only)
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Base vs Fine-tuned */}
            <div className="card">
              <div className="card-header">
                <h2 className="section-title">Base vs Fine-Tuned</h2>
              </div>
              <div className="card-body">
                {baselineEval || finetunedEval ? (
                  <table className="table-base">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th className="text-right">Base</th>
                        <th className="text-right">Fine-tuned</th>
                        <th className="text-right">Δ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {["accuracy", "f1", "macro_f1", "json_validity_rate"].map(
                        (m) => {
                          const bv = baselineEval?.metrics_json?.[m];
                          const fv = finetunedEval?.metrics_json?.[m];
                          const delta =
                            bv != null && fv != null ? fv - bv : null;
                          return (
                            <tr key={m}>
                              <td className="font-mono text-xs">{m}</td>
                              <td className="text-right font-mono">
                                {bv != null ? bv.toFixed(3) : "—"}
                              </td>
                              <td className="text-right font-mono">
                                {fv != null ? fv.toFixed(3) : "—"}
                              </td>
                              <td
                                className={`text-right font-mono ${
                                  delta == null
                                    ? "text-fg-subtle"
                                    : delta > 0
                                      ? "text-accent-success"
                                      : delta < 0
                                        ? "text-accent-danger"
                                        : "text-fg"
                                }`}
                              >
                                {delta != null ? (delta > 0 ? "+" : "") + delta.toFixed(3) : "—"}
                              </td>
                            </tr>
                          );
                        },
                      )}
                    </tbody>
                  </table>
                ) : (
                  <div className="text-center py-6 text-fg-subtle text-sm">
                    No evaluation results yet. Run baseline evaluation first.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Latest dataset/model */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="card">
              <div className="card-header">
                <h3 className="font-medium">Latest Dataset</h3>
              </div>
              <div className="card-body text-sm space-y-2">
                {latestDs ? (
                  <>
                    <div className="font-medium">{latestDs.name}</div>
                    <div className="text-fg-muted">
                      {latestDs.description}
                    </div>
                    {latestDs.versions?.[0] && (
                      <div className="flex gap-4 text-xs text-fg-subtle font-mono mt-2">
                        <span>v{latestDs.versions[0].version}</span>
                        <span>{latestDs.versions[0].sample_count} samples</span>
                        <span>
                          hash: {latestDs.versions[0].content_hash.slice(0, 12)}…
                        </span>
                      </div>
                    )}
                    {latestDs.is_demo && (
                      <div className="badge badge-yellow mt-2">DEMO DATASET</div>
                    )}
                  </>
                ) : (
                  <div className="text-fg-subtle">No datasets yet.</div>
                )}
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <h3 className="font-medium">Latest Model</h3>
              </div>
              <div className="card-body text-sm space-y-2">
                {latestModel ? (
                  <>
                    <div className="font-medium">{latestModel.name}</div>
                    {latestModel.versions?.[0] && (
                      <div className="flex gap-4 text-xs text-fg-subtle font-mono mt-2">
                        <span>{latestModel.versions[0].hf_model_id}</span>
                        <span>{latestModel.versions[0].quantization || "fp"}</span>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-fg-subtle">No models registered.</div>
                )}
              </div>
            </div>
          </div>

          {/* Recent experiments */}
          <div className="card">
            <div className="card-header">
              <h3 className="font-medium">Recent Experiments</h3>
              <Link href="/experiments" className="btn btn-sm">
                View all
              </Link>
            </div>
            <div className="overflow-x-auto">
              <table className="table-base">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Seed</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {experiments.slice(0, 8).map((e: any) => (
                    <tr key={e.id} className="cursor-pointer">
                      <td>
                        <Link
                          href={`/experiments/${e.id}`}
                          className="text-fg hover:text-accent"
                        >
                          {e.name}
                        </Link>
                      </td>
                      <td>
                        <StatusBadge status={e.status} />
                      </td>
                      <td className="font-mono text-xs">{e.seed}</td>
                      <td className="text-fg-muted text-xs font-mono">
                        {new Date(e.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
