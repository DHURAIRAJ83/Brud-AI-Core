# Base Training Candidate Selection (Phase 11)

`select_candidate()` never picks a "winner" by training loss alone. It
combines Phase 10's training-process quality gate with Phase 11's
generalization/learning checks, and the result is always one of three
explicit statuses:

- `selected_base_candidate` — Phase 10 readiness is not `blocked`/`warning`,
  no learning check failed on a blocking code, no non-pass learning check,
  and no memorization warning.
- `selected_with_warnings` — the run is usable but Phase 10's
  `readiness_status == "warning"`, or any Phase 11 learning check is
  `warning`/`fail` on a non-blocking code, or a memorization warning fired.
- `rejected` — Phase 10's `readiness_status == "blocked"`, or a blocking-code
  learning check (`training_loss_improves`, `validation_loss_finite`,
  `no_non_finite_gradients`, `checkpoint_integrity`,
  `dataset_stream_integrity`) failed, or no run in the experiment ever
  completed.

## Selection procedure

1. Among all `completed`/`completed_with_warnings` runs in the experiment,
   pick the one with the lowest validation loss (`_best_validation_loss`).
2. Evaluate that run's held-out **test** split for the first time
   (`_evaluate_run(..., include_test=True)`) — this is the only place the
   test split is ever used.
3. Call Phase 10's `TrainingEvaluationService.assess_quality()` — training-
   process integrity only, unchanged from Phase 10.
4. Classify generalization (`classify_generalization`) and compute
   memorization warnings (`memorization_warnings`) — Phase 11 concerns,
   kept in a separate table from Phase 10's quality assessment
   (`base_training_candidate_selections`, not `training_quality_assessments`).
5. Derive the status from both signals as above.
6. If not `rejected`, call the existing `PretrainingService.promote()`
   (Phase 9/10, unchanged) to register a new `core_model_versions` row.

## The candidate never becomes chat-ready

`PretrainingService.promote()` always sets, on the promoted
`core_model_versions.architecture_summary_json`:

```json
{"base_pretrained": true, "not_instruction_tuned": true, "not_chat_ready": true, ...}
```

The promoted model's `lifecycle_status` is `staging`, never `active`, and
nothing in Phase 11 (or any earlier phase) assigns a base-pretrained model
to `/api/chat`. `backend/api/routes/chat.py` remains a hardcoded
`model="placeholder"` response regardless of how many experiments complete
— this is verified directly in `tests/backend/test_base_training_api.py`
by calling `/api/chat` after a successful candidate selection and asserting
the response is still the placeholder.

## Override comments

If Phase 10's `readiness_status == "warning"`, `PretrainingService.promote()`
requires a non-empty `override_comment` (an existing Phase 10 rule, not
new). `CandidateSelectionRequest.override_comment` threads through
`select_candidate()` for this case; omitting it when required surfaces as a
`ValidationError`, not a silent skip.
