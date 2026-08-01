"""Phase 20 Step 18 -- deterministic calculator.

An `ast`-allowlist evaluator over `decimal.Decimal` -- never `eval`,
never `compile` with anything but `mode="eval"` on a pre-validated
node set. Any AST node that is not explicitly matched (`Call`,
`Attribute`, `Name`, `Import`, comprehensions, assignments, ...) falls
through to a raised `CalculatorError`, since none of the `isinstance`
branches below match it -- an allowlist, not a denylist, so a novel
Python syntax feature is rejected by default rather than silently
permitted.

`%` is deliberately percentage-only, not also a modulo operator: Step
18 requires percentage support but never mentions modulo, and the two
notations are genuinely ambiguous over the same symbol (`10 % 3` reads
identically to a malformed "10 percent" followed by a stray `3`).
`_normalize_percentages()` runs before parsing and cannot tell the two
apart, so supporting both would silently misparse one of them; `Mod`
is not in `_ALLOWED_BINOPS`, so any literal `%` is always treated as a
percentage suffix.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation

MAX_EXPRESSION_LENGTH = 200
MAX_AST_DEPTH = 20
MAX_PAREN_DEPTH = 20
MAX_EXPONENT = 12
MAX_RESULT_EXPONENT = 100  # rejects results whose magnitude exceeds 10**100

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


class CalculatorError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CalculatorResult:
    expression: str
    normalized_expression: str
    result: str
    result_type: str
    precision: int


def _normalize_percentages(expression: str) -> str:
    return _PERCENT_RE.sub(r"(\1/100)", expression)


def _check_paren_depth(expression: str) -> None:
    """Rejects pathologically nested parentheses *before* handing the
    string to `ast.parse()` -- CPython's own parser has a recursion
    limit that a large-enough paren count can hit regardless of what
    `_ast_depth()` later measures on the resulting tree (a run of
    parens around a single atom collapses to one AST node, so the
    post-parse depth check alone cannot catch this)."""

    depth = 0
    for char in expression:
        if char == "(":
            depth += 1
            if depth > MAX_PAREN_DEPTH:
                raise CalculatorError("expression_too_deep")
        elif char == ")":
            depth -= 1


def _ast_depth(node: ast.AST) -> int:
    if isinstance(node, ast.BinOp):
        return 1 + max(_ast_depth(node.left), _ast_depth(node.right))
    if isinstance(node, ast.UnaryOp):
        return 1 + _ast_depth(node.operand)
    return 1


def _eval_node(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError("unsupported_constant")
        try:
            return Decimal(str(node.value))
        except InvalidOperation as exc:
            raise CalculatorError("invalid_number") from exc

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BINOPS):
            raise CalculatorError("unsupported_operator")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise CalculatorError("division_by_zero")
            try:
                return left / right
            except (DivisionByZero, InvalidOperation) as exc:
                raise CalculatorError("division_error") from exc
        if isinstance(node.op, ast.Pow):
            if right != right.to_integral_value():
                raise CalculatorError("non_integer_exponent_unsupported")
            exponent = int(right)
            if abs(exponent) > MAX_EXPONENT:
                raise CalculatorError("exponent_too_large")
            try:
                return left**exponent
            except (InvalidOperation, OverflowError) as exc:
                raise CalculatorError("result_out_of_range") from exc
        raise CalculatorError("unsupported_operator")

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARYOPS):
            raise CalculatorError("unsupported_operator")
        operand = _eval_node(node.operand)
        return operand if isinstance(node.op, ast.UAdd) else -operand

    # ast.Call, ast.Attribute, ast.Name, ast.Subscript, comprehensions,
    # ast.Import, ast.Lambda, etc. all fall through here -- none of
    # them match an allowed branch above.
    raise CalculatorError("unsupported_expression")


def evaluate(expression: str) -> CalculatorResult:
    if not expression or not expression.strip():
        raise CalculatorError("empty_expression")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculatorError("expression_too_long")

    _check_paren_depth(expression)
    normalized = _normalize_percentages(expression.strip())

    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError("invalid_syntax") from exc

    if _ast_depth(tree.body) > MAX_AST_DEPTH:
        raise CalculatorError("expression_too_deep")

    result = _eval_node(tree.body)
    if result.adjusted() > MAX_RESULT_EXPONENT:
        raise CalculatorError("result_out_of_range")

    normalized_result = result.normalize()
    is_integer = normalized_result == normalized_result.to_integral_value()
    # `format(..., "f")` always renders fixed-point, never scientific
    # notation, regardless of the Decimal's internal exponent after
    # `.normalize()` -- a calculator result like 987654*12345 must
    # read as "12192588630", never "1.219258863E+10".
    display = format(normalized_result, "f")
    return CalculatorResult(
        expression=expression,
        normalized_expression=normalized,
        result=display,
        result_type="integer" if is_integer else "decimal",
        precision=abs(normalized_result.as_tuple().exponent) if not is_integer else 0,
    )


__all__ = ["CalculatorError", "CalculatorResult", "evaluate"]
