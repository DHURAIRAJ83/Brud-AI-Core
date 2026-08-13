"""MB-28: unit tests for the pure core_model/mini_brain/llm_runtime/
modules -- no database, no app, no HTTP client, no adapter.
"""

from __future__ import annotations

import pytest

from core_model.mini_brain.llm_runtime import (
    admin_explainer_templates,
    answer_style_policy,
    citation_formatter,
    context_window_manager,
    conversation_title_builder,
    memory_rollup_builder,
    message_sanitizer,
    next_action_planner,
    prompt_builder,
    provider_fallback_policy,
    report_summarizer,
    runtime_diagnostics_builder,
    token_budget,
    tool_intent_classifier,
)

# -- token_budget --------------------------------------------------------------------


def test_estimate_tokens_empty_is_zero() -> None:
    assert token_budget.estimate_tokens("") == 0


def test_estimate_tokens_nonempty_is_at_least_one() -> None:
    assert token_budget.estimate_tokens("hi") >= 1


def test_estimate_tokens_scales_with_length() -> None:
    assert token_budget.estimate_tokens("x" * 400) > token_budget.estimate_tokens("x" * 4)


def test_compute_budget_shape() -> None:
    budget = token_budget.compute_budget(context_length=2048, max_tokens=512)
    assert budget["context_length"] == 2048
    assert budget["input_budget_tokens"] > 0
    assert budget["output_budget_tokens"] > 0
    assert budget["input_budget_tokens"] + budget["output_budget_tokens"] + budget["system_reserve_tokens"] <= 2048


def test_compute_budget_clamps_nonpositive_inputs() -> None:
    budget = token_budget.compute_budget(context_length=0, max_tokens=0)
    assert budget["context_length"] >= 1
    assert budget["output_budget_tokens"] >= 1


def test_fits_within_budget() -> None:
    assert token_budget.fits_within_budget(text="hi", budget_tokens=100) is True
    assert token_budget.fits_within_budget(text="x" * 1000, budget_tokens=1) is False


# -- context_window_manager -----------------------------------------------------------


def test_select_context_messages_empty() -> None:
    result = context_window_manager.select_context_messages(messages=[], input_budget_tokens=100)
    assert result == {"messages": [], "truncated": False, "dropped_count": 0}


def test_select_context_messages_keeps_all_when_budget_is_large() -> None:
    messages = [{"role": "admin", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    result = context_window_manager.select_context_messages(messages=messages, input_budget_tokens=10_000)
    assert result["truncated"] is False
    assert len(result["messages"]) == 2


def test_select_context_messages_truncates_and_keeps_latest() -> None:
    messages = [{"role": "admin", "content": "x" * 400} for _ in range(20)]
    messages.append({"role": "admin", "content": "current question"})
    result = context_window_manager.select_context_messages(messages=messages, input_budget_tokens=55)
    assert result["truncated"] is True
    assert result["dropped_count"] > 0
    assert result["messages"][-1]["content"] == "current question"


def test_select_context_messages_always_keeps_system_messages() -> None:
    messages = [{"role": "system", "content": "sys"}] + [{"role": "admin", "content": "x" * 400} for _ in range(10)]
    result = context_window_manager.select_context_messages(messages=messages, input_budget_tokens=1)
    assert any(m["role"] == "system" for m in result["messages"])


# -- prompt_builder ---------------------------------------------------------------------


def test_build_prompt_shape() -> None:
    style = {"system_prompt": "be concise"}
    result = prompt_builder.build_prompt(style_directives=style, context_messages=[], question="hi")
    assert result["system_prompt"] == "be concise"
    assert result["messages"][-1] == {"role": "user", "content": "hi"}


def test_build_prompt_appends_tool_results() -> None:
    style = {"system_prompt": "x"}
    result = prompt_builder.build_prompt(
        style_directives=style, context_messages=[], question="q",
        tool_results=[{"tool_name": "weather", "summary": "sunny"}],
    )
    tool_messages = [m for m in result["messages"] if m["role"] == "tool"]
    assert len(tool_messages) == 1
    assert "sunny" in tool_messages[0]["content"]


def test_build_prompt_excludes_system_role_from_context_messages() -> None:
    style = {"system_prompt": "x"}
    context = [{"role": "system", "content": "sys"}, {"role": "admin", "content": "prior"}]
    result = prompt_builder.build_prompt(style_directives=style, context_messages=context, question="q")
    assert all(m["role"] != "system" for m in result["messages"][:-1])


# -- build_grounded_messages (MB-37) -------------------------------------------------------


def test_build_grounded_messages_order_and_shape() -> None:
    chunks = [{"normalized_text": "Test phrase: KAVERI-MANGO-7421"}]
    result = prompt_builder.build_grounded_messages(
        system_prompt="be concise", user_message="What is the test phrase?", retrieved_chunks=chunks,
    )
    assert result["system_prompt"] == "be concise"
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "user"
    assert "KAVERI-MANGO-7421" in result["messages"][0]["content"]
    assert result["messages"][1] == {"role": "user", "content": "What is the test phrase?"}


def test_build_grounded_messages_evidence_block_format() -> None:
    chunks = [{"normalized_text": "chunk one text"}, {"normalized_text": "chunk two text"}]
    result = prompt_builder.build_grounded_messages(
        system_prompt="x", user_message="q", retrieved_chunks=chunks,
    )
    evidence = result["messages"][0]["content"]
    assert evidence.startswith(
        "Use the following retrieved knowledge. If the answer is not present, "
        "say that the retrieved knowledge does not contain the answer."
    )
    assert "[Source 1]" in evidence
    assert "chunk one text" in evidence
    assert "[Source 2]" in evidence
    assert "chunk two text" in evidence
    assert evidence.index("[Source 1]") < evidence.index("[Source 2]")


def test_build_grounded_messages_never_invents_citations_with_no_chunks() -> None:
    result = prompt_builder.build_grounded_messages(system_prompt="x", user_message="q", retrieved_chunks=[])
    evidence = result["messages"][0]["content"]
    assert "[Source" not in evidence


# -- answer_style_policy ------------------------------------------------------------------


@pytest.mark.parametrize("capability", [
    "chat", "explain_page", "summarize_report", "summarize_regression",
    "explain_error", "next_actions", "step_guide", "checklist", "clarify",
])
def test_style_for_all_capabilities(capability: str) -> None:
    style = answer_style_policy.style_for(capability=capability)
    assert style["capability"] == capability
    assert len(style["system_prompt"]) > 0


def test_style_for_unknown_capability_falls_back_to_chat() -> None:
    style = answer_style_policy.style_for(capability="totally_unknown")
    assert "Answer the administrator's question directly" in style["system_prompt"]


def test_style_for_bilingual_flag() -> None:
    bilingual = answer_style_policy.style_for(capability="chat", bilingual=True)
    monolingual = answer_style_policy.style_for(capability="chat", bilingual=False)
    assert "Tamil" in bilingual["system_prompt"]
    assert "Tamil" not in monolingual["system_prompt"]


# -- admin_explainer_templates ---------------------------------------------------------------


def test_explain_page_found_by_page_id() -> None:
    result = admin_explainer_templates.explain_page(page_id="overview")
    assert result["found"] is True
    assert result["page_id"] == "overview"
    assert len(result["explanation"]) > 0


def test_explain_page_not_found() -> None:
    result = admin_explainer_templates.explain_page(page_id="totally_unknown_page_xyz")
    assert result["found"] is False
    assert result["explanation"] is None


def test_explain_page_bilingual_dict_rendered_as_text() -> None:
    result = admin_explainer_templates.explain_page(page_id="overview")
    assert result["found"] is True
    assert "{" not in result["explanation"]
    assert "'en'" not in result["explanation"]


def test_explain_page_by_nav_key() -> None:
    result = admin_explainer_templates.explain_page(nav_key="Overview")
    assert result["found"] is True


# -- next_action_planner ---------------------------------------------------------------------


def test_plan_next_actions_empty_snapshot_reports_healthy() -> None:
    actions = next_action_planner.plan_next_actions(status_snapshot={})
    assert len(actions) == 1
    assert actions[0]["severity"] == "low"


def test_plan_next_actions_failing_tests_is_critical() -> None:
    actions = next_action_planner.plan_next_actions(status_snapshot={"failing_tests": 3})
    assert actions[0]["severity"] == "critical"


def test_plan_next_actions_sorted_by_severity() -> None:
    actions = next_action_planner.plan_next_actions(
        status_snapshot={"failing_tests": 1, "pending_proposals": 1, "unconfigured_providers": ["openai"]}
    )
    severities = [a["severity"] for a in actions]
    assert severities == sorted(severities, key=lambda s: {"critical": 0, "high": 1, "medium": 2, "low": 3}[s])


def test_plan_next_actions_always_runs_without_llm() -> None:
    # This is the structural guarantee the plan requires: no LLM
    # involvement needed to produce a non-empty, well-formed list.
    actions = next_action_planner.plan_next_actions(status_snapshot={"failing_tests": 5})
    assert isinstance(actions, list)
    assert all({"title", "severity", "reason"} <= set(a) for a in actions)


def test_parse_llm_output_rephrases_titles() -> None:
    fallback = [{"title": "Fix tests", "severity": "critical", "reason": "x"}]
    rephrased = next_action_planner.parse_llm_output(llm_text="- Resolve failing tests urgently", fallback_actions=fallback)
    assert rephrased[0]["title"] == "Resolve failing tests urgently"
    assert rephrased[0]["severity"] == "critical"


def test_parse_llm_output_empty_text_returns_fallback() -> None:
    fallback = [{"title": "Fix tests", "severity": "critical", "reason": "x"}]
    assert next_action_planner.parse_llm_output(llm_text="", fallback_actions=fallback) == fallback


# -- report_summarizer -----------------------------------------------------------------------


def test_extract_report_facts_pulls_numeric_fields() -> None:
    facts = report_summarizer.extract_report_facts(report={"title": "MB-27", "status": "complete", "tests_passed": 133, "note": "text"})
    assert facts["title"] == "MB-27"
    assert facts["key_numbers"] == {"tests_passed": 133}


def test_extract_report_facts_excludes_booleans() -> None:
    facts = report_summarizer.extract_report_facts(report={"is_green": True, "count": 5})
    assert "is_green" not in facts["key_numbers"]
    assert facts["key_numbers"] == {"count": 5}


def test_extract_regression_facts_computes_totals() -> None:
    facts = report_summarizer.extract_regression_facts(regression_result={"passed": 100, "failed": 2, "errors": 1})
    assert facts["total"] == 103
    assert facts["is_green"] is False


def test_extract_regression_facts_green_when_no_failures() -> None:
    facts = report_summarizer.extract_regression_facts(regression_result={"passed": 50, "failed": 0, "errors": 0})
    assert facts["is_green"] is True


def test_build_summary_prompt_facts_never_invents_numbers() -> None:
    facts = report_summarizer.extract_regression_facts(regression_result={"passed": 42, "failed": 0, "errors": 0})
    text = report_summarizer.build_summary_prompt_facts(facts=facts)
    assert "42" in text


# -- provider_fallback_policy ------------------------------------------------------------------


def test_decide_local_when_local_available_and_loaded() -> None:
    decision = provider_fallback_policy.decide(local_available=True, local_model_loaded=True, external_enabled=False, external_configured=False)
    assert decision["backend"] == "local"


def test_decide_external_when_local_unavailable_but_external_ready() -> None:
    decision = provider_fallback_policy.decide(local_available=False, local_model_loaded=False, external_enabled=True, external_configured=True)
    assert decision["backend"] == "external"


def test_decide_unavailable_when_external_enabled_but_not_configured() -> None:
    decision = provider_fallback_policy.decide(local_available=False, local_model_loaded=False, external_enabled=True, external_configured=False)
    assert decision["backend"] == "unavailable"


def test_decide_unavailable_when_nothing_available() -> None:
    decision = provider_fallback_policy.decide(local_available=False, local_model_loaded=False, external_enabled=False, external_configured=False)
    assert decision["backend"] == "unavailable"


def test_decide_prefers_local_even_when_external_also_ready() -> None:
    decision = provider_fallback_policy.decide(local_available=True, local_model_loaded=True, external_enabled=True, external_configured=True)
    assert decision["backend"] == "local"


# -- tool_intent_classifier --------------------------------------------------------------------


def test_classify_plain_question_is_plain_reply() -> None:
    result = tool_intent_classifier.classify(message="What is the capital of France?")
    assert result["intent"] == "plain_reply"
    assert result["candidate_scope_key"] is None


def test_classify_empty_message() -> None:
    result = tool_intent_classifier.classify(message="   ")
    assert result["intent"] == "plain_reply"
    assert result["confidence"] == 0.0


def test_classify_current_chat_reference_is_tool_call() -> None:
    result = tool_intent_classifier.classify(message="Can you check this conversation for me?")
    assert result["intent"] == "tool_call"
    assert result["candidate_scope_key"] == "chat.read.current"


def test_classify_candidate_scope_is_always_a_known_scope() -> None:
    from core_model.mini_brain.plugin_governance.permission_scope_registry import known_scopes
    result = tool_intent_classifier.classify(message="Check my calendar please")
    if result["candidate_scope_key"] is not None:
        assert result["candidate_scope_key"] in known_scopes()


# -- conversation_title_builder -----------------------------------------------------------------


def test_build_title_from_first_message() -> None:
    assert conversation_title_builder.build_title(first_message="What is Mini Brain?") == "What is Mini Brain?"


def test_build_title_empty_message() -> None:
    assert conversation_title_builder.build_title(first_message="") == "New conversation"


def test_build_title_truncates_long_message() -> None:
    title = conversation_title_builder.build_title(first_message="x" * 200)
    assert len(title) <= 60
    assert title.endswith("…")


def test_build_title_collapses_whitespace() -> None:
    assert conversation_title_builder.build_title(first_message="hello   \n\n  world") == "hello world"


# -- runtime_diagnostics_builder -------------------------------------------------------------------


def test_mask_model_path_filename_only() -> None:
    assert runtime_diagnostics_builder.mask_model_path("/home/user/models/qwen.gguf") == "qwen.gguf"


def test_mask_model_path_none() -> None:
    assert runtime_diagnostics_builder.mask_model_path(None) is None


def test_build_diagnostics_shape() -> None:
    diag = runtime_diagnostics_builder.build_diagnostics(
        local_available=True, local_model_loaded=True, configured_model_path="/a/b/model.gguf",
        external_fallback_enabled=False, external_provider_key=None, active_session_count=2,
        total_messages=10, llama_cpp_installed=True,
    )
    assert diag["configured_model_path"] == "model.gguf"
    assert "/a/b" not in str(diag)


# -- message_sanitizer -----------------------------------------------------------------------------


def test_sanitize_message_redacts_secrets() -> None:
    result = message_sanitizer.sanitize_message(raw_text="my api_key=sk-12345 is here")
    assert "sk-12345" not in result["sanitized_text"]


def test_sanitize_message_truncates_overlong_text() -> None:
    result = message_sanitizer.sanitize_message(raw_text="x" * 9000)
    assert len(result["sanitized_text"]) <= message_sanitizer.MAX_MESSAGE_LENGTH
    assert result["truncated"] is True


def test_sanitize_message_passthrough_for_clean_text() -> None:
    result = message_sanitizer.sanitize_message(raw_text="hello world")
    assert result["sanitized_text"] == "hello world"
    assert result["truncated"] is False


# -- citation_formatter -----------------------------------------------------------------------------


def test_format_citation() -> None:
    assert citation_formatter.format_citation(source_name="weather", fact="It is sunny") == "It is sunny [source: weather]"


def test_append_citations_no_tool_results() -> None:
    assert citation_formatter.append_citations(text="hello", tool_results=[]) == "hello"


def test_append_citations_with_results() -> None:
    text = citation_formatter.append_citations(text="hello", tool_results=[{"tool_name": "weather", "summary": "sunny"}])
    assert "Sources:" in text
    assert "sunny" in text


# -- memory_rollup_builder --------------------------------------------------------------------------


def test_build_memory_row_valid_event_type() -> None:
    row = memory_rollup_builder.build_memory_row(
        session_public_id="s1", admin_public_id="a1", event_type="session_started", backend_type="local", total_messages=0,
    )
    assert row["event_type"] == "session_started"


def test_build_memory_row_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError):
        memory_rollup_builder.build_memory_row(
            session_public_id="s1", admin_public_id="a1", event_type="bogus", backend_type=None, total_messages=0,
        )
