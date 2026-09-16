"""Model inference abstraction.

Handles model loading (with quantization), batched inference, latency
measurement, memory tracking, and graceful fallback to dry-run when models
are not available on disk.
"""

from __future__ import annotations

import gc
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch

from slmforge.core.config import settings
from slmforge.core.logging import get_logger
from slmforge.db.models.model import ModelVersion
from slmforge.utils.env import get_cuda_info, get_python_version
from slmforge.utils.json_utils import parse_json_output, validate_structured_output
from slmforge.utils.seeding import set_seed

logger = get_logger(__name__)

VULN_PROMPT_TEMPLATE = """You are a security code auditor. Analyze the following source code snippet for security vulnerabilities.

Return ONLY a valid JSON object with these exact fields:
- "vulnerable": boolean (true if the code contains a security vulnerability)
- "category": string (one of: SQL_INJECTION, XSS, COMMAND_INJECTION, PATH_TRAVERSAL, BUFFER_OVERFLOW, INSECURE_CRYPTO, HARDCODED_SECRET, INTEGER_OVERFLOW, RACE_CONDITION, DESERIALIZATION, AUTH_BYPASS, INFORMATION_DISCLOSURE, NULL_DEREFERENCE, USE_AFTER_FREE, MEMORY_LEAK, CSRF, SSRF, OPEN_REDIRECT, CODE_INJECTION, FORMAT_STRING, OTHER, NONE)
- "severity": string (one of: CRITICAL, HIGH, MEDIUM, LOW, INFO, NONE)
- "evidence": string (a concise explanation of why the code is or is not vulnerable)

If no vulnerability is present, set vulnerable to false, category to "NONE", and severity to "NONE".

Source code snippet:
```
{code}
```

JSON response:"""


@dataclass
class InferenceResult:
    raw_output: str
    parsed_output: Optional[Dict[str, Any]]
    is_json_valid: bool
    is_schema_valid: bool
    schema_issues: List[str]
    latency_ms: float
    tokens_per_sec: Optional[float] = None
    peak_memory_mb: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ModelInfo:
    loaded: bool = False
    name: str = ""
    parameter_count: Optional[int] = None
    quantized: Optional[str] = None
    device: str = "cpu"
    dtype: str = "float32"
    error: Optional[str] = None
    dry_run: bool = False


class InferenceService:
    """Lazy-loading inference service with dry-run mode for pipeline validation."""

    def __init__(self) -> None:
        self._models: Dict[str, Tuple[Any, Any]] = {}  # version_id -> (model, tokenizer)
        self._info: Dict[str, ModelInfo] = {}

    def load_model(self, model_version: ModelVersion, *, force_dry_run: bool = False) -> ModelInfo:
        """Load a model (or mark as dry-run if not possible). Idempotent."""
        vid = model_version.id
        if vid in self._info and self._info[vid].loaded:
            return self._info[vid]

        info = ModelInfo(name=model_version.hf_model_id or model_version.revision)
        self._info[vid] = info

        if force_dry_run or not model_version.hf_model_id:
            info.dry_run = True
            info.loaded = False
            info.error = "dry_run_mode"
            logger.warning("inference.dry_run", model_version=vid)
            return info

        try:
            from transformers import (
                AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
            )
            from peft import PeftModel
        except ImportError as exc:
            info.dry_run = True
            info.error = f"transformers/peft not available: {exc}"
            logger.warning("inference.import_failed", error=str(exc))
            return info

        try:
            device = "cuda" if torch.cuda.is_available() and not settings.force_cpu else "cpu"
            quant = model_version.quantization

            tokenizer = AutoTokenizer.from_pretrained(
                model_version.hf_model_id,
                revision=model_version.revision,
                trust_remote_code=True,
                cache_dir=str(settings.model_cache_dir),
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            bnb_config = None
            torch_dtype = torch.float32
            if quant == "4bit" and device == "cuda":
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=True,
                )
                torch_dtype = torch.bfloat16
            elif quant == "8bit" and device == "cuda":
                bnb_config = BitsAndBytesConfig(load_in_8bit=True)
                torch_dtype = torch.float16

            model = AutoModelForCausalLM.from_pretrained(
                model_version.hf_model_id,
                revision=model_version.revision,
                quantization_config=bnb_config,
                torch_dtype=torch_dtype,
                device_map="auto" if device == "cuda" else None,
                trust_remote_code=True,
                cache_dir=str(settings.model_cache_dir),
            )

            # If this is an adapter version, load the LoRA weights on top
            if model_version.adapter_path and model_version.adapter_type in ("lora", "qlora"):
                adapter_path = Path(model_version.adapter_path)
                if adapter_path.exists():
                    model = PeftModel.from_pretrained(model, str(adapter_path))
                    logger.info("inference.adapter_loaded", adapter=str(adapter_path))

            if device == "cpu":
                model = model.to("cpu")
            model.eval()

            param_count = sum(p.numel() for p in model.parameters())
            info.loaded = True
            info.parameter_count = param_count
            info.quantized = quant
            info.device = device
            info.dtype = str(torch_dtype).replace("torch.", "")
            self._models[vid] = (model, tokenizer)
            logger.info(
                "inference.model_loaded",
                model=model_version.hf_model_id,
                device=device,
                params=param_count,
                quant=quant,
            )
        except Exception as exc:
            info.dry_run = True
            info.loaded = False
            info.error = str(exc)
            logger.error("inference.load_failed", model=model_version.hf_model_id, error=str(exc))

        return info

    @torch.no_grad()
    def predict(
        self,
        model_version: ModelVersion,
        code_snippet: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        seed: int = 42,
    ) -> InferenceResult:
        """Run a single prediction on a code snippet."""
        set_seed(seed)
        vid = model_version.id
        info = self._info.get(vid)
        if info is None or (not info.loaded and not info.dry_run):
            info = self.load_model(model_version)

        prompt = VULN_PROMPT_TEMPLATE.format(code=code_snippet)

        t0 = time.perf_counter()
        peak_mem: Optional[float] = None

        try:
            if info.dry_run:
                # Dry-run: produce a deterministic placeholder response so pipeline can be validated
                raw_output = json.dumps({
                    "vulnerable": False,
                    "category": "NONE",
                    "severity": "NONE",
                    "evidence": "DRY-RUN: model not loaded; this is a placeholder response for pipeline validation."
                })
            else:
                model, tokenizer = self._models[vid]
                inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
                input_device = next(model.parameters()).device
                inputs = {k: v.to(input_device) for k, v in inputs.items()}

                if torch.cuda.is_available():
                    torch.cuda.reset_peak_memory_stats()

                gen_kwargs: Dict[str, Any] = {
                    "max_new_tokens": max_new_tokens,
                    "do_sample": temperature > 0,
                    "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
                    "eos_token_id": tokenizer.eos_token_id,
                }
                if temperature > 0:
                    gen_kwargs["temperature"] = temperature

                outputs = model.generate(**inputs, **gen_kwargs)
                new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
                raw_output = tokenizer.decode(new_tokens, skip_special_tokens=True)

                if torch.cuda.is_available():
                    peak_mem = torch.cuda.max_memory_allocated() / (1024 * 1024)

            latency_ms = (time.perf_counter() - t0) * 1000
            parsed, err = parse_json_output(raw_output)
            is_json_valid = err is None
            schema_issues: List[str] = []
            is_schema_valid = False
            if parsed:
                is_schema_valid, schema_issues = validate_structured_output(parsed)

            tps: Optional[float] = None
            if latency_ms > 0 and info.loaded:
                _model, tokenizer = self._models[vid]
                out_ids = tokenizer(raw_output, return_tensors="pt")["input_ids"]
                n_tokens = out_ids.shape[1]
                tps = n_tokens / (latency_ms / 1000)

            return InferenceResult(
                raw_output=raw_output,
                parsed_output=parsed if is_json_valid else None,
                is_json_valid=is_json_valid,
                is_schema_valid=is_schema_valid,
                schema_issues=schema_issues,
                latency_ms=latency_ms,
                tokens_per_sec=tps,
                peak_memory_mb=peak_mem,
                error=err,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.error("inference.prediction_failed", error=str(exc))
            return InferenceResult(
                raw_output="",
                parsed_output=None,
                is_json_valid=False,
                is_schema_valid=False,
                schema_issues=[],
                latency_ms=latency_ms,
                error=str(exc),
            )

    def unload_model(self, model_version_id: str) -> None:
        if model_version_id in self._models:
            del self._models[model_version_id]
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        self._info.pop(model_version_id, None)

    def get_model_info(self, model_version_id: str) -> Optional[ModelInfo]:
        return self._info.get(model_version_id)
