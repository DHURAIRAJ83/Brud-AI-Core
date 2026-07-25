# Feedback Admin Dashboard

`apps/admin-dashboard/src/pages/FeedbackPage.jsx`, wired into `App.jsx`
(`active === 'Feedback & Improvement'`) and `Sidebar.jsx` (nav item
placed after "Conversation & Memory", replacing the earlier
Phase-1-era placeholder "Feedback" stub entry; footer phase tag
updated to "Phase 18 · Feedback improvement pipeline").

## Tabs (16)

Overview, Feedback Policies, Feedback Events, Classification, Review
Queues, Human Reviews, Corrected Responses, Privacy & Safety, Dataset
Candidates, Candidate Quality, Candidate Approvals, Regression Suites,
Regression Runs, Model Comparisons, Improvement Reports,
Reproducibility.

Structural pattern mirrors `ConversationMemoryPage.jsx`/`RagPage.jsx`
exactly: tab navigation, `state`/`panelError` React state, a left-side
data list plus a right-side tabbed detail panel, `StatusCard`
components on the Overview tab.

## Required disclaimers (always rendered, verbatim)

- Page-level, always visible: *"Feedback is reviewed,
  privacy-filtered, and explicitly approved before it can become a
  dataset candidate. No automatic self-training occurs."*
- Dataset Candidates tab: *"An approved feedback candidate still
  passes through the existing dataset quality and versioning pipeline
  before training use."*
- Regression Suites and Regression Runs tabs: *"Regression fixtures
  are evaluation-only evidence and must not automatically become
  training records."*

## API integration

`apps/admin-dashboard/src/services/api.js` gained ~55 functions under
`const FB = '/api/admin/feedback'`, covering every route in
`docs/feedback_api_cli.md`.

## Build verification

`cd apps/admin-dashboard && npm run build` — succeeded. `cd
apps/chatbot && npm run build` — succeeded unchanged (placeholder chat
UI untouched by this phase).
