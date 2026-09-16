"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ShieldCheck } from "lucide-react";

export default function DataQualityPage() {
  const [datasets, setDatasets] = useState<any[]>([]);
  useEffect(() => {
    api.listDatasets().then(setDatasets).catch(() => {});
  }, []);
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold">Data Quality</h1>
      <p className="text-sm text-fg-muted">Quality reports: duplicates, leakage, label balance, malformed samples.</p>
      {datasets.length === 0 ? (
        <div className="card py-16 text-center">
          <ShieldCheck className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No datasets to inspect.</p>
        </div>
      ) : (
        datasets.map((d: any) =>
          d.versions?.map((v: any) => (
            <div key={v.id} className="card p-4 space-y-3">
              <div className="flex justify-between">
                <div className="font-medium">{d.name} <span className="text-fg-subtle font-mono text-xs ml-2">{v.version}</span></div>
                <div className="text-xs font-mono text-fg-subtle">{v.sample_count} samples</div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                <ReportMetric label="Train/Val/Test" value={`${v.train_count}/${v.val_count}/${v.test_count}`} />
                <ReportMetric label="Duplicates removed" value={v.duplicates_removed} />
                <ReportMetric label="Invalid removed" value={v.invalid_removed} />
                <ReportMetric label="Hash" value={v.content_hash.slice(0, 12) + "…"} mono />
              </div>
            </div>
          )),
        )
      )}
    </div>
  );
}

function ReportMetric({ label, value, mono }: { label: string; value: any; mono?: boolean }) {
  return (
    <div>
      <div className="text-xs text-fg-subtle uppercase">{label}</div>
      <div className={`mt-0.5 ${mono ? "font-mono text-sm" : "text-sm"}`}>{value}</div>
    </div>
  );
}
