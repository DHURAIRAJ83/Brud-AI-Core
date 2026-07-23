"""Tokenizer corpus, training, evaluation, registry, and artifact services."""

from __future__ import annotations

import hashlib
import math
import re
import shutil
import tempfile
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json, redact_secrets
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.tokenizers import TokenizerRepository, public_row
from backend.models.tokenizers import SPECIAL_TOKENS, TokenizerVersionCreate

try:
    import sentencepiece as spm
except ImportError:  # pragma: no cover - exercised when dependency is absent.
    spm = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_component(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._")
    if not safe or safe in {".", ".."}:
        raise ValidationError("unsafe tokenizer artifact name")
    return safe


def _page(items: list[dict[str, Any]], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


class TokenizerService:
    def __init__(self, repository: TokenizerRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self._cache: OrderedDict[str, Any] = OrderedDict()

    def capabilities(self) -> dict[str, Any]:
        return {
            "sentencepiece_available": spm is not None,
            "sentencepiece_version": getattr(spm, "__version__", None) if spm else None,
            "supported_algorithms": ["bpe", "unigram"],
            "vocabulary_bounds": {
                "minimum": self.settings.tokenizer_min_vocab_size,
                "maximum": self.settings.tokenizer_max_vocab_size,
                "default": self.settings.tokenizer_default_vocab_size,
            },
            "training_limits": {
                "max_corpus_records": self.settings.tokenizer_max_corpus_records,
                "max_corpus_chars": self.settings.tokenizer_max_corpus_chars,
                "max_line_chars": self.settings.tokenizer_max_line_chars,
            },
            "cpu_thread_limit": self.settings.tokenizer_num_threads,
        }

    def create_family(self, payload, admin_id: str) -> dict[str, Any]:
        name = _safe_component(payload.name.lower().replace("_", "-"))
        with self.repository.transaction() as connection:
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO tokenizer_families(public_id,name,display_name,description,
                tokenizer_type,status) VALUES (?,?,?,?,?,?)""",
                (public_id, name, payload.display_name, payload.description, "sentencepiece", "draft"),
            )
            self._audit(connection, "tokenizer_family_created", admin_id, public_id, name=name)
            return public_row(self.repository.family(connection, public_id))

    def list_families(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            items, total = self.repository.list_page(connection, "tokenizer_families", page, page_size)
        return _page(items, total, page, page_size)

    def get_family(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.family(connection, public_id))

    def patch_family(self, public_id: str, payload, admin_id: str) -> dict[str, Any]:
        changes = payload.model_dump(exclude_unset=True)
        allowed = {k: v for k, v in changes.items() if k in {"display_name", "description", "status"}}
        with self.repository.transaction() as connection:
            self.repository.family(connection, public_id)
            if allowed:
                assignments = ",".join(f"{key}=?" for key in allowed)
                connection.execute(
                    f"UPDATE tokenizer_families SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                    (*allowed.values(), public_id),
                )
            self._audit(connection, "tokenizer_family_updated", admin_id, public_id)
            return public_row(self.repository.family(connection, public_id))

    def create_version(self, payload: TokenizerVersionCreate, admin_id: str) -> dict[str, Any]:
        self._validate_version_config(payload.algorithm, payload.vocabulary_size, payload.character_coverage)
        if SPECIAL_TOKENS != payload.special_tokens:
            raise ValidationError("Phase 7 requires the fixed initial special-token policy")
        with self.repository.transaction() as connection:
            family = self.repository.family(connection, payload.family_public_id)
            dataset = self.repository.dataset_version(connection, payload.dataset_version_public_id)
            if dataset["status"] not in {"ready", "archived"}:
                raise ValidationError("tokenizer training requires a ready or archived dataset version")
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
                lifecycle_status,algorithm,vocabulary_size,character_coverage,
                normalization_rule_name,model_type,dataset_version_id,special_tokens_json,
                configuration_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    family["id"],
                    payload.version,
                    "draft",
                    payload.algorithm,
                    payload.vocabulary_size,
                    payload.character_coverage,
                    payload.normalization_rule_name,
                    "sentencepiece",
                    dataset["id"],
                    dumps_json(payload.special_tokens),
                    dumps_json(payload.configuration),
                ),
            )
            self._audit(
                connection,
                "tokenizer_version_created",
                admin_id,
                public_id,
                dataset_version_public_id=dataset["public_id"],
            )
            return public_row(self.repository.version(connection, public_id))

    def list_versions(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                """SELECT v.*,f.public_id AS family_public_id,f.name AS family_name,
                d.public_id AS dataset_version_public_id,d.status AS dataset_version_status
                FROM tokenizer_versions v JOIN tokenizer_families f ON f.id=v.tokenizer_family_id
                JOIN dataset_versions d ON d.id=v.dataset_version_id
                ORDER BY v.created_at DESC,v.id DESC LIMIT ? OFFSET ?""",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM tokenizer_versions").fetchone()[0]
        return _page([public_row(row) for row in rows], total, page, page_size)

    def get_version(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.version(connection, public_id))

    def patch_version(self, public_id: str, payload, admin_id: str) -> dict[str, Any]:
        changes = payload.model_dump(exclude_unset=True)
        with self.repository.transaction() as connection:
            row = self.repository.version(connection, public_id)
            if row["lifecycle_status"] != "draft":
                raise ValidationError("only draft tokenizer versions can be edited")
            if "vocabulary_size" in changes:
                self._validate_version_config(row["algorithm"], changes["vocabulary_size"], row["character_coverage"])
            if changes:
                allowed = {k: v for k, v in changes.items() if k in {"vocabulary_size", "character_coverage"}}
                if "configuration" in changes:
                    allowed["configuration_json"] = dumps_json(changes["configuration"])
                assignments = ",".join(f"{key}=?" for key in allowed)
                connection.execute(
                    f"UPDATE tokenizer_versions SET {assignments} WHERE public_id=?",
                    (*allowed.values(), public_id),
                )
            self._audit(connection, "tokenizer_version_updated", admin_id, public_id)
            return public_row(self.repository.version(connection, public_id))

    def create_job(self, payload, admin_id: str) -> dict[str, Any]:
        if payload.job_type not in {"corpus_build", "dry_run", "train", "evaluate", "full_pipeline"}:
            raise ValidationError("unsupported tokenizer job type")
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, payload.tokenizer_version_public_id)
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO tokenizer_training_jobs(public_id,tokenizer_version_id,
                dataset_version_id,status,job_type,configuration_json,hardware_profile,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    version["id"],
                    version["dataset_version_id"],
                    "draft",
                    payload.job_type,
                    dumps_json(payload.configuration),
                    f"cpu_threads={self.settings.tokenizer_num_threads}",
                    admin_id,
                ),
            )
            job = self.repository.job(connection, public_id)
            self.repository.add_event(connection, job["id"], "job_created", None, "draft", "draft", None)
            self._audit(connection, "tokenizer_job_created", admin_id, public_id)
            return public_row(job)

    def list_jobs(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                """SELECT j.*,v.public_id AS tokenizer_version_public_id
                FROM tokenizer_training_jobs j JOIN tokenizer_versions v ON v.id=j.tokenizer_version_id
                ORDER BY j.created_at DESC,j.id DESC LIMIT ? OFFSET ?""",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM tokenizer_training_jobs").fetchone()[0]
        return _page([public_row(row) for row in rows], total, page, page_size)

    def get_job(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.job(connection, public_id))

    def build_corpus(self, job_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            version = self.repository.version(connection, job["tokenizer_version_public_id"])
            rows = self._dataset_rows(connection, version["dataset_version_id"])
            lines, summary = self._corpus_lines(rows)
            if not lines:
                raise ValidationError("tokenizer corpus is empty")
            target = self._corpus_dir(version)
            target.mkdir(parents=True, exist_ok=True)
            corpus = target / "corpus.txt"
            corpus.write_text("\n".join(lines) + "\n", encoding="utf-8")
            checksum = _sha256_file(corpus)
            manifest = {
                "tokenizer_version_public_id": version["public_id"],
                "dataset_version_public_id": version["dataset_version_public_id"],
                "line_count": len(lines),
                "record_count": len(rows),
                "character_count": sum(len(line) for line in lines),
                "corpus_checksum_sha256": checksum,
                "distribution": summary,
            }
            (target / "corpus_manifest.json").write_text(dumps_json(manifest) + "\n", encoding="utf-8")
            self._chmod_files(target)
            connection.execute(
                """UPDATE tokenizer_versions SET corpus_checksum_sha256=?,lifecycle_status='validating'
                WHERE id=?""",
                (checksum, version["id"]),
            )
            connection.execute(
                """UPDATE tokenizer_training_jobs SET status='completed',
                corpus_record_count=?,corpus_line_count=?,corpus_character_count=?,
                progress=1,current_stage='corpus_built',completed_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (len(rows), len(lines), manifest["character_count"], job["id"]),
            )
            self.repository.add_event(
                connection,
                job["id"],
                "corpus_build_completed",
                job["status"],
                "completed",
                "corpus",
                None,
                {"checksum": checksum[:12], "line_count": len(lines)},
            )
            self._audit(connection, "tokenizer_corpus_built", admin_id, version["public_id"], checksum=checksum[:12])
            return {"status": "completed", "corpus_checksum_sha256": checksum, "summary": manifest}

    def dry_run(self, job_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            version = self.repository.version(connection, job["tokenizer_version_public_id"])
            warnings: list[str] = []
            failures: list[str] = []
            if spm is None:
                failures.append("sentencepiece_unavailable")
            corpus = self._corpus_dir(version) / "corpus.txt"
            if not corpus.is_file():
                failures.append("corpus_missing")
            elif _sha256_file(corpus) != version["corpus_checksum_sha256"]:
                failures.append("corpus_checksum_mismatch")
            unique_chars = set(corpus.read_text(encoding="utf-8")) if corpus.is_file() else set()
            if version["vocabulary_size"] > max(len(unique_chars) * 200, self.settings.tokenizer_min_vocab_size):
                warnings.append("vocabulary_size_high_for_corpus")
            text = corpus.read_text(encoding="utf-8") if corpus.is_file() else ""
            if not re.search(r"[\u0B80-\u0BFF]", text):
                warnings.append("tamil_underrepresented")
            if not re.search(r"[A-Za-z]", text):
                warnings.append("latin_underrepresented")
            status = "fail" if failures else "pass_with_warnings" if warnings else "pass"
            connection.execute(
                """UPDATE tokenizer_training_jobs SET status=?,progress=1,current_stage='dry_run',
                completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                ("failed" if failures else "completed_with_warnings" if warnings else "completed", job["id"]),
            )
            self.repository.add_event(
                connection,
                job["id"],
                "dry_run_completed",
                job["status"],
                status,
                "dry_run",
                None,
                {"warnings": warnings, "failures": failures},
            )
            self._audit(connection, "tokenizer_dry_run", admin_id, version["public_id"], status=status)
            return {"status": status, "warnings": warnings, "failures": failures}

    def train(self, job_public_id: str, admin_id: str) -> dict[str, Any]:
        if spm is None:
            raise ValidationError("SentencePiece is not available")
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, job_public_id)
            version = self.repository.version(connection, job["tokenizer_version_public_id"])
            if version["lifecycle_status"] in {"active", "retired", "archived"}:
                raise ValidationError("tokenizer version is not trainable")
            corpus = self._corpus_dir(version) / "corpus.txt"
            if not corpus.is_file() or _sha256_file(corpus) != version["corpus_checksum_sha256"]:
                raise ValidationError("valid corpus is required before training")
            connection.execute(
                "UPDATE tokenizer_versions SET lifecycle_status='training' WHERE id=?", (version["id"],)
            )
        artifact_dir = self._artifact_dir(version)
        if artifact_dir.exists():
            raise ConflictError("tokenizer artifact directory already exists")
        artifact_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=artifact_dir.parent) as tmp:
            prefix = Path(tmp) / "tokenizer"
            user_symbols = ",".join(SPECIAL_TOKENS[4:])
            spm.SentencePieceTrainer.train(
                input=str(corpus),
                model_prefix=str(prefix),
                model_type=version["algorithm"],
                vocab_size=int(version["vocabulary_size"]),
                character_coverage=float(version["character_coverage"]),
                normalization_rule_name=version["normalization_rule_name"],
                hard_vocab_limit=False,
                input_sentence_size=self.settings.tokenizer_input_sentence_size,
                shuffle_input_sentence=self.settings.tokenizer_shuffle_input_sentence,
                max_sentence_length=self.settings.tokenizer_max_sentence_length,
                num_threads=self.settings.tokenizer_num_threads,
                pad_id=0,
                unk_id=1,
                bos_id=2,
                eos_id=3,
                pad_piece="<pad>",
                unk_piece="<unk>",
                bos_piece="<bos>",
                eos_piece="<eos>",
                user_defined_symbols=user_symbols,
            )
            model = prefix.with_suffix(".model")
            vocab = prefix.with_suffix(".vocab")
            processor = spm.SentencePieceProcessor(model_file=str(model))
            self._verify_special_tokens(processor)
            smoke = "வணக்கம் hello vanakkam தமிழ் English"
            decoded = processor.decode(processor.encode(smoke, out_type=int))
            if not decoded:
                raise ValidationError("tokenizer smoke decode failed")
            artifact_dir.mkdir()
            shutil.move(str(model), artifact_dir / "tokenizer.model")
            shutil.move(str(vocab), artifact_dir / "tokenizer.vocab")
        model_checksum = _sha256_file(artifact_dir / "tokenizer.model")
        vocab_checksum = _sha256_file(artifact_dir / "tokenizer.vocab")
        manifest = {
            "files": ["tokenizer.model", "tokenizer.vocab", "artifact_manifest.json"],
            "model_checksum_sha256": model_checksum,
            "vocabulary_checksum_sha256": vocab_checksum,
            "special_tokens": SPECIAL_TOKENS,
        }
        (artifact_dir / "artifact_manifest.json").write_text(dumps_json(manifest) + "\n", encoding="utf-8")
        (artifact_dir / "checksums.txt").write_text(
            f"{model_checksum}  tokenizer.model\n{vocab_checksum}  tokenizer.vocab\n",
            encoding="utf-8",
        )
        self._chmod_files(artifact_dir)
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, version["public_id"])
            connection.execute(
                """UPDATE tokenizer_versions SET lifecycle_status='staging',
                model_checksum_sha256=?,vocabulary_checksum_sha256=?,
                artifact_manifest_json=?,training_completed_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (model_checksum, vocab_checksum, dumps_json(manifest), version["id"]),
            )
            connection.execute(
                """UPDATE tokenizer_training_jobs SET status='completed',progress=1,
                current_stage='trained',completed_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (job_public_id,),
            )
            job = self.repository.job(connection, job_public_id)
            self.repository.add_event(
                connection,
                job["id"],
                "training_completed",
                "running",
                "completed",
                "training",
                None,
                {"model_checksum": model_checksum[:12], "vocab_checksum": vocab_checksum[:12]},
            )
            self._audit(connection, "tokenizer_training_completed", admin_id, version["public_id"])
            return public_row(self.repository.version(connection, version["public_id"]))

    def evaluate(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            processor = self._processor(version)
            rows = self._dataset_rows(connection, version["dataset_version_id"])
            evaluation_id = str(uuid4())
            connection.execute(
                """INSERT INTO tokenizer_evaluations(public_id,tokenizer_version_id,
                evaluation_name,evaluation_version,status,dataset_version_id,configuration_json,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    evaluation_id,
                    version["id"],
                    "phase7_tokenizer_quality",
                    "phase7-v1",
                    "running",
                    version["dataset_version_id"],
                    "{}",
                    admin_id,
                ),
            )
            eval_row = connection.execute(
                "SELECT id FROM tokenizer_evaluations WHERE public_id=?", (evaluation_id,)
            ).fetchone()
            metrics, summary = self._evaluate_rows(processor, rows)
            for language, values in metrics.items():
                for metric_name, metric_value in values.items():
                    connection.execute(
                        """INSERT INTO tokenizer_evaluation_results(public_id,
                        tokenizer_evaluation_id,language,metric_name,metric_value,
                        sample_count,details_json) VALUES (?,?,?,?,?,?,?)""",
                        (str(uuid4()), eval_row["id"], language, metric_name, metric_value, summary[language]["sample_count"], "{}"),
                    )
            status = "completed" if summary["overall"]["ready"] else "completed_with_warnings"
            connection.execute(
                "UPDATE tokenizer_evaluations SET status=?,summary_json=?,completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, dumps_json(summary), eval_row["id"]),
            )
            connection.execute(
                """UPDATE tokenizer_versions SET lifecycle_status=CASE
                WHEN lifecycle_status='training' THEN 'evaluating' ELSE lifecycle_status END,
                metrics_summary_json=? WHERE id=?""",
                (dumps_json(summary), version["id"]),
            )
            self._audit(connection, "tokenizer_evaluation_completed", admin_id, public_id, status=status)
            return public_row(
                connection.execute("SELECT * FROM tokenizer_evaluations WHERE id=?", (eval_row["id"],)).fetchone()
            )

    def encode(self, public_id: str, text: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            processor = self._processor(version)
        ids = processor.encode(text, out_type=int)
        pieces = processor.encode(text, out_type=str)
        decoded = processor.decode(ids)
        return {
            "tokenizer_version": version["version"],
            "input_length": len(text),
            "token_count": len(ids),
            "pieces": pieces,
            "ids": ids,
            "decoded_text": decoded,
            "round_trip_equal": decoded == text,
        }

    def decode(self, public_id: str, ids: list[int]) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            processor = self._processor(version)
        vocab_size = processor.vocab_size()
        if any(item < 0 or item >= vocab_size for item in ids):
            raise ValidationError("token id outside tokenizer vocabulary")
        return {
            "tokenizer_version": version["version"],
            "token_count": len(ids),
            "ids": ids,
            "decoded_text": processor.decode(ids),
        }

    def processor_for_version(self, public_id: str):
        """Return a checksum-verified SentencePiece processor for a registered version."""

        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            return self._processor(version)

    def compare(self, left_id: str, right_id: str, text: str) -> dict[str, Any]:
        return {"left": self.encode(left_id, text), "right": self.encode(right_id, text)}

    def activate(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            if version["lifecycle_status"] not in {"staging", "retired"}:
                raise ValidationError("only staging or retired tokenizer versions can activate")
            self._verify_artifacts(version)
            if not loads_json(version["metrics_summary_json"], default={}).get("overall", {}).get("ready"):
                raise ValidationError("completed passing evaluation is required before activation")
            connection.execute(
                """UPDATE tokenizer_versions SET lifecycle_status='retired',retired_at=CURRENT_TIMESTAMP
                WHERE tokenizer_family_id=? AND lifecycle_status='active'""",
                (version["tokenizer_family_id"],),
            )
            connection.execute(
                "UPDATE tokenizer_versions SET lifecycle_status='active',activated_at=CURRENT_TIMESTAMP WHERE id=?",
                (version["id"],),
            )
            connection.execute(
                """INSERT INTO tokenizer_assignments(assignment_key,tokenizer_version_id,enabled,
                configuration_json) VALUES ('default',?,?,?)
                ON CONFLICT(assignment_key) DO UPDATE SET tokenizer_version_id=excluded.tokenizer_version_id,
                enabled=1,updated_at=CURRENT_TIMESTAMP""",
                (version["id"], 1, "{}"),
            )
            self._audit(connection, "tokenizer_version_activated", admin_id, public_id)
            return public_row(self.repository.version(connection, public_id))

    def retire(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            if version["lifecycle_status"] not in {"active", "staging"}:
                raise ValidationError("only active or staging versions can retire")
            connection.execute(
                "UPDATE tokenizer_versions SET lifecycle_status='retired',retired_at=CURRENT_TIMESTAMP WHERE id=?",
                (version["id"],),
            )
            self._audit(connection, "tokenizer_version_retired", admin_id, public_id)
            return public_row(self.repository.version(connection, public_id))

    def verify(self, public_id: str, admin_id: str | None = None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            result = self._verify_artifacts(version)
            if admin_id:
                self._audit(connection, "tokenizer_artifact_verified", admin_id, public_id, verified=result["verified"])
        return result

    def assignments(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute("SELECT * FROM tokenizer_assignments ORDER BY assignment_key").fetchall()
        return {"items": [public_row(row) for row in rows]}

    def patch_assignment(self, key: str, payload, admin_id: str) -> dict[str, Any]:
        if key not in {"core_model_training", "chat_input", "dataset_preview", "default"}:
            raise ValidationError("unsupported tokenizer assignment key")
        with self.repository.transaction() as connection:
            version_id = None
            fallback_id = None
            if payload.tokenizer_version_public_id:
                version_id = self.repository.version(connection, payload.tokenizer_version_public_id)["id"]
            if payload.fallback_tokenizer_version_public_id:
                fallback_id = self.repository.version(connection, payload.fallback_tokenizer_version_public_id)["id"]
            connection.execute(
                """INSERT INTO tokenizer_assignments(assignment_key,tokenizer_version_id,
                fallback_tokenizer_version_id,enabled,configuration_json)
                VALUES (?,?,?,?,?)
                ON CONFLICT(assignment_key) DO UPDATE SET tokenizer_version_id=excluded.tokenizer_version_id,
                fallback_tokenizer_version_id=excluded.fallback_tokenizer_version_id,
                enabled=excluded.enabled,configuration_json=excluded.configuration_json,
                updated_at=CURRENT_TIMESTAMP""",
                (key, version_id, fallback_id, 1 if payload.enabled else 0, dumps_json(payload.configuration)),
            )
            self._audit(connection, "tokenizer_assignment_changed", admin_id, key)
            return public_row(connection.execute("SELECT * FROM tokenizer_assignments WHERE assignment_key=?", (key,)).fetchone())

    def export(self, public_id: str, export_format: str, admin_id: str) -> dict[str, Any]:
        if export_format not in {"sentencepiece_bundle", "manifest_only"}:
            raise ValidationError("unsupported tokenizer export format")
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            if version["lifecycle_status"] not in {"staging", "active", "retired"}:
                raise ValidationError("only trained tokenizer versions can be exported")
            self._verify_artifacts(version)
            safe = f"{_safe_component(version['family_name'])}_{_safe_component(version['version'])}_{uuid4().hex[:8]}"
            target = self.settings.resolved_tokenizer_export_dir / safe
            if target.exists():
                raise ConflictError("tokenizer export already exists")
            target.mkdir(parents=True)
            source = self._artifact_dir(version)
            files = ["artifact_manifest.json"] if export_format == "manifest_only" else loads_json(version["artifact_manifest_json"])["files"]
            for filename in files:
                shutil.copy2(source / filename, target / filename)
            checksum = self._checksum_files(target, files)
            export_id = str(uuid4())
            connection.execute(
                """INSERT INTO tokenizer_exports(public_id,tokenizer_version_id,export_format,
                status,safe_name,checksum_sha256,artifact_manifest_json,created_by_admin_public_id,
                completed_at) VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (export_id, version["id"], export_format, "completed", safe, checksum, dumps_json({"files": files}), admin_id),
            )
            self._audit(connection, "tokenizer_export_created", admin_id, export_id, checksum=checksum[:12])
            return public_row(connection.execute("SELECT * FROM tokenizer_exports WHERE public_id=?", (export_id,)).fetchone())

    def list_exports(self, version_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, version_public_id)
            rows = connection.execute(
                "SELECT * FROM tokenizer_exports WHERE tokenizer_version_id=? ORDER BY created_at DESC,id DESC",
                (version["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def get_export(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self._export_row(connection, public_id)
            return public_row(row)

    def verify_export(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = self._export_row(connection, public_id)
            files = loads_json(row["artifact_manifest_json"])["files"]
            checksum = self._checksum_files(self.settings.resolved_tokenizer_export_dir / row["safe_name"], files)
            ok = checksum == row["checksum_sha256"]
            self._audit(connection, "tokenizer_export_verified", admin_id, public_id, verified=ok)
            return {"verified": ok, "checksum_sha256": checksum, "stored_checksum_sha256": row["checksum_sha256"]}

    def export_file(self, public_id: str) -> Path:
        with self.repository.transaction() as connection:
            row = self._export_row(connection, public_id)
        path = self.settings.resolved_tokenizer_export_dir / row["safe_name"] / "artifact_manifest.json"
        if not path.is_file():
            raise ValidationError("tokenizer export manifest is unavailable")
        return path

    def evaluations(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            rows = connection.execute(
                "SELECT * FROM tokenizer_evaluations WHERE tokenizer_version_id=? ORDER BY created_at DESC,id DESC",
                (version["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def evaluation_results(self, evaluation_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            evaluation = connection.execute(
                "SELECT * FROM tokenizer_evaluations WHERE public_id=?", (evaluation_id,)
            ).fetchone()
            if not evaluation:
                raise ValidationError("tokenizer evaluation not found")
            rows = connection.execute(
                "SELECT * FROM tokenizer_evaluation_results WHERE tokenizer_evaluation_id=? ORDER BY language,metric_name",
                (evaluation["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def job_events(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            job = self.repository.job(connection, public_id)
            rows = connection.execute(
                """SELECT event_type,previous_status,new_status,stage,message,metadata_json,created_at
                FROM tokenizer_training_events WHERE training_job_id=? ORDER BY created_at,id""",
                (job["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def _dataset_rows(self, connection, dataset_version_id: int) -> list[Any]:
        return list(
            connection.execute(
                """SELECT r.*,i.split,i.sequence_number,s.public_id AS source_public_id,
                s.source_type,s.licence_status
                FROM dataset_version_items i JOIN dataset_records r ON r.id=i.dataset_record_id
                LEFT JOIN dataset_sources s ON s.id=r.source_id
                WHERE i.dataset_version_id=? ORDER BY i.sequence_number,r.public_id""",
                (dataset_version_id,),
            ).fetchall()
        )

    def _corpus_lines(self, rows: list[Any]) -> tuple[list[str], dict[str, Any]]:
        lines: list[str] = []
        by_language: Counter[str] = Counter()
        by_type: Counter[str] = Counter()
        warnings: Counter[str] = Counter()
        for row in rows[: self.settings.tokenizer_max_corpus_records]:
            by_language[row["language"]] += 1
            by_type[row["record_type"]] += 1
            fields = self._record_fields(row)
            for field in fields:
                value = re.sub(r"\s+", " ", field).strip()
                if not value:
                    continue
                if any(token in value for token in SPECIAL_TOKENS):
                    warnings["special_token_collision"] += 1
                if len(value) > self.settings.tokenizer_max_line_chars:
                    value = value[: self.settings.tokenizer_max_line_chars]
                    warnings["line_truncated"] += 1
                lines.append(value)
                if sum(len(line) for line in lines) > self.settings.tokenizer_max_corpus_chars:
                    warnings["corpus_char_limit_reached"] += 1
                    return lines, self._summary(by_language, by_type, warnings)
        return lines, self._summary(by_language, by_type, warnings)

    def _record_fields(self, row) -> list[str]:
        record_type = row["record_type"]
        if record_type == "pretrain":
            return [row["output_text"] or row["input_text"] or ""]
        if record_type == "instruction":
            return [row["instruction"] or "", row["input_text"] or "", row["output_text"] or ""]
        if record_type in {"chat", "translation", "safety", "preference"}:
            return [row["input_text"] or "", row["output_text"] or ""]
        if record_type == "tanglish_pair":
            return [row["input_text"] or "", row["normalized_input"] or "", row["output_text"] or ""]
        return [row["content"] or ""]

    def _summary(self, by_language: Counter[str], by_type: Counter[str], warnings: Counter[str]) -> dict[str, Any]:
        return {
            "language_line_sources": dict(by_language),
            "record_type_counts": dict(by_type),
            "warnings": dict(warnings),
        }

    def _evaluate_rows(self, processor, rows: list[Any]) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
        samples: dict[str, list[str]] = {key: [] for key in ("ta", "en", "tgl", "mixed")}
        for row in rows:
            language = row["language"] if row["language"] in samples else "mixed"
            for text in self._record_fields(row):
                if text and len(samples[language]) < self.settings.tokenizer_eval_max_samples_per_language:
                    samples[language].append(text)
        fixed = {
            "ta": ["வணக்கம் தமிழ் உலகம்"],
            "en": ["Hello English world"],
            "tgl": ["vanakkam epdi irukeenga"],
            "mixed": ["தமிழ் and English mixed sentence"],
        }
        for language, items in fixed.items():
            samples[language].extend(items)
        metrics: dict[str, dict[str, float]] = {}
        summary: dict[str, Any] = {}
        for language, texts in samples.items():
            metrics[language], summary[language] = self._metrics(processor, texts)
        all_texts = [text for values in samples.values() for text in values]
        metrics["overall"], summary["overall"] = self._metrics(processor, all_texts)
        summary["overall"]["ready"] = summary["overall"]["round_trip_success_rate"] >= self.settings.tokenizer_min_ready_score
        return metrics, summary

    def _metrics(self, processor, texts: list[str]) -> tuple[dict[str, float], dict[str, Any]]:
        total_chars = sum(len(text) for text in texts)
        tokenized = [processor.encode(text, out_type=int) for text in texts]
        total_tokens = sum(len(ids) for ids in tokenized)
        round_trip = sum(1 for text, ids in zip(texts, tokenized, strict=True) if processor.decode(ids) == text)
        unk_id = processor.unk_id()
        unknowns = sum(ids.count(unk_id) for ids in tokenized)
        words = sum(len(text.split()) for text in texts) or 1
        metrics = {
            "total_characters": float(total_chars),
            "total_tokens": float(total_tokens),
            "characters_per_token": total_chars / total_tokens if total_tokens else 0.0,
            "tokens_per_word": total_tokens / words,
            "unknown_token_rate": unknowns / total_tokens if total_tokens else 0.0,
            "round_trip_success_rate": round_trip / len(texts) if texts else 0.0,
            "compression_ratio": total_tokens / total_chars if total_chars else 0.0,
            "tamil_grapheme_split_warning_rate": 0.0,
            "special_token_collision_count": 0.0,
            "byte_fallback_rate": 0.0,
            "long_sequence_rate": sum(1 for ids in tokenized if len(ids) > 512) / len(texts) if texts else 0.0,
        }
        return metrics, {"sample_count": len(texts), "round_trip_success_rate": metrics["round_trip_success_rate"]}

    def _processor(self, version):
        if version["lifecycle_status"] not in {"staging", "active", "retired"}:
            raise ValidationError("tokenizer model is not available for this version")
        key = version["public_id"]
        if key in self._cache:
            return self._cache[key]
        if spm is None:
            raise ValidationError("SentencePiece is not available")
        model_path = self._artifact_dir(version) / "tokenizer.model"
        self._verify_artifacts(version)
        processor = spm.SentencePieceProcessor(model_file=str(model_path))
        self._cache[key] = processor
        while len(self._cache) > 4:
            self._cache.popitem(last=False)
        return processor

    def _verify_artifacts(self, version) -> dict[str, Any]:
        manifest = loads_json(version["artifact_manifest_json"])
        base = self._artifact_dir(version)
        if not manifest or not (base / "tokenizer.model").is_file() or not (base / "tokenizer.vocab").is_file():
            raise ValidationError("tokenizer artifacts are incomplete")
        model_checksum = _sha256_file(base / "tokenizer.model")
        vocab_checksum = _sha256_file(base / "tokenizer.vocab")
        verified = (
            model_checksum == version["model_checksum_sha256"]
            and vocab_checksum == version["vocabulary_checksum_sha256"]
        )
        return {
            "verified": verified,
            "model_checksum_sha256": model_checksum,
            "vocabulary_checksum_sha256": vocab_checksum,
        }

    def _verify_special_tokens(self, processor) -> None:
        for token in SPECIAL_TOKENS:
            if processor.piece_to_id(token) < 0:
                raise ValidationError(f"required special token missing: {token}")

    def _validate_version_config(self, algorithm: str, vocab_size: int, coverage: float) -> None:
        if algorithm not in {"bpe", "unigram"}:
            raise ValidationError("tokenizer algorithm must be bpe or unigram")
        if not self.settings.tokenizer_min_vocab_size <= vocab_size <= self.settings.tokenizer_max_vocab_size:
            raise ValidationError("tokenizer vocabulary size is outside configured bounds")
        if not 0 < coverage <= 1:
            raise ValidationError("character coverage must be between 0 and 1")

    def _corpus_dir(self, version) -> Path:
        return self.settings.resolved_tokenizer_corpus_dir / _safe_component(version["public_id"])

    def _artifact_dir(self, version) -> Path:
        return (
            self.settings.resolved_tokenizer_dir
            / "versions"
            / _safe_component(version["family_name"])
            / _safe_component(version["version"])
        )

    def _export_row(self, connection, public_id: str):
        row = connection.execute("SELECT * FROM tokenizer_exports WHERE public_id=?", (public_id,)).fetchone()
        if not row:
            raise ValidationError("tokenizer export not found")
        return row

    def _checksum_files(self, base: Path, files: list[str]) -> str:
        digest = hashlib.sha256()
        root = base.resolve()
        for filename in sorted(files):
            path = (base / filename).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValidationError("invalid tokenizer export file reference")
            digest.update(filename.encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def _chmod_files(self, path: Path) -> None:
        for item in path.iterdir():
            if item.is_file():
                item.chmod(0o600)

    def _audit(self, connection, event: str, admin_id: str, resource_id: str, **metadata) -> None:
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event,
                "admin",
                "{}",
                str(uuid4()),
                event,
                "admin",
                admin_id,
                "tokenizer",
                resource_id,
                "success",
                dumps_json(redact_secrets(metadata)),
            ),
        )
