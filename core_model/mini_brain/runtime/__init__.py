"""MB-04: CPU Runtime & Model Integration -- pure domain logic.

State machine, memory-guard arithmetic, response formatting, and
model-file validation rules live here with zero I/O. The one
exception any pure module in this codebase makes is reading
`/proc/meminfo` for a real number -- `memory_guard.py` does that in
its own function, mirroring (not importing) the same honest
measure-or-report-unmeasurable pattern already used by
`InferenceRuntimeService._read_available_memory_bytes`.
"""
