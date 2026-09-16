"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Database, Upload, Plus, Loader2, Trash2 } from "lucide-react";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showIngest, setShowIngest] = useState(false);
  const [ingestName, setIngestName] = useState("");
  const [sourcePath, setSourcePath] = useState("demo_data/vulnerability_demo.json");
  const [isDemo, setIsDemo] = useState(true);
  const [ingesting, setIngesting] = useState(false);

  useEffect(() => {
    api.listDatasets().then(setDatasets).finally(() => setLoading(false));
  }, []);

  async function handleIngest() {
    setIngesting(true);
    try {
      await api.ingestDataset({
        name: ingestName,
        source_path: sourcePath,
        is_demo: isDemo,
        description: isDemo ? "DEMO DATASET - pipeline verification" : "",
      });
      const ds = await api.listDatasets();
      setDatasets(ds);
      setShowIngest(false);
      setIngestName("");
    } catch (e: any) {
      alert(e.message);
    } finally {
      setIngesting(false);
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Datasets</h1>
          <p className="text-sm text-fg-muted mt-1">
            Versioned datasets with quality reports and content hashing.
          </p>
        </div>
        <button
          onClick={() => setShowIngest(!showIngest)}
          className="btn btn-primary"
        >
          <Plus className="w-4 h-4" /> Ingest Dataset
        </button>
      </div>

      {showIngest && (
        <div className="card p-4 space-y-3">
          <h3 className="font-medium">Ingest New Dataset</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="label">Name</label>
              <input
                className="input"
                value={ingestName}
                onChange={(e) => setIngestName(e.target.value)}
                placeholder="my-dataset"
              />
            </div>
            <div>
              <label className="label">Source Path</label>
              <input
                className="input"
                value={sourcePath}
                onChange={(e) => setSourcePath(e.target.value)}
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isDemo}
              onChange={(e) => setIsDemo(e.target.checked)}
            />
            Mark as DEMO dataset
          </label>
          <div className="flex gap-2">
            <button
              onClick={handleIngest}
              disabled={!ingestName || ingesting}
              className="btn btn-primary"
            >
              {ingesting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
              {ingesting ? "Ingesting..." : "Ingest"}
            </button>
            <button onClick={() => setShowIngest(false)} className="btn">
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
        </div>
      ) : datasets.length === 0 ? (
        <div className="card py-16 text-center">
          <Database className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No datasets yet. Ingest one to begin.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="table-base">
            <thead>
              <tr>
                <th>Name</th>
                <th>Domain</th>
                <th>Versions</th>
                <th>Latest Samples</th>
                <th>Hash</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d: any) => {
                const latest = d.versions?.[0];
                return (
                  <tr key={d.id}>
                    <td>
                      <Link href={`/datasets/${d.id}`} className="hover:text-accent">
                        <span className="font-medium">{d.name}</span>
                      </Link>
                      {d.is_demo && (
                        <span className="badge badge-yellow ml-2">DEMO</span>
                      )}
                    </td>
                    <td className="text-fg-muted text-xs">{d.domain}</td>
                    <td className="font-mono text-xs">{d.versions?.length || 0}</td>
                    <td className="font-mono text-xs">
                      {latest ? latest.sample_count : "—"}
                    </td>
                    <td className="font-mono text-xs text-fg-subtle">
                      {latest ? latest.content_hash.slice(0, 12) + "…" : "—"}
                    </td>
                    <td>
                      <Link href={`/datasets/${d.id}`} className="btn btn-sm">
                        Inspect
                      </Link>
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
