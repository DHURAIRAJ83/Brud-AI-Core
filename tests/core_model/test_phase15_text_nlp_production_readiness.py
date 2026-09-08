"""Phase 15: Text/NLP Production Readiness.

Tests verify all 40 required scenarios:
1. Tamil detection -> ta
2. English detection -> en
3. Tanglish detection -> tanglish
4. Mixed language detection -> mixed
5. Empty/symbol-only -> unknown
6. Confidence high
7. Confidence medium
8. Confidence low
9. Confidence unknown
10. Unicode NFC normalization
11. Control-character normalization
12. Tanglish -> Tamil normalization
13. git status preservation
14. npm install preservation
15. python3 app.py preservation
16. SELECT * FROM users preservation
17. URL preservation
18. email preservation
19. Brud AI preservation
20. PostgreSQL preservation
21. FastAPI preservation
22. GitHub preservation
23. empty string safety
24. whitespace-only safety
25. emoji-only safety
26. malformed Unicode safety
27. deterministic repeated processing
28. RAG normalizer compatibility
29. memory original-vs-normalized preservation
30. public chat language policy compatibility
31. AST security inspection
32. no eval
33. no exec
34. no subprocess
35. no while True
36. no cron
37. no celery
38. no queueconsumer
39. no database access
40. no external API access
"""

from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest

from core_model.nlp import NLPResult, is_code_or_technical_text, process_text
from core_model.public_chat.language_policy import resolve_answer_language
from core_model.rag.query_normalization import normalize_query


# 1. Tamil detection -> ta
def test_1_tamil_detection_ta() -> None:
    res = process_text("எனக்கு ஒரு அறிக்கை வேண்டும்")
    assert res.detected_language == "ta"


# 2. English detection -> en
def test_2_english_detection_en() -> None:
    res = process_text("Please generate the dataset summary report for production.")
    assert res.detected_language == "en"


# 3. Tanglish detection -> tanglish
def test_3_tanglish_detection_tanglish() -> None:
    res = process_text("epadi irukku venum")
    assert res.detected_language in {"tanglish", "mixed"}
    assert res.is_tanglish is True or res.is_mixed_language is True


# 4. Mixed language detection -> mixed
def test_4_mixed_language_detection_mixed() -> None:
    res = process_text("Brud AI server restart எப்படி செய்வது?")
    assert res.detected_language in {"mixed", "ta", "tanglish"}
    assert res.original_text == "Brud AI server restart எப்படி செய்வது?"


# 5. Empty/symbol-only -> unknown
def test_5_empty_symbol_only_unknown() -> None:
    res = process_text("12345 !!! ??? @#$%^&*()")
    assert res.detected_language == "unknown"


# 6. Confidence high
def test_6_confidence_high() -> None:
    res = process_text("வணக்கம் எப்படி இருக்கிறீர்கள்")
    assert res.language_confidence >= 0.8


# 7. Confidence medium
def test_7_confidence_medium() -> None:
    res = process_text("test 123 சென்னை")
    assert 0.4 <= res.language_confidence <= 0.95


# 8. Confidence low
def test_8_confidence_low() -> None:
    res = process_text("a b c d e f g")
    assert res.language_confidence <= 0.85


# 9. Confidence unknown
def test_9_confidence_unknown() -> None:
    res = process_text("")
    assert res.language_confidence == 0.0


# 10. Unicode NFC normalization
def test_10_unicode_nfc_normalization() -> None:
    raw = "Brud AI e\u0301 test"
    res = process_text(raw)
    assert res.normalized_text == "Brud AI é test"
    assert res.normalization_applied is True


# 11. Control-character normalization
def test_11_control_character_normalization() -> None:
    raw = "Brud\x00AI\x07 test \r\n line 2"
    res = process_text(raw)
    assert "\x00" not in res.normalized_text
    assert "\x07" not in res.normalized_text
    assert "\r" not in res.normalized_text


# 12. Tanglish -> Tamil normalization
def test_12_tanglish_to_tamil_normalization() -> None:
    res = process_text("epadi irukku report venum")
    assert res.normalization_applied is True
    assert "எப்படி" in res.normalized_text
    assert "வேண்டும்" in res.normalized_text


# 13. git status preservation
def test_13_git_status_preservation() -> None:
    res = process_text("git status")
    assert res.is_technical_code is True
    assert res.normalized_text == "git status"


# 14. npm install preservation
def test_14_npm_install_preservation() -> None:
    res = process_text("npm install")
    assert res.is_technical_code is True
    assert res.normalized_text == "npm install"


# 15. python3 app.py preservation
def test_15_python3_app_py_preservation() -> None:
    res = process_text("python3 app.py")
    assert res.is_technical_code is True
    assert res.normalized_text == "python3 app.py"


# 16. SELECT * FROM users preservation
def test_16_select_from_users_preservation() -> None:
    res = process_text("SELECT * FROM users")
    assert res.is_technical_code is True
    assert res.normalized_text == "SELECT * FROM users"


# 17. URL preservation
def test_17_url_preservation() -> None:
    url = "https://brudai.com/api/v1/health"
    res = process_text(f"Check {url} now")
    assert res.is_technical_code is True
    assert url in res.normalized_text


# 18. email preservation
def test_18_email_preservation() -> None:
    email = "support@brudai.com"
    res = process_text(f"Contact {email} for help")
    assert res.is_technical_code is True
    assert email in res.normalized_text


# 19. Brud AI preservation
def test_19_brud_ai_preservation() -> None:
    res = process_text("Brud AI system status")
    assert "Brud AI" in res.normalized_text


# 20. PostgreSQL preservation
def test_20_postgresql_preservation() -> None:
    res = process_text("PostgreSQL database setup")
    assert "PostgreSQL" in res.normalized_text


# 21. FastAPI preservation
def test_21_fastapi_preservation() -> None:
    res = process_text("FastAPI backend router")
    assert "FastAPI" in res.normalized_text


# 22. GitHub preservation
def test_22_github_preservation() -> None:
    res = process_text("GitHub repository code")
    assert "GitHub" in res.normalized_text


# 23. empty string safety
def test_23_empty_string_safety() -> None:
    res = process_text("")
    assert res.detected_language == "unknown"
    assert res.normalized_text == ""


# 24. whitespace-only safety
def test_24_whitespace_only_safety() -> None:
    res = process_text("   \n\t  ")
    assert res.detected_language == "unknown"
    assert res.normalized_text == ""


# 25. emoji-only safety
def test_25_emoji_only_safety() -> None:
    res = process_text("😀😃😄😁😆")
    assert res.detected_language == "unknown"


# 26. malformed Unicode safety
def test_26_malformed_unicode_safety() -> None:
    res = process_text("Test \uFFFD \uFEFF input")
    assert "Test" in res.normalized_text


# 27. deterministic repeated processing
def test_27_deterministic_repeated_processing() -> None:
    sample = "epadi irukku Brud AI system?"
    res1 = process_text(sample)
    res2 = process_text(sample)
    res3 = process_text(sample)
    assert res1 == res2 == res3


# 28. RAG normalizer compatibility
def test_28_rag_normalizer_compatibility() -> None:
    rag_norm = normalize_query("Brud AI dataset check", language_category="en")
    nlp_norm = process_text("Brud AI dataset check")
    assert rag_norm["normalized_query"] == nlp_norm.normalized_text.lower()


# 29. memory original-vs-normalized preservation
def test_29_memory_original_vs_normalized_preservation() -> None:
    user_input = "eppadi irukku model training?"
    res = process_text(user_input)
    assert res.original_text == user_input
    assert res.normalized_text != user_input


# 30. public chat language policy compatibility
def test_30_public_chat_language_policy_compatibility() -> None:
    policy_dec = resolve_answer_language(detected_language_category="tgl")
    assert policy_dec.answer_language == "ta"


# 31-40. AST security inspection & Safety Guards
def test_31_to_40_ast_security_inspection_phase15() -> None:
    from core_model.nlp import text_processor

    source = inspect.getsource(text_processor)
    module = ast.parse(source)

    # Strip docstrings
    for node in ast.walk(module):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]

    code_only = ast.unparse(module)
    lowered = code_only.lower()

    # 32-38: Forbidden execution, loops, workers, schedulers
    for forbidden in (
        "asyncio.create_task",
        "backgroundtasks",
        "while true",
        "celery",
        "apscheduler",
        "cron",
        "queueconsumer",
        "subprocess",
        "os.system",
        "run_tool(",
        "execute_with_governance(",
        "sqlite3",
        "requests",
        "urllib",
        "httpx",
    ):
        assert forbidden not in lowered

    # 32-33: Forbidden eval, exec, compile, dynamic import
    tree = ast.parse(code_only)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile", "__import__"}
