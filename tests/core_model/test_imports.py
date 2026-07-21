import pytest

from core_model import (
    InferenceEngine,
    ModelConfig,
    ModelEvaluator,
    ModelExporter,
    ModelStatus,
    ModelTrainer,
    TokenizerManager,
)


def test_core_model_public_imports() -> None:
    assert ModelConfig().status is ModelStatus.NOT_CONFIGURED
    assert ModelStatus.READY.value == "ready"


@pytest.mark.parametrize(
    "operation",
    [
        lambda: TokenizerManager().build(),
        lambda: ModelConfig().validate_for_training(),
        lambda: ModelTrainer().train(),
        lambda: InferenceEngine().generate("hello"),
        lambda: ModelEvaluator().evaluate(),
        lambda: ModelExporter().export(),
    ],
)
def test_phase_one_interfaces_are_explicitly_unavailable(operation) -> None:
    with pytest.raises(NotImplementedError):
        operation()
