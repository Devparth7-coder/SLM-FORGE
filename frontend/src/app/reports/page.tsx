"use client";
import { useEffect, useState, useSearchParams } from "react";
import { api } from "@/lib/api";
import { FileText, Download } from "lucide-react";

export default function ReportsPage() {
  const params = useSearchParams();
  const expId = params.get("experiment");
  const [reports, setReports] = useState<any[]>([]);
  useEffect(() => {
    api.listReports(expId || undefined).then(setReports).catch(() => {});
  }, [expId]);
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold">Reports</h1>
      <p className="text-sm text-fg-muted">Reproducible experiment reports (JSON/Markdown/HTML).</p>
      {reports.length === 0 ? (
        <div className="card py-16 text-center">
          <FileText className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No reports generated yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {reports.map((r: any) => (
            <div key={r.id} className="card p-4 flex items-start justify-between">
              <div>
                <div className="font-medium">{r.title}</div>
                <div className="text-xs text-fg-subtle uppercase mt-1">{r.report_type}</div>
                <div className="text-xs text-fg-muted font-mono mt-1">
                  {r.size_bytes ? `${Math.round(r.size_bytes / 1024)} KB` : ""}
                </div>
              </div>
              <a
                href={`http://localhost:8000/api/v1/artifacts/${r.id}/download`}
                target="_blank"
                className="btn btn-sm"
              >
                <Download className="w-3 h-3" />
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
