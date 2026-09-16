"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { FlaskConical, Plus, Loader2, Play, Clock, CheckCircle2, XCircle } from "lucide-react";

const statusCfg: Record<string, { cls: string; icon: any }> = {
  QUEUED: { cls: "badge-gray", icon: Clock },
  RUNNING: { cls: "badge-blue", icon: Loader2 },
  COMPLETED: { cls: "badge-green", icon: CheckCircle2 },
  FAILED: { cls: "badge-red", icon: XCircle },
  CANCELLED: { cls: "badge-yellow", icon: XCircle },
};

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [datasets, setDatasets] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [dsVersionId, setDsVersionId] = useState("");
  const [modelVersionId, setModelVersionId] = useState("");
  const [dryRun, setDryRun] = useState(true);

  useEffect(() => {
    Promise.all([api.listExperiments(), api.listDatasets(), api.listModels()]).then(
      ([e, d, m]) => {
        setExperiments(e);
        setDatasets(d);
        setModels(m);
        if (d.length && d[0].versions?.length) setDsVersionId(d[0].versions[0].id);
        if (m.length && m[0].versions?.length) setModelVersionId(m[0].versions[0].id);
        setLoading(false);
      },
    );
  }, []);

  async function createAndStart() {
    const exp = await api.createExperiment({
      name,
      dataset_version_id: dsVersionId,
      base_model_version_id: modelVersionId,
      seed: 42,
      training_config: { method: "qlora" },
      evaluation_config: {},
      tags: {},
    });
    await api.startExperiment(exp.id, dryRun);
    setShowCreate(false);
    setExperiments(await api.listExperiments());
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Experiments</h1>
          <p className="text-sm text-fg-muted mt-1">
            Versioned, reproducible training and evaluation runs.
          </p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)} className="btn btn-primary">
          <Plus className="w-4 h-4" /> New Experiment
        </button>
      </div>

      {showCreate && (
        <div className="card p-4 space-y-3">
          <h3 className="font-medium">New Experiment</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="label">Name</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="qlora-vuln-r16" />
            </div>
            <div>
              <label className="label">Dataset Version</label>
              <select className="select" value={dsVersionId} onChange={(e) => setDsVersionId(e.target.value)}>
                {datasets.map((d: any) =>
                  d.versions?.map((v: any) => (
                    <option key={v.id} value={v.id}>
                      {d.name} / {v.version}
                    </option>
                  )),
                )}
              </select>
            </div>
            <div>
              <label className="label">Base Model Version</label>
              <select className="select" value={modelVersionId} onChange={(e) => setModelVersionId(e.target.value)}>
                {models.map((m: any) =>
                  m.versions?.map((v: any) => (
                    <option key={v.id} value={v.id}>
                      {m.name} / {v.hf_model_id} @ {v.revision}
                    </option>
                  )),
                )}
              </select>
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
            Dry-run mode (validate pipeline without real training)
          </label>
          <button onClick={createAndStart} disabled={!name} className="btn btn-primary">
            <Play className="w-4 h-4" /> Create & Start
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
        </div>
      ) : experiments.length === 0 ? (
        <div className="card py-16 text-center">
          <FlaskConical className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No experiments yet. Create one to begin.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-base">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Seed</th>
                <th>Method</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((e: any) => {
                const sc = statusCfg[e.status] || statusCfg.QUEUED;
                const Icon = sc.icon;
                return (
                  <tr key={e.id}>
                    <td>
                      <Link href={`/experiments/${e.id}`} className="hover:text-accent font-medium">
                        {e.name}
                      </Link>
                    </td>
                    <td>
                      <span className={`badge ${sc.cls}`}>
                        <Icon className={`w-3 h-3 ${e.status === "RUNNING" ? "animate-spin" : ""}`} />
                        {e.status}
                      </span>
                    </td>
                    <td className="font-mono text-xs">{e.seed}</td>
                    <td className="font-mono text-xs">
                      {e.training_config?.method || "baseline"}
                    </td>
                    <td className="text-fg-muted text-xs font-mono">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
