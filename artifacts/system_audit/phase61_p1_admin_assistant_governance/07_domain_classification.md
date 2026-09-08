# 07 DOMAIN CLASSIFICATION

- Module: `core_model/corpus/domain_classification.py`.
- Architecture: Heuristic keyword matching + LLM reasoning suggestion + confidence score.
- Review Gate: `review_required = True` when `confidence < 0.80`.
