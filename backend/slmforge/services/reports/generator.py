"""Experiment report generation (JSON, Markdown, HTML)."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from slmforge.core.config import settings
from slmforge.core.logging import get_logger
from slmforge.db.models.artifact import Artifact, ReportEntry
from slmforge.db.models.dataset import Dataset, DatasetQualityReport, DatasetVersion
from slmforge.db.models.experiment import EvaluationRun, Experiment, RobustnessRun, TrainingRun
from slmforge.db.models.model import ModelRegistry, ModelVersion
from slmforge.services.evaluation.metrics import compare_metrics, MetricReport
from slmforge.storage import get_storage_backend
from slmforge.utils.env import get_cuda_info, get_package_versions, get_python_version, get_platform_info
from slmforge.utils.git import get_git_commit, get_git_branch

logger = get_logger(__name__)


class ReportService:
    """Generate reproducible experiment reports."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = get_storage_backend()

    def generate_all(
        self,
        experiment_id: str,
        formats: Optional[List[str]] = None,
    ) -> List[ReportEntry]:
        formats = formats or ["json", "markdown", "html"]
        exp = self.db.get(Experiment, experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        context = self._build_context(exp)

        reports: List[ReportEntry] = []
        for fmt in formats:
            if fmt == "json":
                reports.append(self._generate_json(exp, context))
            elif fmt == "markdown":
                reports.append(self._generate_markdown(exp, context))
            elif fmt == "html":
                reports.append(self._generate_html(exp, context))
        return reports

    def _build_context(self, exp: Experiment) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {
            "experiment": exp.to_dict() if hasattr(exp, "to_dict") else {
                "id": exp.id, "name": exp.name, "status": exp.status,
                "seed": exp.seed, "git_commit": exp.git_commit,
                "training_config": exp.training_config,
                "evaluation_config": exp.evaluation_config,
                "created_at": exp.created_at.isoformat() if exp.created_at else None,
                "started_at": exp.started_at, "completed_at": exp.completed_at,
                "tags": exp.tags, "error_message": exp.error_message,
                "wandb_run_url": exp.wandb_run_url,
            },
            "environment": {
                "python": get_python_version(),
                "packages": get_package_versions(),
                "platform": get_platform_info(),
                "cuda": get_cuda_info(),
                "git_commit": get_git_commit(),
                "git_branch": get_git_branch(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        # Dataset
        if exp.dataset_version_id:
            dsv = self.db.get(DatasetVersion, exp.dataset_version_id)
            if dsv:
                ds = self.db.get(Dataset, dsv.dataset_id)
                ctx["dataset"] = {
                    "id": ds.id if ds else None,
                    "name": ds.name if ds else None,
                    "version": dsv.version,
                    "content_hash": dsv.content_hash,
                    "sample_count": dsv.sample_count,
                    "train_count": dsv.train_count,
                    "val_count": dsv.val_count,
                    "test_count": dsv.test_count,
                    "raw_count": dsv.raw_count,
                    "is_demo": ds.is_demo if ds else False,
                }
                qr = (
                    self.db.query(DatasetQualityReport)
                    .filter(DatasetQualityReport.version_id == dsv.id)
                    .order_by(DatasetQualityReport.created_at.desc())
                    .first()
                )
                if qr:
                    ctx["data_quality"] = {
                        "duplicate_rate": qr.duplicate_rate,
                        "label_distribution": qr.label_distribution,
                        "issues": qr.issues,
                    }

        # Models
        if exp.base_model_version_id:
            bv = self.db.get(ModelVersion, exp.base_model_version_id)
            if bv:
                bm = self.db.get(ModelRegistry, bv.model_id)
                ctx["base_model"] = {
                    "name": bm.name if bm else None,
                    "hf_id": bv.hf_model_id,
                    "revision": bv.revision,
                    "quantization": bv.quantization,
                    "param_count": bv.parameter_count_str,
                }
        if exp.fine_tuned_model_version_id:
            fv = self.db.get(ModelVersion, exp.fine_tuned_model_version_id)
            if fv:
                fm = self.db.get(ModelRegistry, fv.model_id)
                ctx["finetuned_model"] = {
                    "name": fm.name if fm else None,
                    "adapter_type": fv.adapter_type,
                    "adapter_size_bytes": fv.adapter_size_bytes,
                    "trainable_params": fv.adapter_trainable_params,
                }

        # Evaluations
        evals = (
            self.db.query(EvaluationRun)
            .filter(EvaluationRun.experiment_id == exp.id)
            .all()
        )
        ctx["evaluations"] = []
        baseline_eval = None
        finetuned_eval = None
        for ev in evals:
            d = {
                "id": ev.id, "is_baseline": ev.is_baseline, "status": ev.status,
                "n_samples": ev.sample_count, "metrics": ev.metrics_json,
                "confusion_matrix": ev.confusion_matrix,
                "latency": ev.latency_stats_ms,
                "errors": ev.error_distribution,
            }
            ctx["evaluations"].append(d)
            if ev.is_baseline:
                baseline_eval = ev
            else:
                finetuned_eval = ev

        # Comparison
        if baseline_eval and finetuned_eval:
            bm = MetricReport(**{**MetricReport().to_dict(), **baseline_eval.metrics_json})
            fm = MetricReport(**{**MetricReport().to_dict(), **finetuned_eval.metrics_json})
            ctx["comparison"] = compare_metrics(bm, fm)
        else:
            ctx["comparison"] = []

        # Training
        tr = self.db.query(TrainingRun).filter(TrainingRun.experiment_id == exp.id).first()
        if tr:
            ctx["training"] = {
                "status": tr.status,
                "method": tr.method,
                "total_steps": tr.total_steps,
                "total_epochs": tr.total_epochs,
                "best_val_loss": tr.best_val_loss,
                "elapsed_seconds": tr.elapsed_seconds,
                "final_adapter_path": tr.final_adapter_path,
                "error_message": tr.error_message,
                "metrics_history_count": len(tr.metrics_history),
            }

        # Robustness
        rob = (
            self.db.query(RobustnessRun)
            .filter(RobustnessRun.experiment_id == exp.id)
            .all()
        )
        ctx["robustness"] = [
            {"type": r.perturbation_type, "status": r.status,
             "robustness_score": r.robustness_score,
             "degradation": r.performance_degradation,
             "metrics": r.metrics_json}
            for r in rob
        ]

        return ctx

    def _generate_json(self, exp: Experiment, ctx: Dict[str, Any]) -> ReportEntry:
        payload = json.dumps(ctx, indent=2, default=str)
        key = f"reports/{exp.id}/report.json"
        self.storage.store_bytes(key, payload.encode("utf-8"), content_type="application/json")
        entry = ReportEntry(
            experiment_id=exp.id, report_type="json", title=f"Report: {exp.name} (JSON)",
            storage_path=key, size_bytes=len(payload),
            metadata={"format": "json"},
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def _generate_markdown(self, exp: Experiment, ctx: Dict[str, Any]) -> ReportEntry:
        md = self._render_markdown(ctx)
        b = md.encode("utf-8")
        key = f"reports/{exp.id}/report.md"
        self.storage.store_bytes(key, b, content_type="text/markdown")
        entry = ReportEntry(
            experiment_id=exp.id, report_type="markdown", title=f"Report: {exp.name} (Markdown)",
            storage_path=key, size_bytes=len(b), metadata={"format": "markdown"},
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def _generate_html(self, exp: Experiment, ctx: Dict[str, Any]) -> ReportEntry:
        md_content = self._render_markdown(ctx)
        html_body = self._markdown_to_simple_html(md_content)
        b = html_body.encode("utf-8")
        key = f"reports/{exp.id}/report.html"
        self.storage.store_bytes(key, b, content_type="text/html")
        entry = ReportEntry(
            experiment_id=exp.id, report_type="html", title=f"Report: {exp.name} (HTML)",
            storage_path=key, size_bytes=len(b), metadata={"format": "html"},
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def _render_markdown(self, ctx: Dict[str, Any]) -> str:
        exp = ctx["experiment"]
        ds = ctx.get("dataset", {})
        bm = ctx.get("base_model", {})
        fm = ctx.get("finetuned_model", {})
        tr = ctx.get("training")
        env = ctx["environment"]
        lines: List[str] = []
        w = lines.append

        w(f"# SLM-FORGE Experiment Report")
        w("")
        w(f"**Experiment:** {exp['name']}  ")
        w(f"**ID:** `{exp['id']}`  ")
        w(f"**Status:** {exp['status']}  ")
        w(f"**Generated:** {env['generated_at']}  ")
        w("")
        w("---")
        w("")

        # 1. Overview
        w("## 1. Experiment Overview")
        w("")
        w(f"- **Seed:** {exp['seed']}")
        w(f"- **Git commit:** `{exp.get('git_commit', 'N/A')}`")
        if exp.get("wandb_run_url"):
            w(f"- **W&B:** {exp['wandb_run_url']}")
        if exp.get("error_message"):
            w(f"- **Error:** ⚠ {exp['error_message']}")
        w("")

        # 2. Dataset
        w("## 2. Dataset")
        w("")
        w(f"- **Name:** {ds.get('name', 'N/A')}")
        w(f"- **Version:** {ds.get('version', 'N/A')}")
        w(f"- **Content hash:** `{ds.get('content_hash', 'N/A')}`")
        w(f"- **Samples:** {ds.get('sample_count', 'N/A')} (train {ds.get('train_count', '?')}, val {ds.get('val_count', '?')}, test {ds.get('test_count', '?')})")
        if ds.get("is_demo"):
            w("")
            w("> ⚠ **DEMO DATASET.** This dataset is labeled DEMO and is included only to verify the pipeline. "
              "Published performance claims must be generated from a valid evaluation dataset.")
        w("")

        # 3. Data Quality
        dq = ctx.get("data_quality")
        if dq:
            w("## 3. Data Quality")
            w("")
            w(f"- Duplicate rate: {dq['duplicate_rate']:.2%}")
            w(f"- Label distribution: `{json.dumps(dq['label_distribution'])}`")
            if dq.get("issues"):
                w("")
                w("### Issues")
                for issue in dq["issues"]:
                    w(f"- **{issue.get('severity', 'info')}** `{issue.get('code')}`: {issue.get('message')}")
            w("")

        # 4. Model
        w("## 4. Model")
        w("")
        w("### Base Model")
        w(f"- Name: {bm.get('name', 'N/A')}")
        w(f"- HF ID: `{bm.get('hf_id', 'N/A')}`")
        w(f"- Revision: {bm.get('revision', 'N/A')}")
        w(f"- Quantization: {bm.get('quantization', 'None')}")
        w(f"- Parameters: {bm.get('param_count', 'N/A')}")
        w("")
        if fm:
            w("### Fine-tuned Model")
            w(f"- Adapter type: {fm.get('adapter_type', 'N/A')}")
            w(f"- Adapter size: {fm.get('adapter_size_bytes', 'N/A')} bytes")
            w(f"- Trainable params: {fm.get('trainable_params', 'N/A')}")
            w("")

        # 5. Training
        w("## 5. Training Configuration")
        w("")
        tc = exp.get("training_config", {})
        w("```yaml")
        for k, v in tc.items():
            w(f"{k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}")
        w("```")
        w("")
        if tr:
            w(f"- **Status:** {tr['status']}")
            w(f"- **Method:** {tr['method']}")
            w(f"- **Best val loss:** {tr['best_val_loss']}")
            w(f"- **Elapsed:** {tr['elapsed_seconds']}s")
            if tr.get("error_message"):
                w(f"- **Error:** ⚠ {tr['error_message']}")
            w("")

        # 7/8. Results
        w("## 6-7. Baseline & Fine-tuned Results")
        w("")
        for ev in ctx["evaluations"]:
            label = "**BASELINE**" if ev["is_baseline"] else "**FINE-TUNED**"
            w(f"### {label} ({ev['status']})")
            m = ev.get("metrics", {})
            w(f"- Accuracy: {m.get('accuracy', 'N/A')}")
            w(f"- Precision: {m.get('precision', 'N/A')}")
            w(f"- Recall: {m.get('recall', 'N/A')}")
            w(f"- F1: {m.get('f1', 'N/A')}")
            w(f"- Macro F1: {m.get('macro_f1', 'N/A')}")
            w(f"- JSON validity: {m.get('json_validity_rate', 'N/A')}")
            w(f"- Latency (mean): {m.get('latency_mean_ms', 'N/A')} ms")
            w("")

        # 9. Comparison
        w("## 9. Comparison (Fine-tuned − Baseline)")
        w("")
        if ctx["comparison"]:
            w("| Metric | Base | Fine-tuned | Δ | Higher is better |")
            w("|--------|------|-----------|-----|-----------------|")
            for cmp in ctx["comparison"]:
                bv = f"{cmp['base_value']:.4f}" if cmp.get("base_value") is not None else "N/A"
                fv = f"{cmp['finetuned_value']:.4f}" if cmp.get("finetuned_value") is not None else "N/A"
                dv = f"{cmp['delta']:+.4f}" if cmp.get("delta") is not None else "N/A"
                hb = "✓" if cmp.get("higher_is_better") else "↓ (lower better)"
                w(f"| {cmp['name']} | {bv} | {fv} | {dv} | {hb} |")
        else:
            w("_Comparison requires both baseline and fine-tuned evaluations to complete._")
        w("")

        # 10. Robustness
        w("## 10. Robustness")
        w("")
        if ctx["robustness"]:
            w("| Perturbation | Status | Robustness Score | Degradation |")
            w("|-------------|--------|-----------------|-------------|")
            for r in ctx["robustness"]:
                rs = f"{r['robustness_score']:.3f}" if r.get("robustness_score") is not None else "N/A"
                dg = f"{r['degradation']:.4f}" if r.get("degradation") is not None else "N/A"
                w(f"| {r['type']} | {r['status']} | {rs} | {dg} |")
        else:
            w("_Robustness tests not yet run._")
        w("")

        # 13. Limitations
        w("## 13. Limitations")
        w("")
        w("- This report reflects a single experimental run.")
        w("- Results may vary with random seed, model revision, and hardware.")
        w("- Vulnerability detection is evaluated on the specific dataset used.")
        if ds.get("is_demo"):
            w("- **Demo dataset results are NOT valid evidence of real-world performance.**")
        w("- Always check confidence intervals and run multiple seeds for statistically meaningful conclusions.")
        w("")

        # 14. Reproduction
        w("## 14. Reproduce This Experiment")
        w("")
        w("```bash")
        w(f"slmforge experiment run \\")
        w(f"  --dataset-version {ds.get('version', 'N/A')} \\")
        w(f"  --base-model {bm.get('hf_id', 'N/A')}@{bm.get('revision', 'main')} \\")
        w(f"  --seed {exp['seed']}")
        w("```")
        w("")
        w("### Software Environment")
        w("")
        w(f"- Python: {env['python']}")
        w(f"- Platform: {env['platform'].get('system', 'N/A')} {env['platform'].get('machine', '')}")
        w(f"- CUDA available: {env['cuda'].get('cuda_available', False)}")
        w("")
        w("Key packages:")
        for pkg, ver in env.get("packages", {}).items():
            w(f"- {pkg}: {ver}")
        w("")

        return "\n".join(lines)

    def _markdown_to_simple_html(self, md: str) -> str:
        """Very small markdown-to-HTML conversion for reports (no external dependency)."""
        lines = md.split("\n")
        out: List[str] = []
        in_table = False
        in_code = False
        in_list = False

        out.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
        out.append("<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;"
                   "max-width:960px;margin:2rem auto;padding:0 1rem;color:#1a1a1a;line-height:1.6;}"
                   "h1,h2,h3{border-bottom:1px solid #e5e7eb;padding-bottom:0.3em;}"
                   "code{background:#f3f4f6;padding:0.2em 0.4em;border-radius:3px;font-size:0.9em;}"
                   "pre{background:#1e1e1e;color:#d4d4d4;padding:1rem;border-radius:6px;overflow-x:auto;}"
                   "pre code{background:none;color:inherit;padding:0;}"
                   "table{border-collapse:collapse;width:100%;margin:1rem 0;}"
                   "th,td{border:1px solid #e5e7eb;padding:0.5rem 0.75rem;text-align:left;}"
                   "th{background:#f9fafb;}"
                   "blockquote{border-left:4px solid #fbbf24;background:#fffbeb;margin:1rem 0;padding:0.5rem 1rem;}"
                   "a{color:#2563eb;}</style></head><body>")

        for line in lines:
            if line.startswith("```"):
                if not in_code:
                    out.append("<pre><code>")
                    in_code = True
                else:
                    out.append("</code></pre>")
                    in_code = False
                continue
            if in_code:
                out.append(html.escape(line))
                continue
            if line.startswith("# "):
                out.append(f"<h1>{html.escape(line[2:])}</h1>")
            elif line.startswith("## "):
                out.append(f"<h2>{html.escape(line[3:])}</h2>")
            elif line.startswith("### "):
                out.append(f"<h3>{html.escape(line[4:])}</h3>")
            elif line.startswith("> "):
                out.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
            elif line.startswith("- "):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{html.escape(line[2:])}</li>")
            elif line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if all(set(c) <= {"-", ":", " "} for c in cells):
                    continue  # separator row
                if not in_table:
                    out.append("<table><thead><tr>")
                    for c in cells:
                        out.append(f"<th>{html.escape(c)}</th>")
                    out.append("</tr></thead><tbody>")
                    in_table = True
                else:
                    out.append("<tr>")
                    for c in cells:
                        out.append(f"<td>{html.escape(c)}</td>")
                    out.append("</tr>")
            elif line.strip() == "":
                if in_list:
                    out.append("</ul>")
                    in_list = False
                if in_table:
                    out.append("</tbody></table>")
                    in_table = False
                out.append("")
            elif line.strip() == "---":
                out.append("<hr>")
            else:
                # Inline formatting for bold/italic/code (very simple)
                line_esc = html.escape(line)
                line_esc = line_esc.replace("**", "<b>", 1).replace("**", "</b>", 1) if "**" in line_esc else line_esc
                out.append(f"<p>{line_esc}</p>")

        if in_list:
            out.append("</ul>")
        if in_table:
            out.append("</tbody></table>")
        out.append("</body></html>")
        return "\n".join(out)
