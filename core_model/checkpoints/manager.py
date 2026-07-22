"""Safe registered checkpoint save/load helpers."""

from __future__ import annotations

import inspect
import shutil
import tempfile
from pathlib import Path
from typing import Any

import torch

from backend.core.json_utils import dumps_json, loads_json
from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM
from core_model.checkpoints.manifest import sha256_file, write_manifest


class CheckpointManager:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root
        self.max_bytes = max_bytes

    def save(
        self,
        model: BrudForCausalLM,
        target: Path,
        *,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if target.exists():
            raise FileExistsError("checkpoint target already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp_name:
            tmp = Path(tmp_name)
            config_path = tmp / "config.json"
            state_path = tmp / "model_state.pt"
            config_path.write_text(dumps_json(model.config.to_dict()) + "\n", encoding="utf-8")
            torch.save(model.state_dict(), state_path)
            if state_path.stat().st_size > self.max_bytes:
                raise ValueError("checkpoint exceeds configured size limit")
            manifest_checksum = write_manifest(
                tmp,
                ["config.json", "model_state.pt", "artifact_manifest.json"],
                metadata,
            )
            checksums = {
                "config.json": sha256_file(config_path),
                "model_state.pt": sha256_file(state_path),
                "artifact_manifest.json": manifest_checksum,
            }
            (tmp / "checksums.txt").write_text(
                "".join(f"{value}  {name}\n" for name, value in checksums.items()),
                encoding="utf-8",
            )
            shutil.move(str(tmp), target)
        return {
            "files": ["config.json", "model_state.pt", "artifact_manifest.json", "checksums.txt"],
            "checksum_sha256": sha256_file(target / "model_state.pt"),
            "file_size_bytes": (target / "model_state.pt").stat().st_size,
        }

    def load(self, target: Path, config: BrudModelConfig) -> BrudForCausalLM:
        self.verify(target)
        state_path = target / "model_state.pt"
        kwargs = {"map_location": "cpu"}
        if "weights_only" in inspect.signature(torch.load).parameters:
            kwargs["weights_only"] = True
        state = torch.load(state_path, **kwargs)
        model = BrudForCausalLM(config)
        missing, unexpected = model.load_state_dict(state, strict=True)
        if missing or unexpected:
            raise ValueError("checkpoint state dictionary does not match architecture")
        model.eval()
        return model

    def verify(self, target: Path) -> bool:
        if not target.is_dir():
            raise ValueError("checkpoint directory is unavailable")
        manifest = loads_json((target / "artifact_manifest.json").read_text(encoding="utf-8"))
        for name in manifest.get("files", []):
            path = target / name
            if not path.is_file() or not path.resolve().is_relative_to(target.resolve()):
                raise ValueError("checkpoint manifest references an invalid file")
        checksums = (target / "checksums.txt").read_text(encoding="utf-8").splitlines()
        for line in checksums:
            checksum, name = line.split("  ", 1)
            if sha256_file(target / name) != checksum:
                raise ValueError("checkpoint checksum mismatch")
        return True
