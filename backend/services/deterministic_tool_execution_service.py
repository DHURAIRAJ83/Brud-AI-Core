"""Phase 20 Step 17 -- `DeterministicToolExecutionService`.

Pipeline: Tool Selection (already done by the caller -- this service
never guesses a tool from free text) -> Input Schema Validation ->
Safety/Permission Check -> Deterministic Execution -> Output Schema
Validation (implicit: each `core_model.tool_gateway.*` function's own
return dataclass *is* its output schema) -> Result Normalization ->
Audit (`deterministic_tool_execution_events`, append-only, always
written -- success or failure).

Calculator/unit-conversion/date-arithmetic inputs are numbers, units,
and dates -- never personal data -- so unlike Web evidence excerpts,
`input_summary`/`result_summary` are stored as literal bounded text,
not PII-redacted; there is nothing to redact.
"""

from __future__ import annotations

import time
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.trusted_web_tool_gateway import TrustedWebToolGatewayRepository
from backend.services.deterministic_tool_registry import get_tool_descriptor
from backend.services.public_chat_rate_limiter import check_rate_limit
from core_model.tool_gateway.calculator import CalculatorError
from core_model.tool_gateway.calculator import evaluate as evaluate_calculator
from core_model.tool_gateway.date_time_arithmetic import DateArithmeticError
from core_model.tool_gateway.date_time_arithmetic import add_days as dt_add_days
from core_model.tool_gateway.date_time_arithmetic import add_weeks as dt_add_weeks
from core_model.tool_gateway.date_time_arithmetic import date_difference as dt_date_difference
from core_model.tool_gateway.mcp_contract import (
    ToolExecutionError,
    ToolInvocationRequest,
    ToolInvocationResult,
    ToolPermissionContext,
)
from core_model.tool_gateway.unit_conversion import UnitConversionError
from core_model.tool_gateway.unit_conversion import convert as convert_unit

MAX_INPUT_SUMMARY_CHARS = 200
MAX_RESULT_SUMMARY_CHARS = 200

_TOOL_ERRORS = (CalculatorError, UnitConversionError, DateArithmeticError)


def _validate_required_fields(payload: dict[str, Any], required: list[str]) -> str | None:
    for field in required:
        if field not in payload or payload[field] is None:
            return f"missing_field:{field}"
    return None


class DeterministicToolExecutionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = TrustedWebToolGatewayRepository(settings.resolved_database_path)

    def execute(
        self, request: ToolInvocationRequest, context: ToolPermissionContext
    ) -> ToolInvocationResult:
        started = time.perf_counter()
        descriptor = get_tool_descriptor(request.tool_name)

        if descriptor is None:
            return self._finish(
                request,
                "unknown",
                "v0",
                "unsupported",
                None,
                f"requested_tool_name={request.tool_name}",
                None,
                started,
            )

        # `context.external_mcp_enabled` is deliberately never consulted here --
        # any `external_mcp`-sourced descriptor is refused unconditionally in
        # this phase (see `mcp_contract.py`'s own docstring). No such
        # descriptor exists in the registry today either way.
        if descriptor.source == "external_mcp":
            raise ToolExecutionError("mcp_disabled")

        if context.is_public_request and not descriptor.public_enabled:
            return self._finish(
                request, descriptor.tool_name, descriptor.tool_version, "disabled",
                None, None, None, started,
            )
        if context.is_admin_request and not descriptor.admin_enabled:
            return self._finish(
                request, descriptor.tool_name, descriptor.tool_version, "disabled",
                None, None, None, started,
            )

        if not check_rate_limit(
            "tool_exec",
            max_requests=self.settings.tool_execution_rate_limit_max_requests,
            window_seconds=self.settings.tool_execution_rate_limit_window_seconds,
        ):
            return self._finish(
                request, descriptor.tool_name, descriptor.tool_version, "rate_limited",
                None, None, None, started,
            )

        missing = _validate_required_fields(
            request.input_payload, list(descriptor.input_schema.get("required", []))
        )
        if missing:
            return self._finish(
                request, descriptor.tool_name, descriptor.tool_version, "input_invalid",
                None, missing, None, started,
            )

        try:
            output, input_summary, result_summary = self._dispatch(
                descriptor.tool_name, request.input_payload
            )
        except _TOOL_ERRORS as exc:
            return self._finish(
                request, descriptor.tool_name, descriptor.tool_version, "input_invalid",
                None, exc.reason, None, started,
            )
        except Exception as exc:  # noqa: BLE001 -- deterministic tools must never crash the router
            return self._finish(
                request, descriptor.tool_name, descriptor.tool_version, "execution_failed",
                None, type(exc).__name__, None, started,
            )

        return self._finish(
            request, descriptor.tool_name, descriptor.tool_version, "success",
            output, input_summary, result_summary, started,
        )

    def _dispatch(
        self, tool_name: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], str, str]:
        if tool_name == "calculator":
            expression = payload.get("expression")
            if not isinstance(expression, str):
                raise CalculatorError("input_invalid")
            result = evaluate_calculator(expression)
            output = {
                "expression": result.expression,
                "normalized_expression": result.normalized_expression,
                "result": result.result,
                "result_type": result.result_type,
                "precision": result.precision,
            }
            return output, f"expression_len={len(expression)}", result.result

        if tool_name == "unit_conversion":
            value = payload.get("value")
            source_unit = payload.get("source_unit")
            target_unit = payload.get("target_unit")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise UnitConversionError("input_invalid")
            if not isinstance(source_unit, str) or not isinstance(target_unit, str):
                raise UnitConversionError("input_invalid")
            result = convert_unit(float(value), source_unit, target_unit)
            output = {
                "value": result.value,
                "source_unit": result.source_unit,
                "target_unit": result.target_unit,
                "result": result.result,
                "conversion_formula": result.conversion_formula,
                "category": result.category,
            }
            return (
                output,
                f"{value} {source_unit} -> {target_unit}",
                f"{result.result} {target_unit}",
            )

        if tool_name == "date_time_arithmetic":
            operation = payload.get("operation")
            if operation == "add_days":
                date_value = payload.get("date")
                days = payload.get("days")
                if not isinstance(date_value, str) or not isinstance(days, int) or isinstance(
                    days, bool
                ):
                    raise DateArithmeticError("input_invalid")
                result = dt_add_days(date_value, days)
            elif operation == "add_weeks":
                date_value = payload.get("date")
                weeks = payload.get("weeks")
                if not isinstance(date_value, str) or not isinstance(weeks, int) or isinstance(
                    weeks, bool
                ):
                    raise DateArithmeticError("input_invalid")
                result = dt_add_weeks(date_value, weeks)
            elif operation == "date_difference":
                date_a = payload.get("date_a")
                date_b = payload.get("date_b")
                if not isinstance(date_a, str) or not isinstance(date_b, str):
                    raise DateArithmeticError("input_invalid")
                result = dt_date_difference(date_a, date_b)
            else:
                raise DateArithmeticError("unsupported_operation")
            output = {
                "operation": result.operation,
                "result_date": result.result_date,
                "result_days": result.result_days,
            }
            summary = (
                result.result_date if result.result_date is not None else str(result.result_days)
            )
            return output, f"op={operation}", str(summary)

        raise ToolExecutionError("tool_unsupported")

    def _finish(
        self,
        request: ToolInvocationRequest,
        tool_name: str,
        tool_version: str,
        status: str,
        output: dict[str, Any] | None,
        input_summary: str | None,
        result_summary: str | None,
        started: float,
    ) -> ToolInvocationResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        error_code = None
        if status != "success":
            error_code = input_summary if status == "input_invalid" else status
        # None of these values are ever raw sensitive user text --
        # calculator/unit/date inputs are numbers, units, and dates,
        # and the non-success summaries below are short diagnostic
        # strings this service constructs itself -- so both are
        # persisted (bounded) regardless of outcome, unlike Web
        # evidence excerpts which do require redaction.
        recorded = self.repository.record_tool_execution(
            {
                "request_id": request.request_id,
                "tool_name": tool_name,
                "tool_version": tool_version,
                "status": status,
                "input_summary": (input_summary or "")[:MAX_INPUT_SUMMARY_CHARS] or None,
                "result_summary": (result_summary or "")[:MAX_RESULT_SUMMARY_CHARS] or None,
                "error_code": error_code,
                "latency_ms": latency_ms,
            }
        )
        return ToolInvocationResult(
            tool_name=tool_name,
            tool_version=tool_version,
            status=status,
            output_payload=output,
            error_code=error_code,
            latency_ms=latency_ms,
            execution_public_id=recorded.get("public_id"),
        )


__all__ = ["DeterministicToolExecutionService"]
