"""Experiment orchestration service.

Creates, starts, cancels experiments. Each experiment runs baseline evaluation
→ training → fine-tuned evaluation → comparison using the same harness.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from slmforge.core.exceptions import (
    ExperimentStateError, InvalidTrainingConfigError, NotFoundError, TrainingError,
)
from slmforge.core.logging import get_logger
from slmforge.db.models.experiment import EvaluationRun, Experiment, RobustnessRun, TrainingRun
from slmforge.db.models.model import ModelVersion
from slmforge.db.models.artifact import Artifact
from slmforge.services.data.ingestion import DatasetIngestionService
from slmforge.services.evaluation.engine import EvaluationService
from slmforge.services.model.inference import InferenceService
from slmforge.services.model.registry import ModelRegistryService
from slmforge.services.training.engine import TrainingService
from slmforge.storage import get_storage_backend
from slmforge.utils.git import get_git_commit, is_git_dirty

logger = get_logger(__name__)

VALID_STATUSES = {"QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}


class ExperimentService:
    """Orchestrates full experimental lifecycles."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = get_storage_backend()
        self._training = TrainingService(db)
        self._inference = InferenceService()
        self._active_jobs: Dict[str, threading.Thread] = {}

    def create_experiment(
        self,
        name: str,
        dataset_version_id: str,
        base_model_version_id: str,
        *,
        description: Optional[str] = None,
        training_config: Optional[Dict[str, Any]] = None,
        evaluation_config: Optional[Dict[str, Any]] = None,
        seed: int = 42,
        run_baseline_only: bool = False,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Experiment:
        git_commit = get_git_commit()
        if is_git_dirty():
            logger.warning("experiment.git_dirty", message="Working tree is dirty; results may not be reproducible.")

        exp = Experiment(
            name=name,
            status="QUEUED",
            description=description,
            dataset_version_id=dataset_version_id,
            base_model_version_id=base_model_version_id,
            seed=seed,
            git_commit=git_commit,
            training_config=training_config or {},
            evaluation_config=evaluation_config or {},
            tags=tags or {"baseline_only": run_baseline_only},
        )
        self.db.add(exp)
        self.db.flush()

        # Create dependent training run
        if not run_baseline_only:
            tr = TrainingRun(
                experiment_id=exp.id,
                status="PENDING",
                method=training_config.get("method", "qlora") if training_config else "qlora",
            )
            self.db.add(tr)

        # Create baseline evaluation run
        baseline_eval = EvaluationRun(
            experiment_id=exp.id,
            model_version_id=base_model_version_id,
            dataset_version_id=dataset_version_id,
            is_baseline=True,
            status="PENDING",
            split=(evaluation_config or {}).get("split", "test"),
        )
        self.db.add(baseline_eval)

        self.db.commit()
        self.db.refresh(exp)
        logger.info("experiment.created", experiment_id=exp.id, name=name)
        return exp

    def start_experiment(self, experiment_id: str, *, dry_run: bool = False) -> Experiment:
        """Start an experiment asynchronously in a background thread."""
        exp = self.db.get(Experiment, experiment_id)
        if not exp:
            raise NotFoundError(f"Experiment {experiment_id} not found")
        if exp.status not in ("QUEUED", "FAILED", "CANCELLED"):
            raise ExperimentStateError(f"Cannot start experiment in status {exp.status}")
        exp.status = "RUNNING"
        exp.started_at = datetime.now(timezone.utc).isoformat()
        exp.error_message = None
        self.db.commit()

        thread = threading.Thread(
            target=self._run_experiment, args=(experiment_id, dry_run), daemon=True,
            name=f"experiment-{experiment_id}",
        )
        thread.start()
        self._active_jobs[experiment_id] = thread
        return exp

    def cancel_experiment(self, experiment_id: str) -> Experiment:
        exp = self.db.get(Experiment, experiment_id)
        if not exp:
            raise NotFoundError(f"Experiment {experiment_id} not found")
        if exp.status not in ("QUEUED", "RUNNING"):
            raise ExperimentStateError(f"Cannot cancel experiment in status {exp.status}")
        exp.status = "CANCELLED"
        self.db.commit()
        return exp

    def _run_experiment(self, experiment_id: str, dry_run: bool) -> None:
        """Internal: run the full pipeline synchronously (called from thread)."""
        db = self.db  # Sessions are NOT thread-safe — for background thread use new session
        from slmforge.db.session import SessionLocal
        thread_db = SessionLocal()
        try:
            exp = thread_db.get(Experiment, experiment_id)
            if not exp:
                return

            logger.info("experiment.run.start", experiment_id=experiment_id)

            # 1. BASELINE EVALUATION
            baseline_eval = (
                thread_db.query(EvaluationRun)
                .filter(EvaluationRun.experiment_id == experiment_id)
                .filter(EvaluationRun.is_baseline == True)  # noqa: E712
                .first()
            )
            if baseline_eval:
                eval_svc = EvaluationService(thread_db, self._inference)
                eval_svc.run_evaluation(baseline_eval)

            # 2. TRAINING (if not baseline-only)
            tags = exp.tags or {}
            if not tags.get("baseline_only", False):
                training_run = (
                    thread_db.query(TrainingRun)
                    .filter(TrainingRun.experiment_id == experiment_id)
                    .first()
                )
                if training_run:
                    training_result = self._training.run_training(
                        exp, training_run, dry_run=dry_run,
                    )

                    # Register fine-tuned adapter as a new model version
                    if training_result.get("adapter_path"):
                        model_registry = ModelRegistryService(thread_db)
                        base_v = thread_db.get(ModelVersion, exp.base_model_version_id)
                        method = exp.training_config.get("method", "qlora")
                        adapter_version = model_registry.register_adapter(
                            model_id=base_v.model_id,
                            base_version_id=exp.base_model_version_id,
                            adapter_type=method,
                            adapter_path=training_result["adapter_path"],
                            training_config=exp.training_config,
                            adapter_size_bytes=training_result.get("adapter_size_bytes"),
                            trainable_params=training_result.get("trainable_params"),
                        )
                        exp.fine_tuned_model_version_id = adapter_version.id
                        thread_db.commit()

                        # 3. FINE-TUNED EVALUATION
                        ft_eval = EvaluationRun(
                            experiment_id=experiment_id,
                            model_version_id=adapter_version.id,
                            dataset_version_id=exp.dataset_version_id,
                            is_baseline=False,
                            status="PENDING",
                            split=(exp.evaluation_config or {}).get("split", "test"),
                        )
                        thread_db.add(ft_eval)
                        thread_db.commit()
                        eval_svc = EvaluationService(thread_db, self._inference)
                        eval_svc.run_evaluation(ft_eval)

            exp.status = "COMPLETED"
            exp.completed_at = datetime.now(timezone.utc).isoformat()
            thread_db.commit()
            logger.info("experiment.run.complete", experiment_id=experiment_id)

        except Exception as exc:
            logger.error("experiment.run.failed", experiment_id=experiment_id, error=str(exc))
            try:
                exp = thread_db.get(Experiment, experiment_id)
                if exp:
                    exp.status = "FAILED"
                    exp.error_message = str(exc)
                    exp.completed_at = datetime.now(timezone.utc).isoformat()
                    thread_db.commit()
            except Exception:
                pass
        finally:
            thread_db.close()
            self._active_jobs.pop(experiment_id, None)

    def get_experiment(self, experiment_id: str) -> Experiment:
        exp = self.db.get(Experiment, experiment_id)
        if not exp:
            raise NotFoundError(f"Experiment {experiment_id} not found")
        return exp
