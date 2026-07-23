"""Optimizer-aware training checkpoints."""

from __future__ import annotations

import inspect
import shutil
import tempfile
from pathlib import Path
from typing import Any

import torch

from backend.core.json_utils import dumps_json, loads_json
from core_model.checkpoints.training_manifest import combined_checksum, sha256_file


class TrainingCheckpointManager:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root
        self.max_bytes = max_bytes

    def save(
        self,
        target: Path,
        *,
        model,
        optimizer,
        scheduler,
        optimizer_state: dict[str, Any] | None = None,
        scheduler_state: dict[str, Any] | None = None,
        rng_state: Any | None = None,
        trainer_state: dict[str, Any],
        config: dict[str, Any],
        references: dict[str, str],
    ) -> dict[str, Any]:
        if target.exists():
            raise FileExistsError("training checkpoint already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp_name:
            tmp = Path(tmp_name)
            torch.save(model.state_dict(), tmp / "model_state.pt")
            torch.save(optimizer_state or optimizer.state_dict(), tmp / "optimizer_state.pt")
            torch.save(scheduler_state or scheduler.state_dict(), tmp / "scheduler_state.pt")
            torch.save(
                rng_state if rng_state is not None else torch.random.get_rng_state(),
                tmp / "rng_state.pt",
            )
            (tmp / "trainer_state.json").write_text(dumps_json(trainer_state), encoding="utf-8")
            (tmp / "config.json").write_text(dumps_json(config), encoding="utf-8")
            (tmp / "references.json").write_text(dumps_json(references), encoding="utf-8")
            files = [
                "model_state.pt",
                "optimizer_state.pt",
                "scheduler_state.pt",
                "rng_state.pt",
                "trainer_state.json",
                "config.json",
                "references.json",
            ]
            checksums = {name: sha256_file(tmp / name) for name in files}
            manifest = {"files": files, "checksums": checksums}
            (tmp / "manifest.json").write_text(dumps_json(manifest), encoding="utf-8")
            checksums["manifest.json"] = sha256_file(tmp / "manifest.json")
            (tmp / "checksums.txt").write_text(
                "".join(f"{value}  {name}\n" for name, value in checksums.items()),
                encoding="utf-8",
            )
            size = sum((tmp / name).stat().st_size for name in checksums)
            if size > self.max_bytes:
                raise ValueError("training checkpoint exceeds configured limit")
            shutil.move(str(tmp), target)
        return {
            "file_size_bytes": size,
            "model_checksum_sha256": checksums["model_state.pt"],
            "optimizer_checksum_sha256": checksums["optimizer_state.pt"],
            "scheduler_checksum_sha256": checksums["scheduler_state.pt"],
            "trainer_state_checksum_sha256": checksums["trainer_state.json"],
            "combined_checksum_sha256": combined_checksum(list(checksums.values())),
            "manifest": {"files": list(checksums)},
        }

    def verify(self, target: Path) -> bool:
        if not target.is_dir():
            raise ValueError("checkpoint directory unavailable")
        manifest = loads_json((target / "manifest.json").read_text(encoding="utf-8"))
        for name, checksum in manifest.get("checksums", {}).items():
            path = target / name
            if not path.is_file() or not path.resolve().is_relative_to(target.resolve()):
                raise ValueError("invalid checkpoint manifest entry")
            if sha256_file(path) != checksum:
                raise ValueError("training checkpoint checksum mismatch")
        return True

    def load_states(self, target: Path) -> dict[str, Any]:
        self.verify(target)
        kwargs = {"map_location": "cpu"}
        if "weights_only" in inspect.signature(torch.load).parameters:
            kwargs["weights_only"] = True
        return {
            "model": torch.load(target / "model_state.pt", **kwargs),
            "optimizer": torch.load(target / "optimizer_state.pt", **kwargs),
            "scheduler": torch.load(target / "scheduler_state.pt", **kwargs),
            "rng": torch.load(target / "rng_state.pt", **kwargs),
            "trainer_state": loads_json(
                (target / "trainer_state.json").read_text(encoding="utf-8")
            ),
            "references": loads_json((target / "references.json").read_text(encoding="utf-8")),
        }
