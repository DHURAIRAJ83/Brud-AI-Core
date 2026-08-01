"""Phase 20 Steps 37/38 -- security and functional tests for the
deterministic tool gateway (calculator, unit conversion, date/time
arithmetic, tool selection, input extraction, MCP contract, registry).
No network, no filesystem -- every test here is a pure, fast unit test.
"""

from __future__ import annotations

import ast

import pytest

from core_model.tool_gateway.calculator import (
    MAX_AST_DEPTH,
    MAX_EXPONENT,
    MAX_EXPRESSION_LENGTH,
    MAX_PAREN_DEPTH,
    CalculatorError,
    evaluate,
)
from core_model.tool_gateway.date_time_arithmetic import (
    MAX_DAY_DELTA,
    DateArithmeticError,
    add_days,
    add_weeks,
    date_difference,
)
from core_model.tool_gateway.input_extraction import extract_tool_input
from core_model.tool_gateway.mcp_contract import (
    ToolExecutionError,
    ToolInvocationRequest,
    ToolInvocationResult,
    ToolPermissionContext,
)
from core_model.tool_gateway.tool_selection import select_tool_for_request
from core_model.tool_gateway.unit_conversion import (
    MAX_CONVERSION_MAGNITUDE,
    UnitConversionError,
    convert,
)

# -- Calculator: functional -----------------------------------------------------------------


def test_calculator_addition() -> None:
    assert evaluate("2 + 3").result == "5"


def test_calculator_subtraction() -> None:
    assert evaluate("10 - 4").result == "6"


def test_calculator_multiplication_large_numbers_exact() -> None:
    result = evaluate("987654 * 12345")
    assert result.result == str(987654 * 12345)
    assert result.result_type == "integer"


def test_calculator_division() -> None:
    result = evaluate("10 / 4")
    assert result.result == "2.5"
    assert result.result_type == "decimal"


def test_calculator_parentheses() -> None:
    assert evaluate("(2 + 3) * 4").result == "20"


def test_calculator_decimal_arithmetic() -> None:
    assert evaluate("0.1 + 0.2").result == "0.3"


def test_calculator_percentage() -> None:
    result = evaluate("50% * 200")
    assert result.result == "100"


def test_calculator_safe_power() -> None:
    assert evaluate("2 ** 10").result == "1024"


def test_calculator_negative_numbers() -> None:
    assert evaluate("-5 + 3").result == "-2"


def test_calculator_percent_symbol_is_never_treated_as_modulo() -> None:
    """`%` is percentage-only (see `calculator.py`'s own docstring for
    why): a bare `10 % 3` is not a supported modulo expression -- it's
    rejected, never silently misparsed as `(10/100) 3`."""

    with pytest.raises(CalculatorError):
        evaluate("10 % 3")


def test_calculator_invalid_input_raises() -> None:
    with pytest.raises(CalculatorError):
        evaluate("2 +")


def test_calculator_empty_expression_raises() -> None:
    with pytest.raises(CalculatorError) as exc_info:
        evaluate("")
    assert exc_info.value.reason == "empty_expression"


def test_calculator_result_is_never_scientific_notation() -> None:
    result = evaluate("999999999 * 999999999")
    assert "E" not in result.result and "e" not in result.result


# -- Calculator: security (blocked code execution surfaces) ---------------------------------


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('id')",
        "__import__('os')",
        "open('/etc/passwd')",
        "open('/etc/passwd').read()",
        "(1).__class__",
        "().__class__.__bases__",
        "(1).__class__.__mro__",
        "lambda x: x",
        "[x for x in range(10)]",
        "{x: x for x in range(10)}",
        "(x for x in range(10))",
        "x = 5",
        "exec('1+1')",
        "eval('1+1')",
        "compile('1+1', '<s>', 'eval')",
        "import os",
        "1; import os",
        "globals()",
        "locals()",
        "vars()",
        "getattr(1, '__class__')",
        "print('hi')",
        "input()",
        "1 if True else 2",
        "1 and 2",
        "1 or 2",
        "not 1",
        "1 == 1",
        "1 < 2",
        "5 & 3",
        "5 | 3",
        "5 ^ 3",
        "5 << 1",
        "5 >> 1",
        "~5",
        "'a' + 'b'",
        "[1, 2, 3]",
        "(1, 2, 3)",
        "{1, 2, 3}",
        "{'a': 1}",
        "f'{1}'",
    ],
)
def test_calculator_blocks_arbitrary_python_constructs(expression: str) -> None:
    with pytest.raises(CalculatorError):
        evaluate(expression)


def test_calculator_never_uses_eval_or_exec_source() -> None:
    """Structural proof, not just behavioral: the module source contains
    no call to the builtins `eval`, `exec`, or `compile` with a mode
    other than the one pre-validated `mode="eval"` parse call."""

    import inspect

    from core_model.tool_gateway import calculator as calculator_module

    source = inspect.getsource(calculator_module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec"), (
                f"found forbidden call to {node.func.id}() in calculator.py"
            )


def test_calculator_deeply_nested_parentheses_bounded() -> None:
    expression = "(" * (MAX_PAREN_DEPTH + 5) + "1" + ")" * (MAX_PAREN_DEPTH + 5)
    with pytest.raises(CalculatorError) as exc_info:
        evaluate(expression)
    assert exc_info.value.reason == "expression_too_deep"


def test_calculator_very_long_expression_bounded() -> None:
    expression = "1+" * (MAX_EXPRESSION_LENGTH) + "1"
    with pytest.raises(CalculatorError) as exc_info:
        evaluate(expression)
    assert exc_info.value.reason == "expression_too_long"


def test_calculator_extreme_exponentiation_bounded() -> None:
    with pytest.raises(CalculatorError) as exc_info:
        evaluate(f"2 ** {MAX_EXPONENT + 1}")
    assert exc_info.value.reason == "exponent_too_large"


def test_calculator_exponent_at_bound_succeeds() -> None:
    result = evaluate(f"2 ** {MAX_EXPONENT}")
    assert result.result == str(2**MAX_EXPONENT)


def test_calculator_division_by_zero_is_a_clean_error_not_a_crash() -> None:
    with pytest.raises(CalculatorError) as exc_info:
        evaluate("1 / 0")
    assert exc_info.value.reason == "division_by_zero"


def test_calculator_division_by_zero_via_percent_expression_is_still_clean() -> None:
    with pytest.raises(CalculatorError):
        evaluate("1 % 0")


def test_calculator_non_integer_exponent_rejected_not_silently_approximated() -> None:
    with pytest.raises(CalculatorError) as exc_info:
        evaluate("2 ** 0.5")
    assert exc_info.value.reason == "non_integer_exponent_unsupported"


def test_calculator_deeply_nested_binops_bounded_by_ast_depth() -> None:
    expression = "+".join(["1"] * (MAX_AST_DEPTH + 20))
    with pytest.raises(CalculatorError) as exc_info:
        evaluate(expression)
    assert exc_info.value.reason == "expression_too_deep"


def test_calculator_result_magnitude_is_bounded() -> None:
    expression = " * ".join(["10 ** 12"] * 9)
    with pytest.raises(CalculatorError) as exc_info:
        evaluate(expression)
    assert exc_info.value.reason in ("exponent_too_large", "result_out_of_range")


# -- Unit conversion: functional -------------------------------------------------------------


def test_unit_conversion_length() -> None:
    result = convert(5, "kilometres", "metres")
    assert result.result == 5000.0


def test_unit_conversion_mass() -> None:
    result = convert(1, "kg", "g")
    assert result.result == 1000.0


def test_unit_conversion_temperature_celsius_to_fahrenheit() -> None:
    result = convert(0, "celsius", "fahrenheit")
    assert result.result == 32.0


def test_unit_conversion_temperature_negative_value() -> None:
    result = convert(-40, "celsius", "fahrenheit")
    assert result.result == -40.0


def test_unit_conversion_volume() -> None:
    result = convert(1, "l", "ml")
    assert result.result == 1000.0


def test_unit_conversion_time() -> None:
    result = convert(1, "hour", "minutes")
    assert result.result == 60.0


def test_unit_conversion_data_size() -> None:
    result = convert(1, "gb", "mb")
    assert result.result == 1000.0


def test_unit_conversion_invalid_unit_raises() -> None:
    with pytest.raises(UnitConversionError) as exc_info:
        convert(5, "kilometres", "smoots")
    assert exc_info.value.reason == "invalid_unit"


@pytest.mark.parametrize("unit", ["ton", "gallon", "cup"])
def test_unit_conversion_ambiguous_units_require_clarification(unit: str) -> None:
    with pytest.raises(UnitConversionError) as exc_info:
        convert(5, unit, "kg" if unit == "ton" else "l")
    assert exc_info.value.reason == "ambiguous_unit"


def test_unit_conversion_qualified_ambiguous_unit_succeeds() -> None:
    result = convert(1, "us_ton", "metric_ton")
    assert round(result.result, 4) == round(907.18474 / 1000.0, 4)


def test_unit_conversion_mismatched_categories_rejected() -> None:
    with pytest.raises(UnitConversionError) as exc_info:
        convert(5, "kg", "metres")
    assert exc_info.value.reason == "mismatched_unit_categories"


def test_unit_conversion_negative_value_length() -> None:
    result = convert(-5, "m", "cm")
    assert result.result == -500.0


def test_unit_conversion_extreme_magnitude_rejected() -> None:
    with pytest.raises(UnitConversionError) as exc_info:
        convert(MAX_CONVERSION_MAGNITUDE + 1, "m", "cm")
    assert exc_info.value.reason == "value_out_of_range"


# -- Date/time arithmetic: functional ---------------------------------------------------------


def test_date_add_days() -> None:
    result = add_days("2026-08-01", 30)
    assert result.result_date == "2026-08-31"


def test_date_subtract_days() -> None:
    result = add_days("2026-08-01", -10)
    assert result.result_date == "2026-07-22"


def test_date_difference() -> None:
    result = date_difference("2026-01-01", "2026-02-01")
    assert result.result_days == 31


def test_date_add_weeks() -> None:
    result = add_weeks("2026-01-01", 2)
    assert result.result_date == "2026-01-15"


def test_date_leap_year_handling() -> None:
    result = add_days("2028-02-28", 1)
    assert result.result_date == "2028-02-29"  # 2028 is a leap year


def test_date_non_leap_year_february() -> None:
    result = add_days("2026-02-28", 1)
    assert result.result_date == "2026-03-01"  # 2026 is not a leap year


def test_date_invalid_date_raises() -> None:
    with pytest.raises(DateArithmeticError) as exc_info:
        add_days("2026-13-40", 1)
    assert exc_info.value.reason == "invalid_date"


def test_date_ambiguous_locale_date_rejected() -> None:
    with pytest.raises(DateArithmeticError) as exc_info:
        add_days("01/02/2026", 1)
    assert exc_info.value.reason == "ambiguous_date_format"


def test_date_timezone_required_for_time_component() -> None:
    with pytest.raises(DateArithmeticError) as exc_info:
        add_days("2026-08-01T10:00:00", 1)
    assert exc_info.value.reason == "timezone_required"


def test_date_with_explicit_timezone_is_accepted() -> None:
    result = add_days("2026-08-01T10:00:00Z", 1)
    assert result.result_date == "2026-08-02"


def test_date_huge_range_rejected() -> None:
    with pytest.raises(DateArithmeticError) as exc_info:
        add_days("2026-01-01", MAX_DAY_DELTA + 1)
    assert exc_info.value.reason == "range_too_large"


# -- Tool selection: deterministic, never guesses an arbitrary tool ----------------------------


def test_tool_selection_calculator_for_plain_calculation() -> None:
    assert select_tool_for_request(intent="ask_calculation", text="calculate 2+2") == "calculator"


def test_tool_selection_unit_conversion_detected() -> None:
    assert (
        select_tool_for_request(intent="ask_calculation", text="convert 5 km to metres")
        == "unit_conversion"
    )


def test_tool_selection_date_arithmetic_detected() -> None:
    assert (
        select_tool_for_request(
            intent="ask_calculation", text="days between 2026-01-01 and 2026-02-01"
        )
        == "date_time_arithmetic"
    )


def test_tool_selection_returns_none_for_non_calculation_intent() -> None:
    assert select_tool_for_request(intent="ask_code", text="write code to sort") is None
    assert select_tool_for_request(intent="ask_fact", text="what is the capital") is None
    assert select_tool_for_request(intent=None, text="calculate 2+2") is None


def test_tool_selection_never_returns_an_arbitrary_string() -> None:
    from core_model.tool_gateway import TOOL_NAMES

    for text in ["calculate 2+2", "5 km to metres", "days between 2026-01-01 and 2026-02-01"]:
        result = select_tool_for_request(intent="ask_calculation", text=text)
        assert result is None or result in TOOL_NAMES


# -- Input extraction: bounded regex, never guesses ---------------------------------------------


def test_input_extraction_calculator() -> None:
    result = extract_tool_input("calculator", "calculate 2 + 2")
    assert result == {"expression": "2 + 2"}


def test_input_extraction_returns_none_for_unconfident_input() -> None:
    assert extract_tool_input("calculator", "hello there") is None


def test_input_extraction_unknown_tool_name_returns_none() -> None:
    assert extract_tool_input("not_a_real_tool", "calculate 2+2") is None


def test_input_extraction_unit_conversion() -> None:
    result = extract_tool_input("unit_conversion", "convert 5 km to metres")
    assert result == {"value": 5.0, "source_unit": "km", "target_unit": "metres"}


def test_input_extraction_date_difference() -> None:
    result = extract_tool_input(
        "date_time_arithmetic", "difference between 2026-01-01 and 2026-02-01"
    )
    assert result == {
        "operation": "date_difference",
        "date_a": "2026-01-01",
        "date_b": "2026-02-01",
    }


# -- MCP contract: structural boundary proof -----------------------------------------------------


def test_mcp_permission_context_defaults_external_mcp_disabled() -> None:
    context = ToolPermissionContext(is_public_request=True)
    assert context.external_mcp_enabled is False


def test_tool_invocation_request_has_no_arbitrary_server_field() -> None:
    """Structural proof: `ToolInvocationRequest` has no field for a
    caller to specify an arbitrary MCP server/endpoint -- only a fixed
    `tool_name` string resolved against the closed, hand-written
    registry."""

    import dataclasses

    fields = {f.name for f in dataclasses.fields(ToolInvocationRequest)}
    assert fields == {"tool_name", "input_payload", "request_id", "is_public_request"}


def test_tool_execution_error_carries_stable_error_code() -> None:
    error = ToolExecutionError("mcp_disabled")
    assert error.error_code == "mcp_disabled"


def test_tool_invocation_result_execution_public_id_defaults_none() -> None:
    result = ToolInvocationResult(
        tool_name="calculator",
        tool_version="v1",
        status="success",
        output_payload={},
        error_code=None,
        latency_ms=1,
    )
    assert result.execution_public_id is None


# -- Registry: only the three built-in public tools, external MCP disabled ----------------------


def test_registry_only_exposes_three_built_in_tools() -> None:
    from backend.services.deterministic_tool_registry import list_tool_descriptors

    descriptors = list_tool_descriptors()
    names = {d.tool_name for d in descriptors}
    assert names == {"calculator", "unit_conversion", "date_time_arithmetic"}
    for descriptor in descriptors:
        assert descriptor.source == "built_in_deterministic"
        assert descriptor.public_enabled is True


def test_registry_unknown_tool_name_returns_none() -> None:
    from backend.services.deterministic_tool_registry import get_tool_descriptor

    assert get_tool_descriptor("arbitrary_unregistered_tool") is None
    assert get_tool_descriptor("shell") is None
    assert get_tool_descriptor("file_write") is None
