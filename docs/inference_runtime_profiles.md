# Inference Runtime Profiles (Phase 15)

A runtime profile describes bounded local inference — it never
describes a specific model or assignment.

## Fields

`name`, `runtime_type` (`local_cpu`|`local_gpu`, default `local_cpu`),
`device`, `dtype` (`float32` only), `maximum_loaded_models`,
`maximum_concurrent_requests`, `maximum_context_length`,
`maximum_new_tokens`, `request_timeout_seconds`, `idle_unload_seconds`,
`minimum_available_memory_bytes`, `minimum_available_disk_bytes`,
`resource_policy_json`, `generation_defaults_json`.

## Validation (`core_model.inference_runtime.runtime_config
.validate_runtime_profile()`)

* `runtime_type` must be `local_cpu` or `local_gpu`; `dtype` must be
  `float32` — Phase 15 supports only float32 CPU inference for the
  target low-memory hardware.
* `maximum_loaded_models` / `maximum_concurrent_requests` ≥ 1.
* `maximum_context_length` ≥ 8; `maximum_new_tokens` ≥ 1 and must not
  exceed `maximum_context_length`.
* `request_timeout_seconds` / `idle_unload_seconds` ≥ 1.
* Memory/disk minimums must not be negative.

An invalid profile is rejected at creation (`ValidationError`, surfaced
as `422`) — never silently clamped.

## Phase 15 default hardware target

Approximately 6 GB RAM, approximately 6 GB swap, CPU only: one loaded
model, one active generation, batch size 1, float32. A profile's
`maximum_loaded_models=1`/`maximum_concurrent_requests=1` defaults match
this target; raising them is possible but is the operator's explicit
choice, never Phase 15's default.

## Mutable, not append-only

Unlike most Phase 15 evidence tables, `inference_runtime_profiles` is a
mutable lifecycle row (like Phase 14's release families/candidates) —
an operator can disable a profile (`enabled=false`) or tighten its
limits without losing its identity. `PATCH` re-validates
`maximum_new_tokens ≤ maximum_context_length` against the *merged*
result, not just the changed fields.
