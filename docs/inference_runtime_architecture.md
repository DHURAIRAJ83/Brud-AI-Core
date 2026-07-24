# Controlled Inference Runtime Architecture (Phase 15)

Phase 14 proved model registry and release controls work. Phase 15
proves that **only eligible, verified releases can enter a bounded
inference runtime** — and that entering the runtime is never the same
as being available to the public chatbot.

## Separation of concerns (never merged)

```
model release            -> model_releases.status / deployment_eligibility
runtime compatibility    -> inference_model_compatibility_assessments
runtime loading          -> inference_runtime_instances.status
model assignment         -> inference_model_assignments.status
canary activation        -> inference_canary_runs.run_status
public-chat activation   -> a separate explicit gate, never auto-passed
rollback                 -> inference_assignment_versions + rollback events
```

A release may exist without being loadable. A loadable model may exist
without being assigned. An assigned model may exist only in admin
testing. A canary model may exist without public activation. A public
activation must pass a separate explicit gate every time.

## Modules

`core_model/inference_runtime/` (pure functions, no I/O, no `Settings`
import — matching the discipline of every prior phase's core package):

* `runtime_config.py` — validates a runtime profile's declared limits.
* `resource_guard.py` — bounded memory/disk estimation and fail-closed
  assessment; every figure is labelled `estimated` or `measured`.
* `model_loader.py` — reuses `core_model.release.artifact_inventory
  .resolve_confined_path` unchanged (no second path-confinement
  implementation); adds vocabulary/special-token compatibility checks
  and the 14-dimension `assess_runtime_compatibility()`.
* `generation_config.py` — bounded `GenerationConfig`, validated per
  scope; `public_chat` can never enable sampling or non-`reject`
  truncation, regardless of what is requested.
* `generation_engine.py` — extends Phase 12's `generate_greedy()` loop
  shape (EOS/context-limit/token-cap/timeout stops) with cooperative
  cancellation, a minimum-token floor, and mid-generation role-token
  leakage detection; reuses Phase 12's `no_role_token_leakage()`,
  `no_system_prompt_leakage()`, `no_excessive_repetition()`,
  `valid_unicode()` unchanged for post-hoc checks.
* `context_builder.py` — deterministic, bounded multi-turn context
  assembly using the same `<bos>/<system>/<user>/<assistant>` token
  shape Phase 12's instruction template established.
* `assignment_policy.py` — non-overridable assignment eligibility and
  the public-chat activation gate.
* `canary.py` — deterministic routing, metrics, and auto-stop rules.
* `runtime_health.py` — health-check aggregation; a checkpoint/tokenizer
  mismatch or role-token-leakage smoke-test failure can never yield
  `ready`.
* `fallback.py` — deterministic fallback resolution; a requested
  `previous_active_assignment` fallback with none available degrades
  safely to `placeholder`, never fails open.
* `comparison.py` — structural (not quality) comparison between a
  placeholder and model response.

## Backend

`InferenceRuntimeService` owns runtime profiles/instances, release
compatibility assessment, model loading (the single in-process
`_LOADED_MODELS` slot, keyed by `(database_path, instance_public_id)` so
two different databases in the same process — e.g. two isolated test
runs — never share loaded-model state), health checks, and the bounded
generation primitive. `ModelAssignmentService` owns assignment
lifecycle, admin diagnostics, admin chat lab, canary orchestration,
rollback, and the runtime manifest — composing `InferenceRuntimeService`
rather than duplicating any of its logic. When one service calls the
other **inside an already-open transaction**, it must call
`load_instance_using_connection(connection, ...)` rather than
`load_instance(...)` — a second, independently-opened SQLite connection
cannot see the first one's uncommitted writes (e.g. an instance row
just created in the same request). This was a real bug caught during
implementation; see `docs/phase_15_report.md`.

## Reused, not duplicated

Release registry (Phase 14), release manifests, model-card metadata,
`TrainingCheckpointManager`, the tokenizer registry
(`TokenizerService.processor_for_version`), the core-model loader
(`BrudForCausalLM`/`BrudModelConfig`), Phase 12's bounded greedy
generation loop shape, Phase 13's evaluation readiness, Phase 14's
release eligibility, audit logging, and admin authentication/CSRF are
all reused unchanged. Phase 15 does not implement a second model
registry, a second tokenizer registry, a second checkpoint verifier, a
new model architecture, a duplicate public chat endpoint, or a
deployment orchestrator.

## Non-goals (unchanged from the spec, never added)

No automatic public-chat activation, RAG, web search, tool calling,
external model providers, multi-model concurrent serving, GPU cluster
or distributed serving, quantization, GGUF export, RLHF, DPO, or
production deployment.
