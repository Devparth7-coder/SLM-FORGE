"""Model registry service: register, discover, and load models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from slmforge.core.config import settings
from slmforge.core.exceptions import ModelNotAvailableError, NotFoundError
from slmforge.core.logging import get_logger
from slmforge.db.models.model import ModelRegistry, ModelVersion
from slmforge.storage import get_storage_backend
from slmforge.utils.env import get_package_versions, get_cuda_info, get_python_version, get_platform_info
from slmforge.utils.hardware import detect_hardware

logger = get_logger(__name__)


class ModelRegistryService:
    """Manage registered models and their versions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = get_storage_backend()

    def register_model(
        self,
        name: str,
        *,
        hf_model_id: Optional[str] = None,
        revision: str = "main",
        quantization: Optional[str] = None,
        provider: str = "huggingface",
        architecture: Optional[str] = None,
        domain: str = "code",
        task_type: str = "causal_lm",
        description: Optional[str] = None,
        license: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None,
    ) -> tuple[ModelRegistry, ModelVersion]:
        """Register a new model and its initial version."""
        model = ModelRegistry(
            name=name,
            provider=provider,
            architecture=architecture,
            domain=domain,
            task_type=task_type,
            description=description,
            license=license,
            tags=tags or {},
        )
        self.db.add(model)
        self.db.flush()

        version = ModelVersion(
            model_id=model.id,
            revision=revision,
            quantization=quantization,
            hf_model_id=hf_model_id,
            is_base_model=True,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(model)
        self.db.refresh(version)
        logger.info("model.registered", model_id=model.id, name=name, hf=hf_model_id)
        return model, version

    def register_adapter(
        self,
        model_id: str,
        base_version_id: str,
        *,
        adapter_type: str,
        adapter_path: str,
        training_config: Dict[str, Any],
        adapter_size_bytes: Optional[int] = None,
        trainable_params: Optional[int] = None,
    ) -> ModelVersion:
        """Register a fine-tuned adapter derived from a base model version."""
        base_version = self._get_version(base_version_id)
        adapter_version = ModelVersion(
            model_id=model_id,
            revision=f"adapter-{adapter_type}-{Path(adapter_path).stem[:8]}",
            quantization=base_version.quantization,
            is_base_model=False,
            base_model_version_id=base_version_id,
            adapter_type=adapter_type,
            adapter_path=adapter_path,
            adapter_size_bytes=adapter_size_bytes,
            adapter_trainable_params=trainable_params,
            hf_model_id=base_version.hf_model_id,
            hardware_info=detect_hardware().model_dump(),
            software_versions={
                "python": get_python_version(),
                "packages": get_package_versions(),
                "platform": get_platform_info(),
                "cuda": get_cuda_info(),
            },
        )
        self.db.add(adapter_version)
        self.db.commit()
        self.db.refresh(adapter_version)
        return adapter_version

    def list_models(self) -> List[ModelRegistry]:
        return self.db.query(ModelRegistry).order_by(ModelRegistry.created_at.desc()).all()

    def get_model(self, model_id: str) -> ModelRegistry:
        model = self.db.get(ModelRegistry, model_id)
        if not model:
            raise NotFoundError(f"Model {model_id} not found")
        return model

    def get_version(self, version_id: str) -> ModelVersion:
        return self._get_version(version_id)

    def _get_version(self, version_id: str) -> ModelVersion:
        v = self.db.get(ModelVersion, version_id)
        if not v:
            raise NotFoundError(f"Model version {version_id} not found")
        return v

    def update_download_status(self, version_id: str, *, is_downloaded: bool,
                               local_path: Optional[str] = None,
                               parameter_count: Optional[int] = None,
                               parameter_count_str: Optional[str] = None) -> None:
        v = self._get_version(version_id)
        v.is_downloaded = is_downloaded
        if local_path:
            v.local_path = local_path
        if parameter_count:
            v.parameter_count = parameter_count
        if parameter_count_str:
            v.parameter_count_str = parameter_count_str
        v.hardware_info = detect_hardware().model_dump()
        v.software_versions = {
            "python": get_python_version(),
            "packages": get_package_versions(),
            "platform": get_platform_info(),
            "cuda": get_cuda_info(),
        }
        self.db.commit()

    def estimate_parameter_str(self, param_count: Optional[int]) -> Optional[str]:
        if param_count is None:
            return None
        if param_count >= 1e9:
            return f"{param_count / 1e9:.0f}B"
        if param_count >= 1e6:
            return f"{param_count / 1e6:.0f}M"
        return str(param_count)
