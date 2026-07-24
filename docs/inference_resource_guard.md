# Resource Guard (Phase 15)

`core_model/inference_runtime/resource_guard.py` is a fail-closed,
bounded estimator — it never claims a measured figure for a value it
only estimated, and any single failed check fails the whole assessment.

## Estimation, not measurement, for memory

```
estimate_static_model_bytes(parameter_count, dtype_bytes=4)
  = parameter_count * dtype_bytes

estimate_peak_inference_bytes(...)
  = (static_model_bytes
     + activation_bytes(context_length + generation_length, hidden_size,
                         num_hidden_layers, dtype_bytes)
     + attention_buffer_bytes(sequence_span², num_hidden_layers, dtype_bytes)
    ) * safety_overhead_multiplier   # default 1.5
```

Both are bounded, deterministic functions of the model's own registered
configuration — never a live measurement of the actual process.

## Measurement, where available

Available memory is read from `/proc/meminfo`'s `MemAvailable` line
(Linux) and labelled `measured`; if unavailable, the guard falls back to
`0` labelled `estimated` — it never fabricates a plausible-looking
number. Available disk is measured via `shutil.disk_usage(...)` on the
pretraining directory (the same pattern Phase 13's `_guard_resources()`
already established).

## Checks (`assess_resource_guard()`)

* Requested context length ≤ profile maximum; requested generation
  limit ≤ profile maximum.
* Available disk ≥ checkpoint + tokenizer size + configured minimum.
* Available memory ≥ estimated peak inference bytes + configured
  minimum.
* Currently loaded models (on **other** instances in the **same**
  database) < the profile's `maximum_loaded_models`; currently active
  requests < `maximum_concurrent_requests`.

The "other instances, same database" scoping is deliberate: a runtime
instance being **reloaded** (a new release replacing its own existing
model, e.g. during rollback) must not count its own prior model against
the limit, and a completely different database's in-process state (e.g.
a second isolated test run in the same Python process) must never be
counted at all. Both were real bugs caught during implementation — see
`docs/phase_15_report.md`.

## Verdict

`ResourceAssessment(verdict, reasons, measurement_label)` — `pass` only
when every check passes; any failure yields `fail` with the full list of
reasons, never a partial pass.
