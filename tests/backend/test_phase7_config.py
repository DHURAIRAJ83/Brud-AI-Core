from pathlib import Path

import pytest

from backend.core.config import PROJECT_ROOT, Settings


def test_tokenizer_configuration_defaults_are_bounded(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "db.sqlite",
        allowed_data_dir=tmp_path,
        tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports",
        allow_external_storage=True,
    )
    assert settings.tokenizer_default_algorithm == "bpe"
    assert settings.tokenizer_min_vocab_size <= settings.tokenizer_default_vocab_size
    assert settings.tokenizer_default_vocab_size <= settings.tokenizer_max_vocab_size
    assert 0 < settings.tokenizer_character_coverage <= 1
    assert settings.tokenizer_num_threads >= 1


def test_invalid_tokenizer_algorithm_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="algorithm"):
        Settings(
            database_path=tmp_path / "db.sqlite",
            allowed_data_dir=tmp_path,
            tokenizer_default_algorithm="wordpiece",
            allow_external_storage=True,
        )


def test_invalid_tokenizer_vocabulary_bounds_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="vocab"):
        Settings(
            database_path=tmp_path / "db.sqlite",
            allowed_data_dir=tmp_path,
            tokenizer_min_vocab_size=32000,
            tokenizer_max_vocab_size=1000,
            allow_external_storage=True,
        )


def test_tokenizer_directories_stay_under_allowed_storage(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tokenizer_dir"):
        Settings(
            database_path=PROJECT_ROOT / "data" / "database" / "test.sqlite",
            allowed_data_dir=PROJECT_ROOT / "data",
            tokenizer_dir=tmp_path / "outside",
            allow_external_storage=False,
        )
