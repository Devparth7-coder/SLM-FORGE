"""LoRA / QLoRA training engine.

Implements parameter-efficient fine-tuning using PEFT + TRL/SFTTrainer.
Gracefully degrades to dry-run mode when hardware or libraries are unavailable,
so the pipeline can be validated without actually running training.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from slmforge.core.config import settings
from slmforge.core.exceptions import InvalidTrainingConfigError, TrainingError
from slmforge.core.logging import get_logger
from slmforge.db.models.dataset import DatasetSample, DatasetVersion
from slmforge.db.models.experiment import Experiment, TrainingRun
from slmforge.db.models.model import ModelVersion
from slmforge.storage import get_storage_backend
from slmforge.utils.env import get_cuda_info, get_package_versions, get_python_version, get_platform_info
from slmforge.utils.git import get_git_commit, is_git_dirty
from slmforge.utils.seeding import set_seed

logger = get_logger(__name__)

SYSTEM_INSTRUCTION = (
    "You are a security code auditor. Analyze source code for vulnerabilities and respond with valid JSON."
)
INSTRUCTION_TEMPLATE = """Analyze the following source code for security vulnerabilities:

```
{code}
```

Respond with a JSON object containing vulnerable (bool), category, severity, and evidence."""


class TrainingService:
    """Run LoRA/QLoRA fine-tuning."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = get_storage_backend()

    def validate_config(self, config: Dict[str, Any]) -> list[str]:
        """Validate training configuration; return list of warnings (empty if valid)."""
        warnings: list[str] = []
        method = config.get("method", "qlora")
        if method not in ("lora", "qlora", "full"):
            raise InvalidTrainingConfigError(f"Unsupported method: {method}")
        lr = config.get("learning_rate", 2e-4)
        if lr <= 0 or lr > 1e-2:
            raise InvalidTrainingConfigError(f"Learning rate out of reasonable range: {lr}")
        epochs = config.get("epochs", 3)
        if epochs <= 0 or epochs > 100:
            raise InvalidTrainingConfigError(f"Epochs out of range: {epochs}")
        if method in ("lora", "qlora"):
            lora = config.get("lora", {})
            r = lora.get("r", 16)
            if r < 1 or r > 256:
                raise InvalidTrainingConfigError(f"LoRA rank out of range: {r}")
        return warnings

    def run_training(
        self,
        experiment: Experiment,
        training_run: TrainingRun,
        *,
        dry_run: bool = False,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Run fine-tuning. Returns a results dict."""
        from slmforge.services.model.inference import InferenceService
        inf = InferenceService()

        config = experiment.training_config
        self.validate_config(config)
        set_seed(config.get("seed", experiment.seed))

        base_version: ModelVersion = self.db.get(ModelVersion, experiment.base_model_version_id)
        if not base_version:
            raise TrainingError(f"Base model version {experiment.base_model_version_id} not found")
        dataset_version: DatasetVersion = self.db.get(DatasetVersion, experiment.dataset_version_id)
        if not dataset_version:
            raise TrainingError(f"Dataset version {experiment.dataset_version_id} not found")

        training_run.status = "RUNNING"
        self.db.commit()

        t_start = time.time()

        try:
            # ── Check if we can actually train ────────────────────────────
            can_train = self._check_training_feasibility()
            effective_dry_run = dry_run or not can_train

            if effective_dry_run:
                logger.warning("training.dry_run", reason="hardware_or_libraries_unavailable")
                training_run.status = "COMPLETED"
                training_run.method = config.get("method", "qlora")
                training_run.total_epochs = config.get("epochs", 3)
                training_run.error_message = (
                    "DRY RUN: Training was simulated because GPU/libraries are unavailable. "
                    "This is NOT an actual training result."
                )
                # Create a placeholder adapter path so evaluation proceeds in dry-run mode
                adapter_dir = settings.artifacts_dir / experiment.id / "adapter_dryrun"
                adapter_dir.mkdir(parents=True, exist_ok=True)
                (adapter_dir / "README_DRYRUN.txt").write_text(
                    "This is a DRY-RUN placeholder. No actual adapter was trained.\n"
                )
                training_run.final_adapter_path = str(adapter_dir)
                training_run.elapsed_seconds = 0.0
                self.db.commit()
                return {"dry_run": True, "adapter_path": str(adapter_dir)}

            # ── Load training data ────────────────────────────────────────
            train_samples = (
                self.db.query(DatasetSample)
                .filter(DatasetSample.version_id == dataset_version.id)
                .filter(DatasetSample.split == "train")
                .order_by(DatasetSample.sample_index)
                .all()
            )
            val_samples = (
                self.db.query(DatasetSample)
                .filter(DatasetSample.version_id == dataset_version.id)
                .filter(DatasetSample.split == "val")
                .order_by(DatasetSample.sample_index)
                .all()
            )

            if not train_samples:
                raise TrainingError("No training samples found")

            # ── W&B init (optional) ───────────────────────────────────────
            wandb_run = None
            if settings.wandb_enabled and settings.wandb_api_key:
                try:
                    import wandb
                    wandb_run = wandb.init(
                        project=settings.wandb_project,
                        entity=settings.wandb_entity,
                        name=experiment.name,
                        config={**config, "experiment_id": experiment.id},
                        reinit=True,
                    )
                    experiment.wandb_run_url = wandb_run.get_url()
                    self.db.commit()
                except Exception as exc:
                    logger.warning("training.wandb_init_failed", error=str(exc))

            # ── Tokenizer + Model ─────────────────────────────────────────
            from transformers import (
                AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                TrainingArguments,
            )
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
            from trl import SFTTrainer, DataCollatorForCompletionOnlyLM
            import torch
            from datasets import Dataset as HFDataset

            model_id = base_version.hf_model_id
            revision = base_version.revision

            tokenizer = AutoTokenizer.from_pretrained(
                model_id, revision=revision, trust_remote_code=True,
                cache_dir=str(settings.model_cache_dir),
            )
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            tokenizer.padding_side = "right"

            # BitsAndBytes config
            bnb_config = None
            torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            if config.get("method") == "qlora":
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=config.get("bnb", {}).get("load_in_4bit", True),
                    bnb_4bit_quant_type=config.get("bnb", {}).get("bnb_4bit_quant_type", "nf4"),
                    bnb_4bit_compute_dtype=torch_dtype,
                    bnb_4bit_use_double_quant=config.get("bnb", {}).get("bnb_4bit_use_double_quant", True),
                )

            model = AutoModelForCausalLM.from_pretrained(
                model_id,
                revision=revision,
                quantization_config=bnb_config,
                torch_dtype=torch_dtype,
                device_map="auto",
                trust_remote_code=True,
                cache_dir=str(settings.model_cache_dir),
            )
            model.config.use_cache = False

            if config.get("gradient_checkpointing", True):
                model.gradient_checkpointing_enable()

            if config.get("method") == "qlora":
                model = prepare_model_for_kbit_training(model)

            lora_cfg = config.get("lora", {})
            peft_config = LoraConfig(
                r=lora_cfg.get("r", 16),
                lora_alpha=lora_cfg.get("alpha", 32),
                lora_dropout=lora_cfg.get("dropout", 0.05),
                target_modules=lora_cfg.get("target_modules", ["q_proj", "v_proj"]),
                bias=lora_cfg.get("bias", "none"),
                task_type=TaskType.CAUSAL_LM,
            )
            model = get_peft_model(model, peft_config)
            trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
            total_params = sum(p.numel() for p in model.parameters())
            logger.info("training.params", trainable=trainable_params, total=total_params)

            # ── Format dataset ────────────────────────────────────────────
            def format_example(sample: Dict[str, Any]) -> str:
                label_json = json.dumps({
                    "vulnerable": sample.get("label") == "vulnerable",
                    "category": sample.get("category", "NONE"),
                    "severity": sample.get("severity", "NONE"),
                    "evidence": sample.get("evidence", ""),
                })
                return (
                    f"<|system|>\n{SYSTEM_INSTRUCTION}\n<|user|>\n"
                    f"{INSTRUCTION_TEMPLATE.format(code=sample['input_text'])}\n"
                    f"<|assistant|>\n{label_json}"
                )

            train_records = [{"input_text": s.input_text, "label": s.label,
                              "category": s.category, "severity": s.severity,
                              "evidence": s.evidence} for s in train_samples]
            val_records = [{"input_text": s.input_text, "label": s.label,
                            "category": s.category, "severity": s.severity,
                            "evidence": s.evidence} for s in val_samples]

            train_ds = HFDataset.from_list(train_records)
            val_ds = HFDataset.from_list(val_records) if val_records else None

            def tokenize_fn(examples):
                texts = [format_example({"input_text": c, "label": l, "category": cat,
                                         "severity": sev, "evidence": ev})
                         for c, l, cat, sev, ev in zip(examples["input_text"], examples["label"],
                                                        examples["category"], examples["severity"],
                                                        examples["evidence"])]
                return tokenizer(texts, truncation=True, max_length=config.get("max_seq_length", 1024),
                                 padding="max_length")

            # ── Training arguments ────────────────────────────────────────
            output_dir = str(settings.artifacts_dir / experiment.id / "checkpoints")
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            total_steps_estimate = (
                len(train_records)
                // (config.get("batch_size", 2) * config.get("gradient_accumulation_steps", 8))
            ) * int(config.get("epochs", 3))

            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=config.get("epochs", 3),
                per_device_train_batch_size=config.get("batch_size", 2),
                per_device_eval_batch_size=config.get("batch_size", 2),
                gradient_accumulation_steps=config.get("gradient_accumulation_steps", 8),
                learning_rate=config.get("learning_rate", 2e-4),
                lr_scheduler_type=config.get("scheduler", "cosine"),
                warmup_ratio=config.get("warmup_ratio", 0.03),
                weight_decay=config.get("weight_decay", 0.01),
                max_grad_norm=config.get("max_grad_norm", 1.0),
                logging_steps=config.get("logging_steps", 10),
                eval_steps=config.get("eval_steps", 100) if val_ds else None,
                save_steps=config.get("save_steps", 100),
                eval_strategy="steps" if val_ds else "no",
                save_strategy="steps",
                bf16=torch.cuda.is_bf16_supported() and config.get("mixed_precision", "bf16") == "bf16",
                fp16=not torch.cuda.is_bf16_supported() and config.get("mixed_precision", "bf16") == "fp16",
                optim=config.get("optim", "paged_adamw_8bit"),
                gradient_checkpointing=config.get("gradient_checkpointing", True),
                report_to="wandb" if wandb_run else "none",
                seed=config.get("seed", experiment.seed),
                dataloader_pin_memory=True,
                remove_unused_columns=False,
            )

            trainer = SFTTrainer(
                model=model,
                args=training_args,
                train_dataset=train_ds,
                eval_dataset=val_ds,
                tokenizer=tokenizer,
                peft_config=peft_config,
                max_seq_length=config.get("max_seq_length", 1024),
                formatting_func=lambda examples: [format_example({"input_text": t, "label": l,
                                                                   "category": cat, "severity": sev,
                                                                   "evidence": ev})
                                                  for t, l, cat, sev, ev in zip(
                                                          examples["input_text"], examples["label"],
                                                          examples["category"], examples["severity"],
                                                          examples["evidence"])],
            )

            training_run.total_steps = total_steps_estimate
            training_run.total_epochs = config.get("epochs", 3)
            training_run.method = config.get("method", "qlora")
            self.db.commit()

            trainer.train()

            # Save adapter
            adapter_dir = settings.artifacts_dir / experiment.id / "adapter"
            adapter_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(str(adapter_dir))
            tokenizer.save_pretrained(str(adapter_dir))
            adapter_size = sum(f.stat().st_size for f in adapter_dir.rglob("*") if f.is_file())

            elapsed = time.time() - t_start
            training_run.status = "COMPLETED"
            training_run.final_adapter_path = str(adapter_dir)
            training_run.elapsed_seconds = elapsed
            training_run.best_val_loss = trainer.state.best_metric
            training_run.metrics_history = [
                {"step": m.get("step"), "train_loss": m.get("loss"),
                 "val_loss": m.get("eval_loss"), "learning_rate": m.get("learning_rate"),
                 "epoch": m.get("epoch")}
                for m in trainer.state.log_history
            ]
            self.db.commit()

            if wandb_run:
                try:
                    wandb_run.finish()
                except Exception:
                    pass

            return {
                "dry_run": False,
                "adapter_path": str(adapter_dir),
                "adapter_size_bytes": adapter_size,
                "trainable_params": trainable_params,
                "total_params": total_params,
                "elapsed_seconds": elapsed,
            }

        except Exception as exc:
            training_run.status = "FAILED"
            training_run.error_message = str(exc)
            self.db.commit()
            logger.error("training.failed", error=str(exc))
            raise TrainingError(f"Training failed: {exc}", cause=exc) from exc

    def _check_training_feasibility(self) -> bool:
        """Check whether actual training can proceed (GPU + libs)."""
        try:
            import torch
            import transformers
            import peft
            import trl
            if not torch.cuda.is_available() and not settings.force_cpu:
                logger.warning("training.no_gpu")
                return False
            return True
        except ImportError as e:
            logger.warning("training.missing_libs", error=str(e))
            return False
