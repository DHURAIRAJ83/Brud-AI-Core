# Phase 58 Training Format Design Report

**Workstream:** 13 — Data Format Readiness  
**Timestamp:** 2026-08-30T17:52:00Z  
**Status:** ✅ DESIGN COMPLETE — INSTRUCTION TEMPLATES SPECIFIED (NOT YET EXECUTED)

---

## 1. The Transformation Requirement

Phase 57 established that **70.3% of the Phase 55 corpus consists of flat dictionary entries**, which failed to teach the model question-answering behavior.

In this design, we specify canonical prompt-response templates to transform unstructured records into instruction-following pairs for future training, **preserving all original records and provenance**.

---

## 2. Template Specifications Across 12 Modalities

| Modality | Input Context / Raw Record | Transformed Instruction Template |
|---|---|---|
| 1. Factual QA | Definition / encyclopedic sentence | `<user> [Question about entity] </user> <assistant> [Precise factual definition] </s>` |
| 2. Instruction $\to$ Answer | Directive statement | `<user> [Directive: e.g. விளக்குக] </user> <assistant> [Explanation] </s>` |
| 3. Tamil Grammar | Morphological rule / rule pair | `<user> [Word] என்பதன் [பன்மை/இலக்கணம்] வடிவம் என்ன? </user> <assistant> [Grammar target] </s>` |
| 4. Tamil $\to$ English | Bilingual glossary entry | `<user> Translate to English: [Tamil word] </user> <assistant> [English translation] </s>` |
| 5. English $\to$ Tamil | Bilingual glossary entry | `<user> தமிழில் மொழிபெயர்க்க: [English word] </user> <assistant> [Tamil translation] </s>` |
| 6. Tanglish $\to$ Tamil | Romanized Tamil string | `<user> Tanglish-ஐ தமிழில் எழுதவும்: [Tanglish sentence] </user> <assistant> [Tamil sentence] </s>` |
| 7. Deductive Reasoning | Premise statement | `<user> If [Premise A] and [Premise B], does [Query]? </user> <assistant> Yes/No, [Reasoning]. </s>` |
| 8. Arithmetic Grounding | Math word problem | `<user> [Math problem query] </user> <assistant> [Calculation & exact number] </s>` |
| 9. Intent Classification | Text snippet | `<user> Classify the intent: [Snippet] </user> <assistant> [Intent label] </s>` |
| 10. Grounded Extraction | Passage + query | `<user> Context: [Passage] Query: [Question] </user> <assistant> [Extracted answer] </s>` |
| 11. Concise Summary | Long passage | `<user> Summarize in one sentence: [Passage] </user> <assistant> [Summary] </s>` |
| 12. Conversational Turn | Greeting / exchange | `<user> வணக்கம்! </user> <assistant> வணக்கம்! நான் உங்களுக்கு எவ்வாறு உதவ முடியும்? </s>` |

---

## 3. Implementation Guardrails for Future Phases

- Original JSONL records remain 100% untouched.
- Transformation will generate a separate governed dataset (`phase59_instruction_records_v001.jsonl`).
- Merkle roots will be computed and verified before training.
