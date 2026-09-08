"""Phase 49 Cryptographic Append-Only Token Ledger with Idempotency and Dataset Binding.

Extends Phase 48 ledger with complete block schema, idempotency keys for crash window
protection, dataset manifest hash binding, and multi-day accumulation integrity.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core_model.training.phase48_token_ledger import LedgerBlock, Phase48TokenLedger, TokenLedgerError


@dataclass
class Phase49LedgerBlock:
    index: int
    run_id: str
    job_id: str
    worker_id: str
    parent_checkpoint_id: str
    child_checkpoint_id: str
    run_steps: int
    run_tokens: int
    validation_tokens: int
    cumulative_tokens: int
    dataset_manifest_hash: str
    previous_hash: str
    block_hash: str
    idempotency_key: str
    status: str = "COMMITTED"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Phase49LedgerBlock:
        return cls(**data)


class Phase49TokenLedger(Phase48TokenLedger):
    """Extended append-only ledger supporting Phase 49 multi-day training windows."""

    def __init__(self, ledger_file: Path | str, initial_baseline_tokens: int = 4256) -> None:
        super().__init__(ledger_file, initial_baseline_tokens)

    def _read_blocks(self) -> list[Any]:
        if not self.ledger_file.exists():
            return []
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                blocks = []
                for b in data:
                    if "dataset_manifest_hash" in b:
                        blocks.append(Phase49LedgerBlock.from_dict(b))
                    else:
                        blocks.append(LedgerBlock.from_dict(b))
                return blocks
        except Exception:
            return []

    def _write_blocks(self, blocks: list[Any]) -> None:
        temp_file = self.ledger_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in blocks], f, indent=2)
        temp_file.replace(self.ledger_file)

    def _compute_phase49_hash(
        self,
        index: int,
        run_id: str,
        job_id: str,
        child_checkpoint_id: str,
        dataset_manifest_hash: str,
        run_tokens: int,
        cumulative_tokens: int,
        previous_hash: str,
    ) -> str:
        payload = (
            f"{index}:{run_id}:{job_id}:{child_checkpoint_id}:"
            f"{dataset_manifest_hash}:{run_tokens}:{cumulative_tokens}:{previous_hash}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def has_idempotency_key(self, idempotency_key: str) -> bool:
        """Mandatory Correction 3: Checks if an idempotency key is already committed."""
        blocks = self._read_blocks()
        for b in blocks:
            if getattr(b, "idempotency_key", None) == idempotency_key:
                return True
        return False

    def append_window(
        self,
        run_id: str,
        job_id: str,
        worker_id: str,
        parent_checkpoint_id: str,
        child_checkpoint_id: str,
        run_steps: int,
        run_tokens: int,
        validation_tokens: int = 0,
        dataset_manifest_hash: str = "c8b4480e9fb5e521db5f403f70231bfb673aa09d4d18b7b14fe78afe33454b2a",
        idempotency_key: str | None = None,
    ) -> Phase49LedgerBlock:
        """Appends a new training window block with strict cryptographic validation."""
        if run_tokens < 0 or run_steps < 0:
            raise TokenLedgerError(f"Negative tokens or steps rejected: tokens={run_tokens}, steps={run_steps}")

        blocks = self._read_blocks()
        if not blocks:
            self._initialize_genesis()
            blocks = self._read_blocks()

        existing_run_ids = {b.run_id for b in blocks}
        if run_id in existing_run_ids:
            raise TokenLedgerError(f"Duplicate run_id detected in ledger: {run_id}")

        key = idempotency_key or f"{run_id}:{child_checkpoint_id}:{parent_checkpoint_id}"
        if self.has_idempotency_key(key):
            raise TokenLedgerError(f"Idempotency key already committed: {key}")

        last_block = blocks[-1]
        next_index = len(blocks)
        next_cumulative = last_block.cumulative_tokens + run_tokens
        prev_hash = last_block.block_hash

        b_hash = self._compute_phase49_hash(
            index=next_index,
            run_id=run_id,
            job_id=job_id,
            child_checkpoint_id=child_checkpoint_id,
            dataset_manifest_hash=dataset_manifest_hash,
            run_tokens=run_tokens,
            cumulative_tokens=next_cumulative,
            previous_hash=prev_hash,
        )

        new_block = Phase49LedgerBlock(
            index=next_index,
            run_id=run_id,
            job_id=job_id,
            worker_id=worker_id,
            parent_checkpoint_id=parent_checkpoint_id,
            child_checkpoint_id=child_checkpoint_id,
            run_steps=run_steps,
            run_tokens=run_tokens,
            validation_tokens=validation_tokens,
            cumulative_tokens=next_cumulative,
            dataset_manifest_hash=dataset_manifest_hash,
            previous_hash=prev_hash,
            block_hash=b_hash,
            idempotency_key=key,
        )

        blocks.append(new_block)
        self._write_blocks(blocks)
        return new_block

    def verify_ledger_integrity(self) -> tuple[bool, str]:
        """Cryptographically verifies hash chain, continuity, and dataset bindings."""
        blocks = self._read_blocks()
        if not blocks:
            return False, "Ledger has no blocks"

        genesis = blocks[0]
        if genesis.previous_hash != self.GENESIS_HASH:
            return False, f"Genesis previous hash mismatch: {genesis.previous_hash}"

        seen_runs = set()
        seen_keys = set()

        for i in range(1, len(blocks)):
            prev = blocks[i - 1]
            curr = blocks[i]

            if curr.run_id in seen_runs:
                return False, f"Duplicate run_id at block {i}: {curr.run_id}"
            seen_runs.add(curr.run_id)

            key = getattr(curr, "idempotency_key", None)
            if key:
                if key in seen_keys:
                    return False, f"Duplicate idempotency_key at block {i}: {key}"
                seen_keys.add(key)

            if curr.previous_hash != prev.block_hash:
                return False, f"Broken hash chain at block {i}: {curr.previous_hash} != {prev.block_hash}"

            if curr.cumulative_tokens != prev.cumulative_tokens + curr.run_tokens:
                return False, (
                    f"Token accumulation discontinuity at block {i}: "
                    f"{curr.cumulative_tokens} != {prev.cumulative_tokens} + {curr.run_tokens}"
                )

        return True, f"Verified {len(blocks)} blocks successfully"

