"""Phase 48 Append-Only Idempotent Global Token Ledger.

Provides a cryptographically verifiable, append-only ledger of sovereign training tokens,
enforcing block-chain hash linkage, replay/duplicate run rejection, and truthful milestone accounting.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class TokenLedgerError(Exception):
    """Raised when ledger integrity is compromised or duplicate run is detected."""
    pass


@dataclass
class LedgerBlock:
    index: int
    run_id: str
    job_id: str
    worker_id: str
    parent_checkpoint_id: str
    child_checkpoint_id: str
    run_steps: int
    run_tokens: int
    cumulative_tokens: int
    previous_hash: str
    block_hash: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LedgerBlock:
        return cls(**data)


class Phase48TokenLedger:
    """Cryptographic append-only token ledger with replay protection and milestone tracking."""

    GENESIS_HASH = "GENESIS_PHASE47_SOVEREIGN_ROOT"
    MILESTONES = [10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 5_000_000, 10_000_000]

    def __init__(self, ledger_file: Path | str, initial_baseline_tokens: int = 2080) -> None:
        self.ledger_file = Path(ledger_file)
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        self.initial_baseline_tokens = initial_baseline_tokens
        if not self.ledger_file.exists():
            self._initialize_genesis()

    def _compute_block_hash(
        self,
        index: int,
        run_id: str,
        job_id: str,
        run_tokens: int,
        cumulative_tokens: int,
        previous_hash: str,
    ) -> str:
        payload = f"{index}:{run_id}:{job_id}:{run_tokens}:{cumulative_tokens}:{previous_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _read_blocks(self) -> list[LedgerBlock]:
        if not self.ledger_file.exists():
            return []
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [LedgerBlock.from_dict(b) for b in data]
        except Exception:
            return []

    def _write_blocks(self, blocks: list[LedgerBlock]) -> None:
        temp_file = self.ledger_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in blocks], f, indent=2)
        temp_file.replace(self.ledger_file)

    def _initialize_genesis(self) -> None:
        genesis_hash = self._compute_block_hash(
            index=0,
            run_id="genesis_phase47",
            job_id="job_phase47_baseline",
            run_tokens=self.initial_baseline_tokens,
            cumulative_tokens=self.initial_baseline_tokens,
            previous_hash=self.GENESIS_HASH,
        )
        genesis_block = LedgerBlock(
            index=0,
            run_id="genesis_phase47",
            job_id="job_phase47_baseline",
            worker_id="system_init",
            parent_checkpoint_id="phase46_checkpoint_step_130_root",
            child_checkpoint_id="phase47_checkpoint_step_65_root",
            run_steps=65,
            run_tokens=self.initial_baseline_tokens,
            cumulative_tokens=self.initial_baseline_tokens,
            previous_hash=self.GENESIS_HASH,
            block_hash=genesis_hash,
            timestamp=time.time(),
        )
        self._write_blocks([genesis_block])

    def append_run(
        self,
        run_id: str,
        job_id: str,
        worker_id: str,
        parent_checkpoint_id: str,
        child_checkpoint_id: str,
        run_steps: int,
        run_tokens: int,
    ) -> LedgerBlock:
        """Appends a new verified run to the ledger with strict replay and token integrity checks."""
        blocks = self._read_blocks()
        if not blocks:
            self._initialize_genesis()
            blocks = self._read_blocks()

        # Check for replay / duplicate run_id (Mandatory Correction 3)
        for b in blocks:
            if b.run_id == run_id:
                raise TokenLedgerError(f"Duplicate run_id detected: {run_id} has already been committed to the ledger")

        last_block = blocks[-1]
        new_index = len(blocks)
        new_cumulative = last_block.cumulative_tokens + run_tokens
        new_hash = self._compute_block_hash(
            index=new_index,
            run_id=run_id,
            job_id=job_id,
            run_tokens=run_tokens,
            cumulative_tokens=new_cumulative,
            previous_hash=last_block.block_hash,
        )

        new_block = LedgerBlock(
            index=new_index,
            run_id=run_id,
            job_id=job_id,
            worker_id=worker_id,
            parent_checkpoint_id=parent_checkpoint_id,
            child_checkpoint_id=child_checkpoint_id,
            run_steps=run_steps,
            run_tokens=run_tokens,
            cumulative_tokens=new_cumulative,
            previous_hash=last_block.block_hash,
            block_hash=new_hash,
            timestamp=time.time(),
        )
        blocks.append(new_block)
        self._write_blocks(blocks)
        return new_block

    def get_latest_block(self) -> LedgerBlock:
        blocks = self._read_blocks()
        if not blocks:
            self._initialize_genesis()
            blocks = self._read_blocks()
        return blocks[-1]

    def get_cumulative_tokens(self) -> int:
        return self.get_latest_block().cumulative_tokens

    def verify_ledger_integrity(self) -> tuple[bool, str]:
        """Cryptographically verifies entire ledger chain and mathematical token continuity."""
        blocks = self._read_blocks()
        if not blocks:
            return False, "Ledger is empty"

        seen_run_ids: set[str] = set()

        for i, b in enumerate(blocks):
            # Check unique run_id
            if b.run_id in seen_run_ids:
                return False, f"Duplicate run_id at block {i}: {b.run_id}"
            seen_run_ids.add(b.run_id)

            # Check hash correctness
            expected_hash = self._compute_block_hash(
                index=b.index,
                run_id=b.run_id,
                job_id=b.job_id,
                run_tokens=b.run_tokens,
                cumulative_tokens=b.cumulative_tokens,
                previous_hash=b.previous_hash,
            )
            if b.block_hash != expected_hash:
                return False, f"Hash mismatch at block {i}: expected {expected_hash}, got {b.block_hash}"

            if i == 0:
                if b.previous_hash != self.GENESIS_HASH:
                    return False, f"Invalid genesis previous_hash: {b.previous_hash}"
            else:
                prev_block = blocks[i - 1]
                if b.previous_hash != prev_block.block_hash:
                    return False, f"Broken chain at block {i}: expected previous_hash {prev_block.block_hash}, got {b.previous_hash}"
                if b.cumulative_tokens != prev_block.cumulative_tokens + b.run_tokens:
                    return False, f"Mathematical token discontinuity at block {i}: {b.cumulative_tokens} != {prev_block.cumulative_tokens} + {b.run_tokens}"

        return True, f"Verified {len(blocks)} blocks successfully"

    def get_milestone_status(self) -> dict[str, Any]:
        total = self.get_cumulative_tokens()
        status: dict[str, Any] = {}
        for m in self.MILESTONES:
            label = f"{m // 1000}K" if m < 1_000_000 else f"{m // 1_000_000}M"
            if total >= m:
                status[label] = {"target": m, "status": "ACHIEVED", "current": total}
            else:
                status[label] = {"target": m, "status": f"IN_PROGRESS ({total}/{m})", "current": total}
        return status
