const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let err: any;
    try {
      err = await res.json();
    } catch {
      err = { message: res.statusText };
    }
    throw new Error(err.message || err.error_code || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => request<any>("/health"),
  hardware: () => request<any>("/hardware"),

  // Datasets
  listDatasets: () => request<any[]>("/datasets"),
  ingestDataset: (body: any) =>
    request<any>("/datasets/ingest", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getDataset: (id: string) => request<any>(`/datasets/${id}`),
  getDatasetQuality: (id: string) => request<any[]>(`/datasets/${id}/quality`),
  getDatasetStats: (id: string, versionId?: string) =>
    request<any>(
      `/datasets/${id}/statistics${versionId ? `?version_id=${versionId}` : ""}`,
    ),
  listSamples: (id: string, versionId?: string, split?: string) => {
    const params = new URLSearchParams();
    if (versionId) params.set("version_id", versionId);
    if (split) params.set("split", split);
    const qs = params.toString();
    return request<any[]>(`/datasets/${id}/samples${qs ? `?${qs}` : ""}`);
  },

  // Models
  listModels: () => request<any[]>("/models"),
  registerModel: (body: any) =>
    request<any>("/models", { method: "POST", body: JSON.stringify(body) }),
  getModel: (id: string) => request<any>(`/models/${id}`),

  // Experiments
  listExperiments: (status?: string) =>
    request<any[]>(`/experiments${status ? `?status=${status}` : ""}`),
  createExperiment: (body: any) =>
    request<any>("/experiments", { method: "POST", body: JSON.stringify(body) }),
  getExperiment: (id: string) => request<any>(`/experiments/${id}`),
  startExperiment: (id: string, dryRun = false) =>
    request<any>(
      `/experiments/${id}/start${dryRun ? "?dry_run=true" : ""}`,
      { method: "POST" },
    ),
  cancelExperiment: (id: string) =>
    request<any>(`/experiments/${id}/cancel`, { method: "POST" }),
  getComparison: (id: string) => request<any>(`/experiments/${id}/comparison`),
  runRobustness: (id: string, isBaseline = true, maxSamples?: number) => {
    const params = new URLSearchParams();
    params.set("is_baseline", String(isBaseline));
    if (maxSamples) params.set("max_samples", String(maxSamples));
    return request<any>(`/experiments/${id}/robustness?${params}`, {
      method: "POST",
    });
  },

  // Evaluations
  listEvaluations: (experimentId?: string) =>
    request<any[]>(
      `/evaluations${experimentId ? `?experiment_id=${experimentId}` : ""}`,
    ),
  getEvaluation: (id: string) => request<any>(`/evaluations/${id}`),
  getEvalMetrics: (id: string) => request<any>(`/evaluations/${id}/metrics`),
  getPredictions: (id: string, limit = 100, correct?: boolean) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (correct !== undefined) params.set("correct", String(correct));
    return request<any[]>(`/evaluations/${id}/predictions?${params}`);
  },

  // Failures
  listFailures: (experimentId?: string, failureType?: string) => {
    const params = new URLSearchParams();
    if (experimentId) params.set("experiment_id", experimentId);
    if (failureType) params.set("failure_type", failureType);
    return request<any[]>(`/failures${params.toString() ? `?${params}` : ""}`);
  },
  getFailure: (id: string) => request<any>(`/failures/${id}`),

  // Robustness
  listRobustness: (experimentId?: string) =>
    request<any[]>(
      `/robustness${experimentId ? `?experiment_id=${experimentId}` : ""}`,
    ),

  // Reports
  listReports: (experimentId?: string) =>
    request<any[]>(
      `/reports${experimentId ? `?experiment_id=${experimentId}` : ""}`,
    ),
  generateReports: (body: any) =>
    request<any[]>("/reports/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
