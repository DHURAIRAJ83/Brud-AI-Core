# Phase 60 WS02 — Instruction-Following Specification

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS02 — Dataset Expansion Architecture & Curation Specification  
**Date:** 2026-08-31  
**Status:** ✅ **INSTRUCTION CONSTRAINTS & BEHAVIORS SPECIFIED**

---

## 1. Instruction Modalities
Instruction-following records must enforce explicit, measurable constraints:
1. **Length Constraints:** "In exactly 2 sentences...", "In under 30 words..."
2. **Format Constraints:** "Provide a bulleted list of exactly 3 items...", "Enclose output in quotes..."
3. **Language Constraints:** "Respond purely in Tamil without English loanwords...", "Use English only..."
4. **Ordering & Step Constraints:** "List chronologically...", "Number each step sequentially..."
5. **Inclusion/Exclusion Constraints:** "Do not use the letter 'e'...", "Mention the year of publication..."

Every record must include an `expected_behavior` assertion enabling programmatic validation.
