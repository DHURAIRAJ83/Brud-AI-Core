"""Phase 20 Step 17 -- built-in deterministic tool registry.

Exactly three tools are defined and public-enabled in this phase
(Step 2's own minimum scope). No reflection-based dynamic import, no
plugin auto-loading from any location, no arbitrary tool name accepted
from a caller -- `get_tool_descriptor()` only ever returns one of
these three fixed, hand-written descriptors or `None`.
"""

from __future__ import annotations

from core_model.tool_gateway.calculator import MAX_EXPRESSION_LENGTH
from core_model.tool_gateway.mcp_contract import ToolDescriptor

TOOL_VERSION = "v1"

TOOL_DESCRIPTORS: tuple[ToolDescriptor, ...] = (
    ToolDescriptor(
        tool_name="calculator",
        tool_version=TOOL_VERSION,
        description=(
            "Deterministic arithmetic: addition, subtraction, multiplication, division, "
            "parentheses, percentages, bounded powers, decimal arithmetic. Never the model."
        ),
        input_schema={
            "type": "object",
            "required": ["expression"],
            "properties": {"expression": {"type": "string", "maxLength": MAX_EXPRESSION_LENGTH}},
        },
        output_schema={
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
                "normalized_expression": {"type": "string"},
                "result": {"type": "string"},
                "result_type": {"type": "string"},
                "precision": {"type": "integer"},
            },
        },
        risk_level="low",
        source="built_in_deterministic",
        permission="public_safe_deterministic",
        public_enabled=True,
        admin_enabled=True,
        timeout_seconds=2.0,
        maximum_input_size=MAX_EXPRESSION_LENGTH,
    ),
    ToolDescriptor(
        tool_name="unit_conversion",
        tool_version=TOOL_VERSION,
        description="Deterministic unit conversion across length/mass/volume/temperature/time/"
        "area/speed/data_size, using explicit unit allowlists only.",
        input_schema={
            "type": "object",
            "required": ["value", "source_unit", "target_unit"],
            "properties": {
                "value": {"type": "number"},
                "source_unit": {"type": "string", "maxLength": 40},
                "target_unit": {"type": "string", "maxLength": 40},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "number"},
                "conversion_formula": {"type": "string"},
                "category": {"type": "string"},
            },
        },
        risk_level="low",
        source="built_in_deterministic",
        permission="public_safe_deterministic",
        public_enabled=True,
        admin_enabled=True,
        timeout_seconds=2.0,
        maximum_input_size=40,
    ),
    ToolDescriptor(
        tool_name="date_time_arithmetic",
        tool_version=TOOL_VERSION,
        description="Deterministic calendar-date arithmetic: add/subtract days or weeks, date "
        "difference. ISO-8601 dates only; never a live current-time value.",
        input_schema={
            "type": "object",
            "required": ["operation"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add_days", "add_weeks", "date_difference"],
                },
                "date": {"type": "string", "maxLength": 40},
                "date_a": {"type": "string", "maxLength": 40},
                "date_b": {"type": "string", "maxLength": 40},
                "days": {"type": "integer"},
                "weeks": {"type": "integer"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "result_date": {"type": ["string", "null"]},
                "result_days": {"type": ["integer", "null"]},
            },
        },
        risk_level="low",
        source="built_in_deterministic",
        permission="public_safe_deterministic",
        public_enabled=True,
        admin_enabled=True,
        timeout_seconds=2.0,
        maximum_input_size=40,
    ),
)

_BY_NAME = {descriptor.tool_name: descriptor for descriptor in TOOL_DESCRIPTORS}


def get_tool_descriptor(tool_name: str) -> ToolDescriptor | None:
    return _BY_NAME.get(tool_name)


def list_tool_descriptors() -> list[ToolDescriptor]:
    return list(TOOL_DESCRIPTORS)


__all__ = ["TOOL_DESCRIPTORS", "TOOL_VERSION", "get_tool_descriptor", "list_tool_descriptors"]
