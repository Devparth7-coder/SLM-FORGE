"""Dataset ingestion pipeline.

End-to-end: load → validate → normalize → deduplicate → split → hash → version → persist.

Supported input formats: JSON, JSONL, CSV, Parquet, HuggingFace datasets,
directories of source files.
"""

from __future__ import annotations

import csv
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from slmforge.core.config import settings
from slmforge.core.exceptions import DatasetIngestionError, DatasetValidationError
from slmforge.core.logging import get_logger
from slmforge.db.models.dataset import (
    Dataset, DatasetVersion, DatasetSample, DatasetQualityReport,
)
from slmforge.services.data.deduplication import DeduplicationService, content_hash
from slmforge.services.data.quality import DataQualityService
from slmforge.services.data.validation import SchemaValidator, BatchValidationStats
from slmforge.storage import get_storage_backend
from slmforge.utils.hashing import compute_dataset_hash, compute_hash, compute_file_hash

logger = get_logger(__name__)


class DatasetIngestionService:
    """Run the full dataset ingestion pipeline and persist results."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.validator = SchemaValidator()
        self.dedup = DeduplicationService()
        self.quality = DataQualityService()
        self.storage = get_storage_backend()

    # ── Public entry point ────────────────────────────────────────────────
    def ingest(
        self,
        name: str,
        *,
        source_path: Optional[str] = None,
        file_format: Optional[str] = None,
        hf_dataset_id: Optional[str] = None,
        hf_dataset_config: Optional[str] = None,
        hf_dataset_split: Optional[str] = None,
        uploaded_file: Optional[BinaryIO] = None,
        uploaded_filename: Optional[str] = None,
        domain: str = "code_security",
        task: str = "vulnerability_classification",
        description: Optional[str] = None,
        is_demo: bool = False,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        deduplicate: bool = True,
        detect_leakage: bool = True,
        seed: int = 42,
    ) -> Tuple[Dataset, DatasetVersion, DatasetQualityReport, Dict[str, Any]]:
        """Run ingestion and persist all results."""
        import random
        random.seed(seed)

        logger.info("dataset.ingest.start", name=name, source=source_path, hf=hf_dataset_id)

        # 1. LOAD raw samples
        raw_samples = self._load_samples(
            source_path=source_path, file_format=file_format,
            hf_dataset_id=hf_dataset_id, hf_dataset_config=hf_dataset_config,
            hf_dataset_split=hf_dataset_split,
            uploaded_file=uploaded_file, uploaded_filename=uploaded_filename,
        )
        raw_count = len(raw_samples)
        logger.info("dataset.ingest.loaded", raw_count=raw_count)

        if raw_count == 0:
            raise DatasetValidationError("Dataset contains no samples.")

        # 2. VALIDATE + NORMALIZE
        valid_samples, val_stats = self.validator.validate_batch(raw_samples)
        logger.info(
            "dataset.ingest.validated",
            valid=val_stats.valid, invalid=val_stats.invalid,
        )

        if len(valid_samples) < 10:
            raise DatasetValidationError(
                f"Only {len(valid_samples)} valid samples (need at least 10).",
                details={"validation_stats": val_stats.issues_counter},
            )

        # 3. DEDUPLICATE
        deduped = valid_samples
        dup_count = 0
        near_dup_count = 0
        if deduplicate:
            deduped, dup_stats = self.dedup.deduplicate_exact(valid_samples)
            dup_count = dup_stats.exact_duplicate_count
            # Near-duplicate detection (flag, but don't remove to avoid surprising the user)
            near_stats = self.dedup.detect_near_duplicates(deduped)
            near_dup_count = near_stats.near_duplicate_count
            logger.info(
                "dataset.ingest.deduplicated",
                exact=dup_count, near=near_dup_count, remaining=len(deduped),
            )

        # 4. SPLIT train/val/test (deterministic via sort + seed-based shuffle)
        deduped.sort(key=lambda s: content_hash(s.get("input", "")))
        random.shuffle(deduped)
        n = len(deduped)
        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)
        splits = {
            "train": deduped[:train_end],
            "val": deduped[train_end:val_end],
            "test": deduped[val_end:],
        }

        # 5. Train/test leakage detection
        leakage_count = 0
        if detect_leakage:
            leak_stats = self.dedup.detect_train_test_leakage(
                splits["train"], splits["test"]
            )
            leakage_count = leak_stats.train_test_overlap_count

        # 6. HASH
        dataset_content_hash = compute_dataset_hash(deduped)
        split_hash = compute_dataset_hash(splits["test"])

        # 7. QUALITY REPORT
        quality_report = self.quality.analyse(
            deduped,
            duplicate_count=dup_count,
            near_duplicate_count=near_dup_count,
            invalid_count=val_stats.invalid,
            train_test_overlap=leakage_count,
        )

        # 8. PERSIST
        dataset = Dataset(
            name=name,
            description=description or f"Dataset '{name}' ingested at {datetime.utcnow().isoformat()}",
            source=source_path or (hf_dataset_id and f"hf:{hf_dataset_id}") or "upload",
            source_uri=hf_dataset_id or source_path,
            domain=domain,
            task=task,
            is_demo=is_demo,
            pipeline_version="0.1.0",
        )
        self.db.add(dataset)
        self.db.flush()

        version_str = self._next_version(dataset.id)
        manifest = self._write_manifest(
            dataset.id, version_str, deduped, splits,
            dataset_content_hash, split_hash, seed,
        )

        dsv = DatasetVersion(
            dataset_id=dataset.id,
            version=version_str,
            content_hash=dataset_content_hash,
            sample_count=n,
            train_count=len(splits["train"]),
            val_count=len(splits["val"]),
            test_count=len(splits["test"]),
            raw_count=raw_count,
            duplicates_removed=dup_count,
            invalid_removed=val_stats.invalid,
            manifest_path=manifest,
            split_hash=split_hash,
            stats={
                "seed": seed,
                "train_ratio": train_ratio,
                "val_ratio": val_ratio,
                "test_ratio": test_ratio,
                "near_duplicates_flagged": near_dup_count,
                "validation_issues": val_stats.issues_counter,
            },
        )
        self.db.add(dsv)
        self.db.flush()

        # Insert samples
        sample_idx = 0
        for split_name, split_samples in splits.items():
            for s in split_samples:
                ch = content_hash(s.get("input", ""))
                ds_sample = DatasetSample(
                    dataset_id=dataset.id,
                    version_id=dsv.id,
                    sample_index=sample_idx,
                    split=split_name,
                    sample_id=s.get("id", str(uuid.uuid4())),
                    input_text=s["input"],
                    label=s.get("label"),
                    category=s.get("category"),
                    severity=s.get("severity"),
                    evidence=s.get("evidence", ""),
                    is_synthetic=s.get("metadata", {}).get("synthetic", False),
                    synthetic_metadata=s.get("metadata", {}).get("synthetic_metadata", {}),
                    quality_score=s.get("quality_score"),
                    is_duplicate=False,
                    content_hash=ch,
                    metadata_=s.get("metadata", {}),
                )
                self.db.add(ds_sample)
                sample_idx += 1

        # Quality report row
        qr = DatasetQualityReport(
            dataset_id=dataset.id,
            version_id=dsv.id,
            **quality_report.to_dict(),
        )
        self.db.add(qr)
        self.db.commit()

        ingest_stats = {
            "raw_count": raw_count,
            "clean_count": len(valid_samples),
            "duplicates_removed": dup_count,
            "invalid_removed": val_stats.invalid,
            "near_duplicates_flagged": near_dup_count,
            "train_count": len(splits["train"]),
            "val_count": len(splits["val"]),
            "test_count": len(splits["test"]),
            "train_test_overlap": leakage_count,
            "content_hash": dataset_content_hash,
        }
        logger.info("dataset.ingest.complete", **ingest_stats)

        return dataset, dsv, qr, ingest_stats

    # ── Loading ───────────────────────────────────────────────────────────
    def _load_samples(
        self,
        *,
        source_path: Optional[str],
        file_format: Optional[str],
        hf_dataset_id: Optional[str],
        hf_dataset_config: Optional[str],
        hf_dataset_split: Optional[str],
        uploaded_file: Optional[BinaryIO],
        uploaded_filename: Optional[str],
    ) -> List[Dict[str, Any]]:
        if hf_dataset_id:
            return self._load_hf(hf_dataset_id, hf_dataset_config, hf_dataset_split)
        if uploaded_file is not None:
            fmt = (file_format or self._guess_format(uploaded_filename or "")).lower()
            return self._load_from_fileobj(uploaded_file, fmt)
        if source_path:
            p = Path(source_path)
            if not p.exists():
                raise DatasetIngestionError(f"Source path does not exist: {source_path}")
            fmt = (file_format or self._guess_format(str(p))).lower()
            if p.is_dir():
                return self._load_directory(p)
            return self._load_from_path(p, fmt)
        raise DatasetIngestionError("No source specified: provide source_path, hf_dataset_id, or upload a file.")

    def _guess_format(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return {
            ".json": "json",
            ".jsonl": "jsonl",
            ".csv": "csv",
            ".parquet": "parquet",
            ".py": "directory",
        }.get(ext, "json")

    def _load_from_path(self, path: Path, fmt: str) -> List[Dict[str, Any]]:
        if fmt == "json":
            data = json.loads(path.read_text())
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            if isinstance(data, list):
                return data
            raise DatasetValidationError(f"JSON file must contain a list, got {type(data).__name__}")
        if fmt == "jsonl":
            records = []
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
            return records
        if fmt == "csv":
            with open(path, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        if fmt == "parquet":
            try:
                import pandas as pd
                df = pd.read_parquet(path)
                return df.to_dict(orient="records")
            except ImportError:
                raise DatasetIngestionError("pyarrow/pandas required for Parquet ingestion.")
        raise DatasetIngestionError(f"Unsupported format: {fmt}")

    def _load_from_fileobj(self, f: BinaryIO, fmt: str) -> List[Dict[str, Any]]:
        content = f.read()
        text = content.decode("utf-8", errors="replace")
        if fmt == "json":
            data = json.loads(text)
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            if not isinstance(data, list):
                raise DatasetValidationError("JSON must contain a list of samples.")
            return data
        if fmt in ("jsonl", "jsonl"):
            return [json.loads(ln) for ln in text.splitlines() if ln.strip()]
        if fmt == "csv":
            import io
            return list(csv.DictReader(io.StringIO(text)))
        raise DatasetIngestionError(f"Unsupported upload format: {fmt}")

    def _load_hf(
        self,
        dataset_id: str,
        config: Optional[str],
        split: Optional[str],
    ) -> List[Dict[str, Any]]:
        try:
            from datasets import load_dataset
        except ImportError:
            raise DatasetIngestionError("Hugging Face datasets library not installed.")
        try:
            ds = load_dataset(
                dataset_id,
                config or "default",
                split=split or "train",
                trust_remote_code=True,
            )
        except Exception as exc:
            raise DatasetIngestionError(
                f"Failed to load HuggingFace dataset '{dataset_id}': {exc}",
                cause=exc,
            )
        return [dict(row) for row in ds]

    def _load_directory(self, directory: Path) -> List[Dict[str, Any]]:
        """Load source-code files from a directory, treating each file as a sample."""
        samples: List[Dict[str, Any]] = []
        code_extensions = {".py", ".js", ".java", ".c", ".cpp", ".go", ".rs", ".php",
                           ".rb", ".ts", ".cs", ".sh"}
        for fp in directory.rglob("*"):
            if fp.is_file() and fp.suffix.lower() in code_extensions:
                try:
                    content = fp.read_text(errors="replace")
                    samples.append({
                        "id": str(fp.relative_to(directory)),
                        "input": content,
                        "label": "safe",  # default — user can re-label
                        "category": "NONE",
                        "severity": "NONE",
                        "evidence": f"Loaded from {fp.name}",
                        "metadata": {"source_file": str(fp)},
                    })
                except Exception as exc:
                    logger.warning("dataset.ingest.file_error", path=str(fp), error=str(exc))
        return samples

    # ── Helpers ───────────────────────────────────────────────────────────
    def _next_version(self, dataset_id: str) -> str:
        existing = (
            self.db.query(DatasetVersion)
            .filter(DatasetVersion.dataset_id == dataset_id)
            .count()
        )
        return f"v{existing + 1}.0.0"

    def _write_manifest(
        self,
        dataset_id: str,
        version: str,
        samples: List[Dict[str, Any]],
        splits: Dict[str, List[Dict[str, Any]]],
        content_hash: str,
        split_hash: str,
        seed: int,
    ) -> str:
        manifest = {
            "dataset_id": dataset_id,
            "version": version,
            "content_hash": content_hash,
            "split_hash": split_hash,
            "seed": seed,
            "total_samples": len(samples),
            "splits": {k: len(v) for k, v in splits.items()},
            "created_at": datetime.utcnow().isoformat(),
            "pipeline_version": "0.1.0",
        }
        key = f"datasets/{dataset_id}/{version}/manifest.json"
        self.storage.store_bytes(key, json.dumps(manifest, indent=2).encode("utf-8"),
                                 content_type="application/json")
        return key
