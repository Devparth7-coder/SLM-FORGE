"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Cpu, Plus, Loader2 } from "lucide-react";

export default function ModelsPage() {
  const [models, setModels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [show, setShow] = useState(false);
  const [name, setName] = useState("Qwen-0.5B-Instruct");
  const [hfId, setHfId] = useState("Qwen/Qwen2.5-0.5B-Instruct");
  const [quant, setQuant] = useState("4bit");

  useEffect(() => {
    api.listModels().then(setModels).finally(() => setLoading(false));
  }, []);

  async function handleRegister() {
    await api.registerModel({
      name, hf_model_id: hfId, quantization: quant || null,
    });
    setModels(await api.listModels());
    setShow(false);
  }

  const paramFmt = (n?: number) => {
    if (!n) return "—";
    if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(0)}M`;
    return String(n);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Models</h1>
          <p className="text-sm text-fg-muted mt-1">
            Registry of base models and fine-tuned adapters.
          </p>
        </div>
        <button onClick={() => setShow(!show)} className="btn btn-primary">
          <Plus className="w-4 h-4" /> Register Model
        </button>
      </div>

      {show && (
        <div className="card p-4 space-y-3">
          <h3 className="font-medium">Register Base Model</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="label">Display Name</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="label">HuggingFace ID</label>
              <input className="input font-mono" value={hfId} onChange={(e) => setHfId(e.target.value)} />
            </div>
            <div>
              <label className="label">Quantization</label>
              <select className="select" value={quant} onChange={(e) => setQuant(e.target.value)}>
                <option value="">None (fp16/bf16)</option>
                <option value="4bit">4-bit (QLoRA)</option>
                <option value="8bit">8-bit</option>
              </select>
            </div>
          </div>
          <button onClick={handleRegister} className="btn btn-primary">
            Register
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
        </div>
      ) : models.length === 0 ? (
        <div className="card py-16 text-center">
          <Cpu className="w-12 h-12 mx-auto text-fg-subtle mb-3" />
          <p className="text-fg-muted">No models registered yet.</p>
          <p className="text-xs text-fg-subtle mt-1">
            Register a base model like Qwen/Qwen2.5-0.5B-Instruct to start.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {models.map((m: any) => (
            <div key={m.id} className="card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium">{m.name}</div>
                  <div className="text-xs text-fg-muted font-mono mt-1">
                    {m.versions?.[0]?.hf_model_id || "—"}
                  </div>
                </div>
                <span className="badge badge-blue">{m.task_type}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                <div>
                  <div className="text-xs text-fg-subtle uppercase">Parameters</div>
                  <div className="font-mono text-sm mt-1">
                    {m.versions?.[0]?.parameter_count_str || paramFmt(m.versions?.[0]?.parameter_count) || "?"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-fg-subtle uppercase">Quant</div>
                  <div className="font-mono text-sm mt-1">
                    {m.versions?.[0]?.quantization || "fp"}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-fg-subtle uppercase">Versions</div>
                  <div className="font-mono text-sm mt-1">{m.versions?.length || 0}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
