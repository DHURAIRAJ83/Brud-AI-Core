"""Phase 40 — Production SentencePiece Tokenizer Trainer & Validator.

Implements Workstream 4:
- SentencePiece BPE tokenizer training on approved sovereign corpus
- Target vocabulary ~32,000 (configurable)
- Special tokens: <pad>, <unk>, <bos>, <eos>, <system>, <user>, <assistant>
- Unknown-token rate evaluation across Tamil, English, and Tanglish
- Artifact manifest generation and SHA-256 verification
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import sentencepiece as spm
except ImportError:
    spm = None


SPECIAL_USER_DEFINED_SYMBOLS = ["<system>", "<user>", "<assistant>"]


@dataclass
class TokenizerEvaluationResult:
    vocabulary_size: int
    pad_id: int
    unk_id: int
    bos_id: int
    eos_id: int
    special_tokens_valid: bool
    tamil_unk_rate: float
    english_unk_rate: float
    tanglish_unk_rate: float
    code_switching_unk_rate: float
    overall_unk_rate: float
    model_sha256: str
    vocab_sha256: str
    manifest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SovereignTokenizerTrainer:
    """Trains and qualifies sovereign SentencePiece BPE tokenizers."""

    def __init__(self, target_vocab_size: int = 32000, model_type: str = "bpe") -> None:
        self.target_vocab_size = target_vocab_size
        self.model_type = model_type

    def train(
        self,
        input_text_file: Path,
        output_prefix: Path,
        vocab_size: int | None = None,
    ) -> tuple[Path, Path]:
        """Trains SentencePiece model with required special tokens."""
        if spm is None:
            raise RuntimeError("SentencePiece is not installed")

        actual_vocab = vocab_size or self.target_vocab_size
        output_prefix.parent.mkdir(parents=True, exist_ok=True)

        spm.SentencePieceTrainer.train(
            input=str(input_text_file),
            model_prefix=str(output_prefix),
            vocab_size=actual_vocab,
            model_type=self.model_type,
            pad_id=0,
            unk_id=1,
            bos_id=2,
            eos_id=3,
            user_defined_symbols=SPECIAL_USER_DEFINED_SYMBOLS,
            normalization_rule_name="nmt_nfkc",
            character_coverage=0.9995,
            hard_vocab_limit=False,
            num_threads=2,
        )


        model_path = Path(f"{output_prefix}.model")
        vocab_path = Path(f"{output_prefix}.vocab")
        return model_path, vocab_path

    def evaluate_and_manifest(
        self,
        model_path: Path,
        vocab_path: Path,
        eval_samples: dict[str, list[str]],
        output_manifest: Path,
    ) -> TokenizerEvaluationResult:
        """Evaluates tokenization properties, unknown token rates, and writes SHA-256 manifest."""
        if spm is None:
            raise RuntimeError("SentencePiece is not installed")

        sp = spm.SentencePieceProcessor(model_file=str(model_path))
        actual_vocab = sp.get_piece_size()

        pad_id = sp.pad_id()
        unk_id = sp.unk_id()
        bos_id = sp.bos_id()
        eos_id = sp.eos_id()

        special_valid = (
            pad_id == 0
            and unk_id == 1
            and bos_id == 2
            and eos_id == 3
            and all(sp.piece_to_id(sym) > 0 for sym in SPECIAL_USER_DEFINED_SYMBOLS)
        )

        def compute_unk_rate(texts: list[str]) -> float:
            total_tokens = 0
            unk_tokens = 0
            for text in texts:
                ids = sp.encode(text, out_type=int)
                total_tokens += len(ids)
                unk_tokens += sum(1 for tok in ids if tok == unk_id)
            return unk_tokens / total_tokens if total_tokens > 0 else 0.0

        ta_unk = compute_unk_rate(eval_samples.get("tamil", []))
        en_unk = compute_unk_rate(eval_samples.get("english", []))
        tgl_unk = compute_unk_rate(eval_samples.get("tanglish", []))
        cs_unk = compute_unk_rate(eval_samples.get("code_switch", []))
        all_samples = [s for lst in eval_samples.values() for s in lst]
        overall_unk = compute_unk_rate(all_samples)

        model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
        vocab_sha = hashlib.sha256(vocab_path.read_bytes()).hexdigest()

        result = TokenizerEvaluationResult(
            vocabulary_size=actual_vocab,
            pad_id=pad_id,
            unk_id=unk_id,
            bos_id=bos_id,
            eos_id=eos_id,
            special_tokens_valid=special_valid,
            tamil_unk_rate=ta_unk,
            english_unk_rate=en_unk,
            tanglish_unk_rate=tgl_unk,
            code_switching_unk_rate=cs_unk,
            overall_unk_rate=overall_unk,
            model_sha256=model_sha,
            vocab_sha256=vocab_sha,
        )

        manifest_data = {
            "tokenizer_name": "brud_sovereign_spm_bpe",
            "model_type": self.model_type,
            "metrics": result.to_dict(),
        }
        manifest_bytes = json.dumps(manifest_data, indent=2, sort_keys=True).encode("utf-8")
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        manifest_data["manifest_sha256"] = manifest_sha
        result.manifest_sha256 = manifest_sha

        output_manifest.parent.mkdir(parents=True, exist_ok=True)
        output_manifest.write_text(json.dumps(manifest_data, indent=2, sort_keys=True), encoding="utf-8")
        return result
