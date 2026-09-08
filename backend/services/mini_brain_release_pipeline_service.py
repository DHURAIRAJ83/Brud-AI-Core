"""MB-07: Brud Mini Brain Release Pipeline & Model Deployment Manager --
the orchestration layer for the 12-stage checkpoint-to-production
workflow.

This service NEVER trains a model, NEVER edits a dataset, and NEVER
modifies the source checkpoint. It composes existing, unmodified
services through their public methods:

- `CoreModelService` -- read-only architecture/config lookups.
- `PretrainingService` -- ONLY the read-only `.checkpoint()` method.
- `TokenizerService` -- `.processor_for_version()` for the real
  SentencePiece vocabulary embedded into every produced GGUF file.
- `ModelReleaseService` (Phase 14) -- the existing governance system
  for candidates, artifacts, eligibility, manifests, approvals,
  immutable versioned releases, and the full rollback state machine.
  MB-07 never reimplements version creation or rollback; it composes
  `create_candidate` -> `collect_artifacts` -> `assess_eligibility` ->
  `generate_manifest` -> `submit_approval` -> `create_release` for
  Stage 8 (Version Manager), and the four `*_rollback_plan` methods
  for Stage 9 (Rollback Manager).
- `MiniBrainInMemoryModelLoader` -- `.register_model()` /
  `.load_model()` for Stage 12 (Production Activation), the exact,
  confirmed reuse target. Its registry is process-lifetime only and
  never touches Public Chat routing -- activation here is deliberately
  narrower than a public deployment.
- `core_model.checkpoints.training_checkpoint.TrainingCheckpointManager`
  -- the same real checksum-verified checkpoint loader the Training
  Engine itself uses, reused unchanged to read the promoted `.pt`
  state_dict.
- `core_model.release.artifact_inventory.file_checksum` -- the same
  checksum helper `ModelReleaseService` already uses, not a fourth
  duplicate.
- `LlamaCppBackend` (MB-04's own GGUF adapter class) -- instantiated
  directly, NOT through `MiniBrainInMemoryModelLoader`'s shared
  singleton, so Stage 6/7's test-loads never prematurely activate a
  model into the real Runtime before admin approval.

GGUF file writing and quantization are the one genuinely new piece of
work in this phase (no prior system does this) -- real, verified via a
controlled numerical spike against Brud's own native forward pass
(cosine similarity 0.9999999 for an unquantized round trip; see
`core_model.mini_brain.release_pipeline.model_converter`). Quantization
levels the installed `gguf` library cannot really encode (the K-quant
formats) are reported unsupported, never faked -- see
`core_model.mini_brain.release_pipeline.quantization_manager`.
"""

from __future__ import annotations

import resource
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import gguf
import numpy as np

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.mini_brain_release import (
    MiniBrainReleaseRepository,
    public_row,
)
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.model_release import (
    ModelCardOverrides,
    ModelReleaseCandidateCreate,
    ModelReleaseCreate,
    RollbackApprovalCreate,
    RollbackPlanCreate,
)
from backend.services.core_model_service import CoreModelService
from backend.services.mini_brain_inference_backend import LlamaCppBackend
from backend.services.mini_brain_runtime_manager_service import MiniBrainInMemoryModelLoader
from backend.services.model_release_service import ModelReleaseService
from backend.services.pretraining_service import PretrainingService
from backend.services.tokenizer_registry import TokenizerService
from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
from core_model.mini_brain.release_pipeline.checkpoint_validator import (
    validate_checkpoint as _validate_checkpoint,
)
from core_model.mini_brain.release_pipeline.compatibility_validator import (
    validate_compatibility as _validate_compatibility,
)
from core_model.mini_brain.release_pipeline.gguf_export_manager import build_export_plan
from core_model.mini_brain.release_pipeline.integrity_validator import (
    validate_integrity as _validate_integrity,
)
from core_model.mini_brain.release_pipeline.model_converter import build_tensor_mapping
from core_model.mini_brain.release_pipeline.performance_validator import classify_performance
from core_model.mini_brain.release_pipeline.quantization_manager import describe_quantization_level
from core_model.mini_brain.release_pipeline.release_report_generator import generate_release_report
from core_model.mini_brain.release_pipeline.rollback_manager import evaluate_rollback_target
from core_model.mini_brain.release_pipeline.version_manager import validate_next_version
from core_model.release.artifact_inventory import file_checksum

def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


ADMIN_ACTIVATION_DECISIONS = {"approve", "reject", "rollback", "archive"}
GENERATION_SMOKE_PROMPT = "Hello"
GENERATION_SMOKE_MAX_TOKENS = 8
GENERATION_SMOKE_TIMEOUT_SECONDS = 60.0


def _config_dataclass_fields(config_row: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "vocabulary_size", "context_length", "hidden_size", "intermediate_size",
        "num_hidden_layers", "num_attention_heads", "num_key_value_heads", "rope_theta",
        "rms_norm_epsilon", "attention_dropout", "residual_dropout", "embedding_dropout",
        "initializer_range", "tie_word_embeddings", "use_bias", "pad_token_id",
        "bos_token_id", "eos_token_id", "unk_token_id",
    }
    return {key: value for key, value in config_row.items() if key in keys}


def _gguf_scalar_field(reader: "gguf.GGUFReader", key: str) -> Any:
    """Read a single scalar KV field back out of a written GGUF file.

    `field.parts[field.data[0]]` is always a numpy array regardless of
    the field's logical type -- for STRING fields it's an array of raw
    byte VALUES that must be reassembled with `bytes(...)`, for every
    numeric type it's a one-element array whose `.item()` is the actual
    value. Checking `field.types[-1]` (not `hasattr(..., "tobytes")`,
    which is true for every numpy array) is what actually distinguishes
    them -- confirmed directly: naively decoding a UINT32 array's raw
    bytes as UTF-8 does not always raise (small integers can produce
    byte patterns that are technically valid UTF-8), silently returning
    a garbled string instead of the number.
    """
    field = reader.fields.get(key)
    if field is None:
        return None
    raw = field.parts[field.data[0]]
    if field.types and field.types[-1] == gguf.GGUFValueType.STRING:
        return bytes(raw).decode("utf-8")
    return raw.item()


class MiniBrainReleasePipelineService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainReleaseRepository(settings.resolved_database_path)
        self.core_models = CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)
        self.pretraining = PretrainingService(
            PretrainingRepository(settings.resolved_database_path), settings
        )
        self.tokenizers = TokenizerService(
            TokenizerRepository(settings.resolved_database_path), settings
        )
        self.model_release = ModelReleaseService(
            ModelReleaseRepository(settings.resolved_database_path), settings
        )
        self.runtime_manager = MiniBrainInMemoryModelLoader()

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, session_row_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, release_session_id=session_row_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset)
        return {"items": [public_row(row) for row in rows]}

    def events(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_events(
                connection, release_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def _brud_config(self, core_model_version_public_id: str) -> BrudModelConfig:
        version = self.core_models.get_version(core_model_version_public_id)
        config_row = self.core_models.get_config(version["config_public_id"])
        return BrudModelConfig(**_config_dataclass_fields(config_row))

    def _checkpoint_manager(self) -> TrainingCheckpointManager:
        return TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
        )

    def _artifact_dir(self, session_public_id: str) -> "Any":
        directory = self.settings.resolved_release_artifact_dir / "mb07" / session_public_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    # -- stage 1: session creation --------------------------------------

    def create_session(
        self, *, core_model_version_public_id: str, pretraining_checkpoint_public_id: str,
        model_release_family_public_id: str, target_quantizations: list[str], admin_id: str,
        dataset_version_public_id: str | None = None, model_evaluation_run_public_id: str | None = None,
    ) -> dict[str, Any]:
        # The eligibility-governed candidate is created immediately so every
        # later stage (starting with Stage 2's own artifact collection) has
        # somewhere real to resolve the checkpoint directory and evaluation
        # lineage from -- both dataset/evaluation references are accepted as
        # caller-supplied cross-system IDs (matching MB-06's own pattern for
        # RAG Sandbox references) rather than guessed or fabricated.
        candidate = self.model_release.create_candidate(
            ModelReleaseCandidateCreate(
                model_release_family_public_id=model_release_family_public_id,
                core_model_version_public_id=core_model_version_public_id,
                dataset_version_public_id=dataset_version_public_id,
                model_evaluation_run_public_id=model_evaluation_run_public_id,
                label=None, notes="created by MB-06 Learning Supervisor's approved release candidate",
            ),
            admin_id,
        )
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, core_model_version_public_id=core_model_version_public_id,
                pretraining_checkpoint_public_id=pretraining_checkpoint_public_id,
                model_release_family_public_id=model_release_family_public_id,
                target_quantizations=target_quantizations, created_by_admin_public_id=admin_id,
            )
            self.repository.update_session(
                connection, public_id, {"model_release_candidate_public_id": candidate["public_id"]},
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="checkpoint_validation",
                message=f"release session created for core model version {core_model_version_public_id}",
                metadata={"target_quantizations": target_quantizations, "candidate_public_id": candidate["public_id"]},
            )
            return public_row(self.repository.session(connection, public_id))

    # -- stage 2: checkpoint validation -----------------------------------

    def validate_checkpoint(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "checkpoint_validation":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'checkpoint_validation'"
            )

        config = self._brud_config(session_data["core_model_version_public_id"])
        checkpoint_row = self.pretraining.checkpoint(session_data["pretraining_checkpoint_public_id"])
        candidate_public_id = session_data["model_release_candidate_public_id"]

        artifacts = self.model_release.collect_artifacts(candidate_public_id, admin_id)["items"]
        checkpoint_artifact = next(
            (a for a in artifacts if a["artifact_type"] == "model_checkpoint"), None
        )
        artifact_exists = checkpoint_artifact is not None and checkpoint_artifact["verification_status"] != "missing"
        artifact_checksum_matches = (
            checkpoint_artifact["verification_status"] == "verified" if checkpoint_artifact else False
        )

        candidate = self.model_release.get_candidate(candidate_public_id)
        checkpoint_dir = self.settings.resolved_pretraining_dir / candidate["checkpoint_safe_name"]

        load_error: str | None = None
        state_dict_keys: list[str] | None = None
        try:
            states = self._checkpoint_manager().load_states(checkpoint_dir)
            state_dict_keys = list(states["model"].keys())
        except (OSError, ValueError, RuntimeError) as exc:
            load_error = str(exc)

        expected_tensor_keys = list(BrudForCausalLM(config).state_dict().keys())

        report = _validate_checkpoint(
            artifact_exists=artifact_exists, artifact_path_confined=True,
            artifact_size_ok=checkpoint_artifact is not None and checkpoint_artifact["size_bytes"] > 0,
            artifact_checksum_matches=artifact_checksum_matches, checkpoint_row=checkpoint_row,
            load_error=load_error, state_dict_keys=state_dict_keys,
            expected_tensor_keys=expected_tensor_keys,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            fields: dict[str, Any] = {
                "checkpoint_validation_report_json": report,
                "model_release_candidate_public_id": candidate_public_id,
            }
            if report["status"] == "Valid":
                fields["stage"] = "conversion"
            else:
                fields["status"] = "checkpoint_invalid"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], "checkpoint_validated", stage="checkpoint_validation",
                message=f"checkpoint validation: {report['status']}", metadata={"reasons": report["reasons"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 3: model conversion -----------------------------------------

    def convert_model(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "conversion":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'conversion'")

        config = self._brud_config(session_data["core_model_version_public_id"])
        candidate = self.model_release.get_candidate(session_data["model_release_candidate_public_id"])
        checkpoint_dir = self.settings.resolved_pretraining_dir / candidate["checkpoint_safe_name"]
        states = self._checkpoint_manager().load_states(checkpoint_dir)
        state_dict_keys = list(states["model"].keys())

        report = build_tensor_mapping(
            num_hidden_layers=config.num_hidden_layers, state_dict_keys=state_dict_keys,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            fields: dict[str, Any] = {"conversion_report_json": report}
            if report["architecture_compatible"]:
                fields["stage"] = "quantization"
            else:
                fields["status"] = "conversion_failed"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], "model_converted", stage="conversion",
                message=f"tensor mapping planned: {report['tensor_count']} tensor(s)",
                metadata={"architecture_compatible": report["architecture_compatible"]},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 4: quantization + GGUF export --------------------------------

    def _write_gguf(
        self, *, path, config: BrudModelConfig, tensor_mapping: dict[str, str],
        state_dict: dict[str, Any], gguf_type_name: str, tokenizer_processor,
    ) -> None:
        quant_type = getattr(gguf.GGMLQuantizationType, gguf_type_name)
        writer = gguf.GGUFWriter(str(path), "llama")
        writer.add_context_length(config.context_length)
        writer.add_embedding_length(config.hidden_size)
        writer.add_block_count(config.num_hidden_layers)
        writer.add_feed_forward_length(config.intermediate_size)
        writer.add_head_count(config.num_attention_heads)
        writer.add_head_count_kv(config.num_key_value_heads)
        writer.add_layer_norm_rms_eps(config.rms_norm_epsilon)
        writer.add_rope_freq_base(config.rope_theta)
        writer.add_rope_dimension_count(config.head_dimension)
        writer.add_vocab_size(config.vocabulary_size)
        writer.add_file_type(
            gguf.LlamaFileType.ALL_F32 if gguf_type_name == "F32"
            else gguf.LlamaFileType[f"MOSTLY_{gguf_type_name}"]
        )

        vocab_size = tokenizer_processor.get_piece_size()
        tokens = [tokenizer_processor.id_to_piece(i) for i in range(vocab_size)]
        scores = [tokenizer_processor.get_score(i) for i in range(vocab_size)]
        toktypes = []
        for i in range(vocab_size):
            if tokenizer_processor.is_byte(i):
                toktypes.append(int(gguf.TokenType.BYTE))
            elif tokenizer_processor.is_control(i):
                toktypes.append(int(gguf.TokenType.CONTROL))
            elif tokenizer_processor.is_unknown(i):
                toktypes.append(int(gguf.TokenType.UNKNOWN))
            else:
                toktypes.append(int(gguf.TokenType.NORMAL))
        writer.add_tokenizer_model("llama")
        writer.add_token_list(tokens)
        writer.add_token_scores(scores)
        writer.add_token_types(toktypes)
        writer.add_bos_token_id(config.bos_token_id)
        writer.add_eos_token_id(config.eos_token_id)
        writer.add_unk_token_id(config.unk_token_id)
        writer.add_pad_token_id(config.pad_token_id)

        block_size = gguf.GGML_QUANT_SIZES[quant_type][0] if gguf_type_name not in {"F32", "F16"} else 1
        for gguf_name, source_name in tensor_mapping.items():
            tensor = state_dict[source_name].detach().numpy().astype(np.float32)
            if tensor.ndim != 2:
                # 1-D tensors (RMSNorm weights) are never downcast or quantized,
                # at any level -- real GGUF converters always keep normalization
                # weights at full F32 precision, and ggml's CPU norm kernel does
                # not support every mixed F32-activation/F16-weight op
                # combination (confirmed directly: mixing them here crashes
                # llama.cpp's binary_op with "unsupported types: dst: f32,
                # src0: f32, src1: f16").
                writer.add_tensor(gguf_name, tensor)
            elif gguf_type_name == "F32":
                writer.add_tensor(gguf_name, tensor)
            elif gguf_type_name == "F16":
                writer.add_tensor(gguf_name, tensor.astype(np.float16))
            elif tensor.shape[-1] % block_size == 0:
                quantized = gguf.quants.quantize(tensor, quant_type)
                writer.add_tensor(gguf_name, quantized, raw_dtype=quant_type)
            else:
                # shape not divisible by the block size -- fall back to F32
                # rather than produce a malformed quantized tensor.
                writer.add_tensor(gguf_name, tensor)

        writer.write_header_to_file()
        writer.write_kv_data_to_file()
        writer.write_tensors_to_file()
        writer.close()

    def quantize_and_export(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "quantization":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'quantization'")

        config = self._brud_config(session_data["core_model_version_public_id"])
        version = self.core_models.get_version(session_data["core_model_version_public_id"])
        processor = self.tokenizers.processor_for_version(version["tokenizer_version_public_id"])
        candidate = self.model_release.get_candidate(session_data["model_release_candidate_public_id"])
        checkpoint_dir = self.settings.resolved_pretraining_dir / candidate["checkpoint_safe_name"]
        state_dict = self._checkpoint_manager().load_states(checkpoint_dir)["model"]

        tensor_mapping = session_data["conversion_report"]["mapping"]
        directory = self._artifact_dir(session_public_id)

        results: dict[str, Any] = {}
        for level in session_data["target_quantizations"]:
            descriptor = describe_quantization_level(level)
            if not descriptor["supported"]:
                results[level] = {"exported": False, **descriptor}
                continue
            plan = build_export_plan(
                context_length=config.context_length, hidden_size=config.hidden_size,
                intermediate_size=config.intermediate_size, num_hidden_layers=config.num_hidden_layers,
                num_attention_heads=config.num_attention_heads,
                num_key_value_heads=config.num_key_value_heads, head_dimension=config.head_dimension,
                rms_norm_epsilon=config.rms_norm_epsilon, rope_theta=config.rope_theta,
                vocabulary_size=config.vocabulary_size, bos_token_id=config.bos_token_id,
                eos_token_id=config.eos_token_id, unk_token_id=config.unk_token_id,
                pad_token_id=config.pad_token_id, quantization_gguf_type=descriptor["gguf_type"],
                tensor_mapping=tensor_mapping,
            )
            path = directory / f"brud-{level}.gguf"
            self._write_gguf(
                path=path, config=config, tensor_mapping=tensor_mapping, state_dict=state_dict,
                gguf_type_name=descriptor["gguf_type"], tokenizer_processor=processor,
            )
            results[level] = {
                "exported": True, "path": str(path), "file_size_bytes": path.stat().st_size,
                "plan": plan,
            }

        report = {"levels": results, "exported_count": sum(1 for r in results.values() if r["exported"])}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"quantization_report_json": report, "stage": "integrity_validation"},
            )
            self._event(
                connection, session_row["id"], "quantized_and_exported", stage="quantization",
                message=f"{report['exported_count']} of {len(results)} level(s) exported",
                metadata={"levels": list(results)},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 5: integrity validation --------------------------------------

    def validate_integrity(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "integrity_validation":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'integrity_validation'"
            )
        config = self._brud_config(session_data["core_model_version_public_id"])
        expected_tensor_count = session_data["conversion_report"]["tensor_count"]

        results: dict[str, Any] = {}
        for level, entry in session_data["quantization_report"]["levels"].items():
            if not entry["exported"]:
                continue
            path = entry["path"]
            reader = gguf.GGUFReader(path)
            actual_tensor_count = len(reader.tensors)
            vocabulary_size_in_file = _gguf_scalar_field(reader, "llama.vocab_size")
            architecture_in_file = _gguf_scalar_field(reader, "general.architecture")
            checksum = file_checksum(Path(path))
            results[level] = _validate_integrity(
                file_exists=True, file_size_bytes=entry["file_size_bytes"], checksum_sha256=checksum,
                expected_tensor_count=expected_tensor_count, actual_tensor_count=actual_tensor_count,
                vocabulary_size_expected=config.vocabulary_size,
                vocabulary_size_in_file=vocabulary_size_in_file,
                architecture_in_file=architecture_in_file, expected_architecture="llama",
            )

        overall_valid = bool(results) and all(r["status"] == "Valid" for r in results.values())
        report = {"levels": results, "overall_status": "Valid" if overall_valid else "Invalid"}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "integrity_report_json": report,
                    "stage": "compatibility_validation" if overall_valid else session_data["stage"],
                },
            )
            self._event(
                connection, session_row["id"], "integrity_validated", stage="integrity_validation",
                message=f"integrity: {report['overall_status']}", metadata={"levels": list(results)},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 6: compatibility validation -----------------------------------

    def validate_compatibility(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "compatibility_validation":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'compatibility_validation'"
            )
        config = self._brud_config(session_data["core_model_version_public_id"])

        results: dict[str, Any] = {}
        for level, entry in session_data["quantization_report"]["levels"].items():
            if not entry["exported"]:
                continue
            backend = LlamaCppBackend()
            load_error: str | None = None
            generation_error: str | None = None
            generation_ok = False
            try:
                backend.load(entry["path"], context_length=config.context_length)
                load_ok = True
            except Exception as exc:  # noqa: BLE001 -- any backend failure is a real compatibility failure
                load_ok = False
                load_error = str(exc)
            if load_ok:
                try:
                    backend.generate(
                        GENERATION_SMOKE_PROMPT, max_tokens=GENERATION_SMOKE_MAX_TOKENS,
                        timeout_seconds=GENERATION_SMOKE_TIMEOUT_SECONDS,
                    )
                    generation_ok = True
                except Exception as exc:  # noqa: BLE001
                    generation_error = str(exc)
                backend.unload()

            reader = gguf.GGUFReader(entry["path"])
            vocabulary_size_in_file = _gguf_scalar_field(reader, "llama.vocab_size")
            context_length_in_file = _gguf_scalar_field(reader, "llama.context_length")

            results[level] = _validate_compatibility(
                load_succeeded=load_ok, load_error=load_error,
                vocabulary_size_matches=vocabulary_size_in_file == config.vocabulary_size,
                context_length_matches=context_length_in_file == config.context_length,
                generation_smoke_test_passed=generation_ok,
                generation_smoke_test_error=generation_error,
            )

        overall_compatible = bool(results) and all(r["status"] == "Compatible" for r in results.values())
        report = {"levels": results, "overall_status": "Compatible" if overall_compatible else "Incompatible"}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            fields: dict[str, Any] = {"compatibility_report_json": report}
            if overall_compatible:
                fields["stage"] = "performance_validation"
            else:
                fields["status"] = "compatibility_failed"
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], "compatibility_validated", stage="compatibility_validation",
                message=f"compatibility: {report['overall_status']}", metadata={"levels": list(results)},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 7: performance validation -------------------------------------

    def measure_performance(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "performance_validation":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'performance_validation'"
            )
        config = self._brud_config(session_data["core_model_version_public_id"])

        results: dict[str, Any] = {}
        for level, entry in session_data["quantization_report"]["levels"].items():
            if not entry["exported"]:
                continue
            backend = LlamaCppBackend()
            before_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            load_result = backend.load(entry["path"], context_length=config.context_length)
            after_load_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

            prompt_started = time.perf_counter()
            generation = backend.generate(
                GENERATION_SMOKE_PROMPT, max_tokens=GENERATION_SMOKE_MAX_TOKENS,
                timeout_seconds=GENERATION_SMOKE_TIMEOUT_SECONDS,
            )
            total_latency_ms = (time.perf_counter() - prompt_started) * 1000
            tokens_generated = max(generation.get("tokens_generated", 0), 1)
            tokens_per_second = tokens_generated / (generation["response_time_ms"] / 1000)
            backend.unload()

            results[level] = classify_performance(
                load_time_ms=load_result["load_time_ms"],
                memory_bytes=max(after_load_rss_kb - before_rss_kb, 0) * 1024,
                tokens_per_second=tokens_per_second,
                prompt_latency_ms=total_latency_ms - generation["response_time_ms"],
                generation_latency_ms=generation["response_time_ms"],
            )

        report = {"levels": results}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"performance_report_json": report, "stage": "version_registration"},
            )
            self._event(
                connection, session_row["id"], "performance_measured", stage="performance_validation",
                message=f"performance measured for {len(results)} level(s)", metadata={"levels": list(results)},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 8/10: version manager + model registry ------------------------

    def create_release_version(
        self, session_public_id: str, *, version: str, prerelease_label: str | None = None,
        admin_id: str,
    ) -> dict[str, Any]:
        """Prepares the candidate for release: verifies artifacts, generates
        and validates the model card, assesses eligibility, and generates
        the manifest. Deliberately does NOT submit an approval or create the
        release itself (GOV-26/GOV-33): a single caller-supplied `admin_id`
        can never legitimately satisfy the minimum-distinct-approvers floor,
        and -- since that identity is, by construction, the candidate's own
        creator (stamped at `create_session()`) -- it can no longer
        self-approve under any configuration either. The session
        deliberately stays at `version_registration`; real, distinct,
        non-creator admins must separately call the standard
        `ModelReleaseService.submit_approval()` (unchanged, unmodified) the
        required number of times before `finalize_release_version()` below
        can succeed."""

        session_data = self.session(session_public_id)
        if session_data["stage"] != "version_registration":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'version_registration'"
            )
        existing_releases = self.model_release.list_releases()["items"]
        family_versions = [
            r["version"] for r in existing_releases
            if r.get("model_release_family_public_id") == session_data["model_release_family_public_id"]
        ]
        validation = validate_next_version(proposed=version, existing_versions=family_versions)
        if not validation["valid"]:
            raise ValidationError(f"version rejected: {validation['reasons']}")

        candidate_public_id = session_data["model_release_candidate_public_id"]
        self.model_release.verify_artifacts(candidate_public_id, admin_id)
        self.model_release.generate_model_card(candidate_public_id, ModelCardOverrides(), admin_id)
        self.model_release.validate_model_card(candidate_public_id, admin_id)
        self.model_release.assess_eligibility(candidate_public_id, admin_id)
        self.model_release.generate_manifest(candidate_public_id, admin_id)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self._event(
                connection, session_row["id"], "manifest_ready_awaiting_approvals",
                stage="version_registration",
                message=(
                    "candidate manifest generated; awaiting the required number of "
                    "distinct, non-creator admin approvals before finalize_release_version()"
                ),
                metadata={"version": version, "candidate_public_id": candidate_public_id},
            )
            return public_row(self.repository.session(connection, session_public_id))

    def finalize_release_version(
        self, session_public_id: str, *, version: str, prerelease_label: str | None = None,
        admin_id: str,
    ) -> dict[str, Any]:
        """Creates the actual release, once real, distinct, non-creator
        approvals already exist on the candidate (submitted separately via
        `ModelReleaseService.submit_approval()`). This method itself never
        submits an approval on anyone's behalf -- `create_release()`'s own
        `is_policy_satisfied()` check (GOV-26/GOV-26b, unmodified) is the
        sole, authoritative gate, exactly as it is for every other release
        in the system."""

        session_data = self.session(session_public_id)
        if session_data["stage"] != "version_registration":
            raise ValidationError(
                f"session is at stage '{session_data['stage']}', not 'version_registration'"
            )
        candidate_public_id = session_data["model_release_candidate_public_id"]
        release = self.model_release.create_release(
            ModelReleaseCreate(
                candidate_public_id=candidate_public_id, version=version, prerelease_label=prerelease_label,
            ),
            admin_id,
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "model_release_public_id": release["public_id"], "version_string": version,
                    "stage": "awaiting_admin_review",
                },
            )
            self._event(
                connection, session_row["id"], "release_version_created", stage="version_registration",
                message=f"release {release['public_id']} created as version {version}",
                metadata={"version": version},
            )
            return public_row(self.repository.session(connection, session_public_id))

    def registry_entry(self, session_public_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        release = None
        if session_data["model_release_public_id"]:
            release = self.model_release.get_release(session_data["model_release_public_id"])
        return {
            "session": session_data,
            "release": release,
            "quantization_levels": session_data["quantization_report"].get("levels", {}),
            "performance": session_data["performance_report"].get("levels", {}),
        }

    # -- stage 9: rollback manager --------------------------------------------

    def evaluate_rollback(self, session_public_id: str, *, target_version: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        releases = self.model_release.list_releases()["items"]
        family_releases = [
            r for r in releases
            if r.get("model_release_family_public_id") == session_data["model_release_family_public_id"]
        ]
        return evaluate_rollback_target(
            target_version=target_version, current_version=session_data["version_string"],
            releases=family_releases,
        )

    def execute_rollback(
        self, session_public_id: str, *, target_release_public_id: str, reason: str, admin_id: str,
    ) -> dict[str, Any]:
        plan = self.model_release.create_rollback_plan(
            RollbackPlanCreate(target_release_public_id=target_release_public_id, reason=reason), admin_id,
        )
        self.model_release.validate_rollback_plan(plan["public_id"], admin_id)
        self.model_release.approve_rollback_plan(
            plan["public_id"], RollbackApprovalCreate(comment="MB-07 admin-approved rollback"), admin_id,
        )
        executed = self.model_release.execute_rollback_plan(plan["public_id"], admin_id)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id, {"rollback_plan_public_id": plan["public_id"]},
            )
            self._event(
                connection, session_row["id"], "rollback_executed", stage=None,
                message=f"rolled back to release {target_release_public_id}",
                metadata={"reason": reason},
            )
        return executed

    # -- stage 11: admin review + report -------------------------------------

    def generate_report(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        report = generate_release_report(
            session_public_id=session_public_id,
            checkpoint_validation_report=session_data["checkpoint_validation_report"] or None,
            conversion_report=session_data["conversion_report"] or None,
            quantization_report=session_data["quantization_report"] or None,
            integrity_report=session_data["integrity_report"] or None,
            compatibility_report=session_data["compatibility_report"] or None,
            performance_report=session_data["performance_report"] or None,
            version_string=session_data["version_string"],
            model_release_public_id=session_data["model_release_public_id"],
        )
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(connection, session_public_id, {"release_report_json": report})
            self._event(
                connection, session_row["id"], "release_report_generated", stage="awaiting_admin_review",
                message=f"ready_for_admin_review={report['ready_for_admin_review']}",
            )
            return public_row(self.repository.session(connection, session_public_id))

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_ACTIVATION_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_ACTIVATION_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(
                    f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'"
                )
            status_map = {
                "approve": "in_progress", "reject": "admin_rejected",
                "rollback": "in_progress", "archive": "archived",
            }
            stage = "production_activation" if decision == "approve" else "closed"
            fields = {
                "admin_activation_decision": decision, "admin_activation_decided_by": admin_id,
                "status": status_map[decision], "stage": stage,
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"admin_review_{decision}", stage="awaiting_admin_review",
                message=f"admin decided '{decision}' on the release report", metadata={"admin_id": admin_id},
            )
            return public_row(self.repository.session(connection, session_public_id))

    # -- stage 12: production activation (no Public Chat deployment) ---------

    def activate(self, session_public_id: str, *, quantization_level: str, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "production_activation" or session_data["admin_activation_decision"] != "approve":
            raise ValidationError(
                "session must be at stage 'production_activation' with an 'approve' admin decision"
            )
        entry = session_data["quantization_report"]["levels"].get(quantization_level)
        if not entry or not entry["exported"]:
            raise ValidationError(f"quantization level {quantization_level!r} was not successfully exported")

        config = self._brud_config(session_data["core_model_version_public_id"])
        registered = self.runtime_manager.register_model(
            name=f"brud-{session_data['version_string']}-{quantization_level}",
            path=entry["path"], quantization=quantization_level, context_length=config.context_length,
        )
        self.runtime_manager.load_model(registered["public_id"])

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "runtime_model_public_id": registered["public_id"], "activated_at": _now(),
                    "stage": "closed", "status": "activated",
                },
            )
            self._event(
                connection, session_row["id"], "production_activated", stage="production_activation",
                message=(
                    f"model {registered['public_id']} loaded into MB-04 Runtime -- "
                    "not deployed to Public Chat"
                ),
                metadata={"quantization_level": quantization_level},
            )
            return public_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainReleasePipelineService"]
